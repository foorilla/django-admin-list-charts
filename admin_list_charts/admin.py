import hashlib
import json

from django.conf import settings
from django.contrib.admin import FieldListFilter, SimpleListFilter
from django.contrib.admin.options import IncorrectLookupParameters
from django.core import checks
from django.core.cache import caches
from django.core.exceptions import EmptyResultSet, FieldDoesNotExist, PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.http import HttpResponseNotAllowed, JsonResponse
from django.urls import path, reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from .charts import ChartBuilder, metric_paths


class ListChartMixin:
    change_list_template = 'admin_list_charts/change_list_with_chart.html'
    chart_facet_fields = ()
    chart_rate_fields = ()
    chart_top_fields = ()
    chart_metrics = {}
    chart_labels = {}
    chart_facet_max_series = 6
    chart_auto_select = True
    chart_auto_max_facet_fields = 3
    chart_auto_max_rate_fields = 2
    chart_lazy = False
    chart_cache_timeout = 0
    chart_cache_alias = 'default'

    def get_chart_field(self, request, queryset, name):
        """Resolve a single-valued model path or scalar queryset annotation."""
        annotation = queryset.query.annotations.get(name)
        if annotation is not None:
            return annotation.output_field
        model = queryset.model
        parts = name.split('__')
        for index, part in enumerate(parts):
            try:
                field = model._meta.pk if part == 'pk' else model._meta.get_field(part)
            except FieldDoesNotExist:
                return None
            if field.many_to_many or field.one_to_many:
                return None
            if index < len(parts) - 1:
                if not field.is_relation:
                    return None
                model = field.related_model
        return field

    def get_chart_date_field(self, request):
        if self.date_hierarchy:
            return self.date_hierarchy
        if not self.chart_auto_select:
            return None
        fields = {
            field.name: field for field in self.model._meta.concrete_fields
            if isinstance(field, models.DateField)
            and not field.primary_key and not field.auto_now
            and not field.name.startswith(('updated', 'modified', 'last_modified', 'last_updated'))
        }
        for name in ('created_at', 'created', 'date_created', 'date_joined',
                     'published_at', 'published', 'timestamp'):
            if name in fields:
                return name
        return next(iter(fields)) if len(fields) == 1 else None

    def get_chart_queryset(self, request, changelist):
        return changelist.queryset

    def get_chart_facet_fields(self, request):
        return tuple(self.chart_facet_fields)

    def get_chart_rate_fields(self, request):
        return tuple(self.chart_rate_fields)

    def get_chart_top_fields(self, request):
        return tuple(self.chart_top_fields)

    def get_chart_metrics(self, request):
        """A mapping of display names to Django Count, Sum or Avg expressions."""
        return self.chart_metrics

    def get_chart_auto_max_facet_fields(self, request):
        return max(0, int(self.chart_auto_max_facet_fields))

    def get_chart_auto_max_rate_fields(self, request):
        return max(0, int(self.chart_auto_max_rate_fields))

    def get_chart_palette(self, request):
        config = getattr(settings, 'ADMIN_LIST_CHARTS', {})
        palette = config.get('palette', {}) if isinstance(config, dict) else {}
        if not isinstance(palette, dict):
            return {}
        result = {}
        accent = palette.get('accent')
        if isinstance(accent, str) and accent.strip():
            result['accent'] = accent.strip()
        series = palette.get('series')
        if isinstance(series, (list, tuple)):
            colors = [color.strip() for color in series if isinstance(color, str) and color.strip()]
            if colors:
                result['series'] = colors
        return result

    def _get_chart_period(self, request):
        name = self.get_chart_date_field(request)
        for suffix, period in (('day', 'hour'), ('month', 'day'), ('year', 'week')):
            if name and f'{name}__{suffix}' in request.GET:
                return period
        return 'month'

    def get_chart_link(self, request, field_name, value, end=None):
        """Override for annotation dimensions or custom filter semantics."""
        field = ListChartMixin.get_chart_field(
            self, request, self.model._default_manager.all(), field_name)
        if field is None:
            return None
        for item in self.get_list_filter(request):
            if isinstance(item, type) and issubclass(item, SimpleListFilter):
                parameter = item.parameter_name
                if parameter == field_name or parameter.startswith(field_name + '__'):
                    return None
            if isinstance(item, (tuple, list)) and item[0] == field_name:
                filter_class = item[1]
                if not (isinstance(filter_class, type) and issubclass(filter_class, FieldListFilter)
                        and filter_class.__module__ == 'django.contrib.admin.filters'):
                    return None
        lookup = field_name + ('__gte' if end is not None else '__isnull' if value is None else '__exact')
        if not self.lookup_allowed(lookup, value, request):
            return None
        if end is not None and not self.lookup_allowed(field_name + '__lt', end, request):
            return None
        params = request.GET.copy()
        params.pop('p', None)
        for key in list(params):
            if key == field_name or key.startswith(field_name + '__'):
                params.pop(key)
        if end is not None:
            params[field_name + '__gte'] = value.isoformat()
            params[field_name + '__lt'] = end.isoformat()
        elif value is None:
            params[field_name + '__isnull'] = 'True'
        else:
            params[field_name + '__exact'] = str(value)
        return '?' + params.urlencode()

    def get_chart_payload(self, request, qs, period=None, facets_on=True, total_rows=None):
        # facets_on remains accepted for callers upgrading from 0.4; charts are always visible.
        return ChartBuilder(self, request, qs).build(period or self._get_chart_period(request), total_rows)

    def _chart_payload(self, request, changelist):
        queryset = self.get_chart_queryset(request, changelist)
        key = None
        if self.chart_cache_timeout:
            try:
                sql, params = queryset.query.get_compiler(using=queryset.db).as_sql()
            except EmptyResultSet:
                sql, params = 'EMPTY', ()
            config = {
                'class': f'{type(self).__module__}.{type(self).__qualname__}',
                'model': self.model._meta.label_lower,
                'date': self.get_chart_date_field(request),
                'facets': self.get_chart_facet_fields(request),
                'rates': self.get_chart_rate_fields(request),
                'tops': self.get_chart_top_fields(request),
                'metrics': repr(self.get_chart_metrics(request)),
                'labels': self.chart_labels,
                'auto': self.chart_auto_select,
                'filters': repr(self.get_list_filter(request)),
                'limits': [self.chart_facet_max_series, self.get_chart_auto_max_facet_fields(request),
                           self.get_chart_auto_max_rate_fields(request)],
                'palette': self.get_chart_palette(request),
                'user': [request.user.pk, request.user.is_superuser],
                'query': [request.path, sorted(request.GET.lists()), sql, params],
                'database': queryset.db,
                'language': translation.get_language(),
                'timezone': timezone.get_current_timezone_name(),
                'count': changelist.result_count,
            }
            digest = hashlib.sha256(json.dumps(config, default=str, sort_keys=True).encode()).hexdigest()
            key = 'admin_list_charts:1:' + digest
            cached = caches[self.chart_cache_alias].get(key)
            if cached is not None:
                return cached
        total = changelist.result_count if queryset is changelist.queryset else None
        payload = self.get_chart_payload(request, queryset, total_rows=total)
        payload['object_label'] = str(changelist.opts.verbose_name_plural)
        payload['palette'] = self.get_chart_palette(request)
        if key:
            caches[self.chart_cache_alias].set(key, payload, self.chart_cache_timeout)
        return payload

    def get_urls(self):
        info = self.opts.app_label, self.opts.model_name
        return [path('chart-data/', self.admin_site.admin_view(self.chart_data_view),
                     name='%s_%s_chart_data' % info)] + super().get_urls()

    def chart_data_view(self, request):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        if request.method not in ('GET', 'HEAD'):
            response = HttpResponseNotAllowed(['GET', 'HEAD'])
        else:
            # Reuse the page's filtering and permissions without rendering or pagination.
            try:
                changelist = self.get_changelist_instance(request)
            except IncorrectLookupParameters:
                response = JsonResponse({'error': _('Invalid changelist filters.')}, status=400)
            else:
                response = JsonResponse(self._chart_payload(request, changelist), encoder=DjangoJSONEncoder)
        response['Cache-Control'] = 'private, no-store'
        return response

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        context = getattr(response, 'context_data', None)
        if not context or 'cl' not in context:
            return response
        if self.chart_lazy:
            name = '%s_%s_chart_data' % (self.opts.app_label, self.opts.model_name)
            url = reverse(f'{self.admin_site.name}:{name}')
            context['chart_endpoint'] = url + ('?' + request.GET.urlencode() if request.GET else '')
        else:
            payload = self._chart_payload(request, context['cl'])
            context['chart_payload'] = payload
            context['chart_period'] = payload['period']
        return response

    def check(self, **kwargs):
        errors = super().check(**kwargs)
        queryset = self.model._default_manager.all()
        for name in (*self.chart_facet_fields, *self.chart_rate_fields,
                     *(item[0] for item in self.chart_top_fields)):
            # Annotations are request-dependent and are validated when their query is built.
            if self.get_chart_field(None, queryset, name) is None:
                errors.append(checks.Warning(
                    _('Chart field “%(name)s” is not a single-valued model field; '
                      'provide it as a scalar queryset annotation.') % {'name': name},
                    obj=self.__class__, id='admin_list_charts.W001'))
        for name, expression in self.chart_metrics.items():
            if not isinstance(expression, (models.Count, models.Sum, models.Avg)):
                errors.append(checks.Error(
                    f'Chart metric {name!r} must be Count, Sum or Avg.',
                    obj=self.__class__, id='admin_list_charts.E001'))
                continue
            for path_name in metric_paths(expression):
                parts = path_name.split('__')
                model = self.model
                for part in parts:
                    try:
                        field = model._meta.get_field(part)
                    except FieldDoesNotExist:
                        break  # Scalar annotation or lookup suffix.
                    if field.many_to_many or field.one_to_many:
                        errors.append(checks.Error(
                            f'Chart metric {name!r} traverses a multi-valued relation; '
                            'annotate a scalar subquery first.',
                            obj=self.__class__, id='admin_list_charts.E003'))
                        break
                    if not field.is_relation:
                        break
                    model = field.related_model
        for name in ('chart_facet_max_series', 'chart_auto_max_facet_fields',
                     'chart_auto_max_rate_fields', 'chart_cache_timeout'):
            if not isinstance(getattr(self, name), int) or getattr(self, name) < 0:
                errors.append(checks.Error(f'{name} must be a nonnegative integer.',
                                          obj=self.__class__, id='admin_list_charts.E002'))
        return errors

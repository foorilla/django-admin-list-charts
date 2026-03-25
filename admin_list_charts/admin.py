import json

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Avg, Case, Count, DateTimeField, FloatField, Value, When
from django.db.models.functions import Trunc


class ListChartMixin(object):
    change_list_template = 'admin_list_charts/change_list_with_chart.html'
    chart_facet_fields = ()
    chart_rate_fields = ()
    chart_top_fields = ()
    chart_facet_max_series = 6
    chart_auto_select = True
    chart_auto_max_facet_fields = 4
    chart_auto_max_rate_fields = 3

    def _get_chart_period(self, request):
        if self.date_hierarchy + '__day' in request.GET:
            return 'hour'
        if self.date_hierarchy + '__month' in request.GET:
            return 'day'
        if self.date_hierarchy + '__year' in request.GET:
            return 'week'
        return 'month'

    def get_chart_facet_fields(self, request):
        return tuple(getattr(self, 'chart_facet_fields', ()))

    def get_chart_rate_fields(self, request):
        return tuple(getattr(self, 'chart_rate_fields', ()))

    def get_chart_top_fields(self, request):
        return tuple(getattr(self, 'chart_top_fields', ()))

    def get_chart_auto_max_facet_fields(self, request):
        return max(0, int(getattr(self, 'chart_auto_max_facet_fields', 4)))

    def get_chart_auto_max_rate_fields(self, request):
        return max(0, int(getattr(self, 'chart_auto_max_rate_fields', 3)))

    def get_chart_palette(self, request):
        config = getattr(settings, 'ADMIN_LIST_CHARTS', {})
        if not isinstance(config, dict):
            return {}

        palette = config.get('palette', {})
        if not isinstance(palette, dict):
            return {}

        normalized = {}
        accent = palette.get('accent')
        if isinstance(accent, str) and accent.strip():
            normalized['accent'] = accent.strip()

        series = palette.get('series')
        if isinstance(series, (list, tuple)):
            clean_series = [
                color.strip()
                for color in series
                if isinstance(color, str) and color.strip()
            ]
            if clean_series:
                normalized['series'] = clean_series

        return normalized

    def _get_auto_list_filter_facet_candidates(self):
        candidates = []
        seen = set()

        for raw_filter in getattr(self, 'list_filter', ()) or ():
            field_name = None
            if isinstance(raw_filter, str):
                field_name = raw_filter
            elif isinstance(raw_filter, (tuple, list)) and raw_filter:
                head = raw_filter[0]
                if isinstance(head, str):
                    field_name = head

            if isinstance(field_name, str) and '__' in field_name:
                field_name = field_name.split('__', 1)[0]

            if not field_name or field_name in seen:
                continue

            field = self._get_model_field(field_name)
            if field is None:
                continue
            if not getattr(field, 'concrete', False):
                continue
            if getattr(field, 'many_to_many', False) or getattr(field, 'one_to_many', False):
                continue
            if field.name == self.date_hierarchy:
                continue

            seen.add(field_name)
            candidates.append(field_name)

        return candidates

    def _get_auto_choice_facet_candidates(self):
        candidates = []
        for field in self.model._meta.get_fields():
            if not getattr(field, 'concrete', False):
                continue
            if getattr(field, 'many_to_many', False) or getattr(field, 'one_to_many', False):
                continue
            if not getattr(field, 'choices', None):
                continue
            if field.name == self.date_hierarchy:
                continue
            candidates.append(field.name)
        return candidates

    def _get_auto_boolean_rate_candidates(self):
        candidates = []
        for field in self.model._meta.get_fields():
            if not getattr(field, 'concrete', False):
                continue
            if isinstance(field, models.BooleanField):
                candidates.append(field.name)
        return candidates

    def _select_auto_facet_fields(self, qs, request, total_rows, exclude_fields=None):
        max_fields = self.get_chart_auto_max_facet_fields(request)
        if max_fields <= 0 or total_rows <= 0:
            return ()

        exclude_fields = set(exclude_fields or ())

        sequential_candidates = self._get_auto_list_filter_facet_candidates()
        fallback_candidates = self._get_auto_choice_facet_candidates()
        all_candidates = sequential_candidates + [
            field_name for field_name in fallback_candidates if field_name not in sequential_candidates
        ]

        if not all_candidates:
            return ()

        scored = []
        for candidate_index, field_name in enumerate(all_candidates):
            if field_name in exclude_fields:
                continue
            rows = list(qs.values(field_name).annotate(c=Count('pk')).order_by('-c'))
            non_empty_rows = [
                row
                for row in rows
                if row[field_name] not in (None, '')
            ]
            non_empty_total = sum(row['c'] for row in non_empty_rows)
            if non_empty_total == 0:
                continue

            unique_count = len(non_empty_rows)
            dominant_share = non_empty_rows[0]['c'] / non_empty_total if non_empty_rows else 1.0
            diversity = min(unique_count, self.chart_facet_max_series) / max(1, self.chart_facet_max_series)
            coverage = non_empty_total / total_rows
            spread = 1.0 - dominant_share
            sequence_bias = max(0.0, 1.0 - (candidate_index * 0.1))
            score = (coverage * 0.45) + (spread * 0.3) + (diversity * 0.15) + (sequence_bias * 0.1)
            scored.append(
                {
                    'field': field_name,
                    'score': score,
                    'index': candidate_index,
                }
            )

        if not scored:
            return ()

        ranked = sorted(scored, key=lambda item: item['score'], reverse=True)
        selected = [item['field'] for item in ranked if item['score'] >= 0.25][:max_fields]

        if len(selected) < max_fields:
            for item in sorted(scored, key=lambda item: item['index']):
                if item['field'] in selected:
                    continue
                selected.append(item['field'])
                if len(selected) >= max_fields:
                    break

        return tuple(selected[:max_fields])

    def _select_auto_rate_fields(self, qs, request):
        max_fields = self.get_chart_auto_max_rate_fields(request)
        if max_fields <= 0:
            return ()

        candidates = self._get_auto_boolean_rate_candidates()
        if not candidates:
            return ()

        annotations = {}
        for field_name in candidates:
            annotations[field_name] = Avg(
                Case(
                    When(**{field_name: True}, then=Value(1.0)),
                    default=Value(0.0),
                    output_field=FloatField(),
                )
            )

        rates = qs.aggregate(**annotations)
        scored = []
        for field_name in candidates:
            rate = float(rates.get(field_name) or 0.0)
            balance_score = 1.0 - abs(0.5 - rate) * 2.0
            scored.append((field_name, balance_score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return tuple(field_name for field_name, _ in scored[:max_fields])

    def _get_model_field(self, field_name):
        try:
            return self.model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return None

    def _get_relation_display_map(self, field, keys):
        if field is None:
            return {}
        if not (
            getattr(field, 'many_to_one', False)
            or getattr(field, 'one_to_one', False)
            or getattr(field, 'many_to_many', False)
        ):
            return {}

        related_model = getattr(field, 'related_model', None)
        if related_model is None:
            return {}

        label_attr = None
        for candidate in ('label', 'name'):
            if hasattr(related_model, candidate):
                label_attr = candidate
                break

        if label_attr is None:
            return {}

        relation_ids = [key for key in keys if key not in (None, '')]
        if not relation_ids:
            return {}

        objects = related_model._default_manager.filter(pk__in=relation_ids)
        display_map = {}
        for obj in objects:
            relation_id = getattr(obj, related_model._meta.pk.attname)
            display_value = getattr(obj, label_attr, None)
            if display_value in (None, ''):
                display_value = relation_id
            display_map[relation_id] = str(display_value)

        return display_map

    def _display_value(self, field, value, relation_display_map=None):
        if value in (None, ''):
            return '(empty)'
        if relation_display_map and value in relation_display_map:
            return relation_display_map[value]
        if field is not None and getattr(field, 'choices', None):
            choices = dict(field.flatchoices)
            return str(choices.get(value, value))
        if isinstance(value, bool):
            return 'Yes' if value else 'No'
        return str(value)

    def _get_volume_data(self, qs, period):
        rows = (
            qs.annotate(
                x=Trunc(self.date_hierarchy, period, output_field=DateTimeField())
            )
            .values('x')
            .annotate(y=Count('pk'))
            .order_by('x')
        )
        return list(rows)

    def _get_facet_data(self, qs, period, field_name):
        field = self._get_model_field(field_name)
        if field is None:
            return None

        rows = (
            qs.annotate(
                x=Trunc(self.date_hierarchy, period, output_field=DateTimeField())
            )
            .values('x', field_name)
            .annotate(y=Count('pk'))
            .order_by('x')
        )

        totals = {}
        points = {}
        for row in rows:
            key = row[field_name]
            totals[key] = totals.get(key, 0) + row['y']
            points.setdefault(key, []).append({'x': row['x'], 'y': row['y']})

        keys = [
            key
            for key, _ in sorted(totals.items(), key=lambda item: item[1], reverse=True)[
                : self.chart_facet_max_series
            ]
        ]
        relation_display_map = self._get_relation_display_map(field, keys)

        series = [
            {
                'key': key,
                'label': self._display_value(field, key, relation_display_map),
                'data': points.get(key, []),
            }
            for key in keys
        ]
        return {
            'field': field_name,
            'label': str(getattr(field, 'verbose_name', field_name)).title(),
            'series': series,
        }

    def _get_rate_data(self, qs, period, rate_fields):
        annotations = {}
        valid_fields = []
        for field_name in rate_fields:
            field = self._get_model_field(field_name)
            if field is None:
                continue
            valid_fields.append((field_name, field))
            annotations[field_name] = Avg(
                Case(
                    When(**{field_name: True}, then=Value(1.0)),
                    default=Value(0.0),
                    output_field=FloatField(),
                )
            )

        if not annotations:
            return []

        rows = (
            qs.annotate(
                x=Trunc(self.date_hierarchy, period, output_field=DateTimeField())
            )
            .values('x')
            .annotate(**annotations)
            .order_by('x')
        )

        series = []
        for field_name, field in valid_fields:
            data = [{'x': row['x'], 'y': float(row[field_name] or 0.0)} for row in rows]
            series.append(
                {
                    'field': field_name,
                    'label': str(getattr(field, 'verbose_name', field_name)).title(),
                    'data': data,
                }
            )
        return series

    def _get_top_data(self, qs, top_fields):
        charts = []
        for field_name, limit in top_fields:
            field = self._get_model_field(field_name)
            if field is None:
                continue
            rows = list(
                qs.values(field_name)
                .annotate(y=Count('pk'))
                .order_by('-y')[: max(1, int(limit))]
            )
            relation_display_map = self._get_relation_display_map(
                field,
                [row[field_name] for row in rows],
            )
            data = [
                {
                    'x': self._display_value(
                        field,
                        row[field_name],
                        relation_display_map,
                    ),
                    'y': row['y'],
                }
                for row in rows
            ]
            charts.append(
                {
                    'field': field_name,
                    'label': str(getattr(field, 'verbose_name', field_name)).title(),
                    'data': data,
                }
            )
        return charts

    def get_chart_payload(self, request, qs, period, facets_on=False, total_rows=None):
        if total_rows is None:
            total_rows = qs.count()

        payload = {
            'period': period,
            'volume': self._get_volume_data(qs, period),
            'facets_on': bool(facets_on),
            'facets': [],
            'rates': [],
            'tops': [],
        }

        if not facets_on:
            return payload

        rate_fields = self.get_chart_rate_fields(request)
        if not rate_fields and self.chart_auto_select:
            rate_fields = self._select_auto_rate_fields(qs, request)
        rate_field_set = set(rate_fields)

        if rate_fields:
            payload['rates'] = self._get_rate_data(qs, period, rate_fields)

        facet_fields = self.get_chart_facet_fields(request)
        if facet_fields:
            facet_fields = tuple(
                field_name for field_name in facet_fields if field_name not in rate_field_set
            )
        elif self.chart_auto_select:
            facet_fields = self._select_auto_facet_fields(
                qs,
                request,
                total_rows,
                exclude_fields=rate_field_set,
            )

        for field_name in facet_fields:
            facet = self._get_facet_data(qs, period, field_name)
            if facet and facet['series']:
                payload['facets'].append(facet)

        top_fields = self.get_chart_top_fields(request)
        if top_fields:
            payload['tops'] = self._get_top_data(qs, top_fields)

        return payload

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)

        if hasattr(self, 'date_hierarchy'):
            try:
                cl = response.context_data['cl']
                qs = cl.queryset
            except (AttributeError, KeyError):
                return response

            period = self._get_chart_period(request)
            facets_on = bool(getattr(cl, 'add_facets', False))
            total_count = getattr(cl, 'result_count', None)
            payload = self.get_chart_payload(
                request,
                qs,
                period,
                facets_on=facets_on,
                total_rows=total_count,
            )
            payload['total_count'] = total_count
            payload['object_label'] = str(getattr(cl.opts, 'verbose_name_plural', 'records'))
            payload['palette'] = self.get_chart_palette(request)

            response.context_data['chart_payload'] = json.dumps(payload, cls=DjangoJSONEncoder)
            response.context_data['chart_data'] = json.dumps(payload['volume'], cls=DjangoJSONEncoder)
            response.context_data['chart_period'] = period

        return response

"""Bounded chart discovery and aggregation, independent of admin rendering."""
from datetime import date, datetime, timedelta
from datetime import timezone as datetime_timezone

from django.conf import settings
from django.db import models
from django.db.models import Count, Max, Min, OuterRef, Q, Subquery, Value
from django.db.models.functions import ExtractYear, Floor, Trunc
from django.utils import formats, timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext


PERIODS = ('hour', 'day', 'week', 'month', 'quarter', 'year')
MAX_BUCKETS = 240


def metric_paths(expression):
    for node in expression.flatten():
        if isinstance(node, models.F):
            yield node.name
        elif isinstance(node, Q):
            for child in node.children:
                if isinstance(child, tuple):
                    yield child[0]


def next_bucket(value, period, step=1):
    if period == 'hour':
        result = value + timedelta(hours=1)
        # Skip nonexistent local hours while keeping Django's local-hour grouping.
        return result.astimezone(datetime_timezone.utc).astimezone(result.tzinfo) if timezone.is_aware(result) else result
    if period == 'day':
        return value + timedelta(days=1)
    if period == 'week':
        return value + timedelta(days=7)
    if period in ('month', 'quarter'):
        month = value.month - 1 + (3 if period == 'quarter' else 1)
        return value.replace(year=value.year + month // 12, month=month % 12 + 1, day=1)
    return value.replace(year=value.year + step, month=1, day=1)


def bucket_count(first, last, period):
    if period == 'hour':
        return int((last - first).total_seconds() // 3600) + 1
    if period == 'day':
        return (last - first).days + 1
    if period == 'week':
        return (last - first).days // 7 + 1
    if period in ('month', 'quarter'):
        months = (last.year - first.year) * 12 + last.month - first.month
        return months // (3 if period == 'quarter' else 1) + 1
    return last.year - first.year + 1


class ChartBuilder:
    def __init__(self, admin, request, queryset):
        self.admin = admin
        self.request = request
        self.source = queryset
        # A semijoin counts every base object once, even after M2M searches or filters.
        # Scalar annotations are correlated back only if a displayed chart needs them.
        source = queryset.order_by().select_related(None).prefetch_related(None)
        self.queryset = queryset.model._base_manager.using(queryset.db).filter(
            pk__in=source.values('pk'))
        annotations = {
            name: Subquery(source.annotate(**{name: models.F(name)})
                           .filter(pk=OuterRef('pk')).values(name)[:1])
            for name in source.query.annotations
        }
        if annotations:
            self.queryset = self.queryset.annotate(**annotations)
        self.fields = {}

    def field(self, name):
        if name not in self.fields:
            self.fields[name] = self.admin.get_chart_field(self.request, self.source, name)
        return self.fields[name]

    def label(self, name):
        field = self.field(name)
        label = str(self.admin.chart_labels.get(name, getattr(field, 'verbose_name', None)
                                               or name.replace('__', ' / ').replace('_', ' ')))
        return label[:1].upper() + label[1:]

    def metric_valid(self, expression):
        for path in metric_paths(expression):
            parts = path.split('__')
            while parts and self.field('__'.join(parts)) is None:
                parts.pop()
            if not parts:
                return False
            field = self.field('__'.join(parts))
            if field.is_relation and len(parts) < len(path.split('__')):
                return False
        return True

    def candidates(self):
        names = []
        for item in self.admin.get_list_filter(self.request) or ():
            name = item if isinstance(item, str) else item[0] if isinstance(item, (tuple, list)) else None
            if name:
                names.append(name)
        fields = self.source.model._meta.concrete_fields
        names.extend(field.name for field in fields if field.choices)
        names.extend(field.name for field in fields if isinstance(field, models.BooleanField))
        result = []
        for name in dict.fromkeys(names):
            field = self.field(name)
            if (field is not None and not field.is_relation and not field.primary_key
                    and (isinstance(field, models.BooleanField) or field.choices)):
                result.append(name)
        return result

    def build(self, period, total_rows):
        payload = {'period': period, 'volume': [], 'rates': [], 'metrics': [],
                   'facets': [], 'tops': [], 'total_count': total_rows,
                   'date_field': None, 'date_label': '', 'missing_dates': 0}
        if total_rows == 0:
            return payload
        date_name = self.admin.get_chart_date_field(self.request)
        if date_name and not isinstance(self.field(date_name), models.DateField):
            date_name = None
        candidates = self.candidates() if self.admin.chart_auto_select else []
        rates = self.admin.get_chart_rate_fields(self.request)
        if not rates:
            rates = tuple(name for name in candidates if isinstance(self.field(name), models.BooleanField))[
                :self.admin.get_chart_auto_max_rate_fields(self.request)]
        rates = [name for name in dict.fromkeys(rates) if isinstance(self.field(name), models.BooleanField)]
        if date_name:
            payload['date_field'] = date_name
            payload['date_label'] = self.label(date_name)
            self.timeline(payload, date_name, period, rates)
        facets = self.admin.get_chart_facet_fields(self.request)
        explicit_facets = bool(facets)
        if not facets:
            facets = [name for name in candidates if not date_name or name not in rates][
                :self.admin.get_chart_auto_max_facet_fields(self.request)]
        tops = dict(self.admin.get_chart_top_fields(self.request))
        for name in dict.fromkeys(facets):
            if name in tops:
                continue
            chart = self.distribution(name, self.admin.chart_facet_max_series, explicit_facets)
            if chart:
                payload['facets'].append(chart)
        for name, limit in tops.items():
            chart = self.distribution(name, limit, True)
            if chart:
                payload['tops'].append(chart)
        payload['missing_dates_label'] = ngettext(
            '%(count)s record has no date.', '%(count)s records have no date.',
            payload['missing_dates']) % {'count': payload['missing_dates']}
        return payload

    def timeline(self, payload, date_name, period, rate_names):
        field = self.field(date_name)
        if not isinstance(field, models.DateTimeField) and period == 'hour':
            period = 'day'
        aggregates = {'_alc_count': Count('pk')}
        for index, name in enumerate(rate_names):
            aggregates[f'_alc_true_{index}'] = Count('pk', filter=Q(**{name: True}))
            aggregates[f'_alc_known_{index}'] = Count('pk', filter=Q(**{name + '__isnull': False}))
        metrics = {
            name: expression for name, expression in self.admin.get_chart_metrics(self.request).items()
            if isinstance(expression, (models.Count, models.Sum, models.Avg))
            and self.metric_valid(expression)
        }
        for index, expression in enumerate(metrics.values()):
            aggregates[f'_alc_metric_{index}'] = expression
        dated = self.queryset.order_by()
        step = 1
        while True:
            if step == 1:
                expression = Trunc(date_name, period)
            else:
                expression = Floor((ExtractYear(date_name) - Value(1)) / Value(float(step)))
            rows = list(dated.annotate(_alc_bucket=expression).values('_alc_bucket')
                        .annotate(**aggregates).order_by('_alc_bucket')[:MAX_BUCKETS + 2])
            missing = next((row['_alc_count'] for row in rows if row['_alc_bucket'] is None), 0)
            rows = [row for row in rows if row['_alc_bucket'] is not None]
            if not rows:
                payload['missing_dates'] = missing
                if payload['total_count'] is None:
                    payload['total_count'] = missing
                return
            if step > 1:
                for row in rows:
                    year = int(row['_alc_bucket']) * step + 1
                    row['_alc_bucket'] = (
                        datetime(year, 1, 1, tzinfo=timezone.get_current_timezone() if settings.USE_TZ else None)
                        if isinstance(field, models.DateTimeField) else date(year, 1, 1))
            if (len(rows) <= MAX_BUCKETS
                    and (step > 1 or bucket_count(rows[0]['_alc_bucket'], rows[-1]['_alc_bucket'], period) <= MAX_BUCKETS)):
                break
            if period != 'year':
                period = PERIODS[PERIODS.index(period) + 1]
            else:
                bounds = dated.aggregate(first=Min(date_name), last=Max(date_name))
                step = (bounds['last'].year - bounds['first'].year) // (MAX_BUCKETS - 1) + 1
        payload['period'] = period
        payload['year_step'] = step
        points = {row['_alc_bucket']: row for row in rows}
        first, last = rows[0]['_alc_bucket'], rows[-1]['_alc_bucket']
        buckets = []
        current = first
        while current <= last and len(buckets) < MAX_BUCKETS:
            buckets.append(current)
            if current == last:
                break
            current = next_bucket(current, period, step)
        counts = sum(row['_alc_count'] for row in rows)
        payload['missing_dates'] = missing
        if payload['total_count'] is None:
            payload['total_count'] = counts + missing
        for bucket in buckets:
            row = points.get(bucket, {})
            try:
                end = next_bucket(bucket, period, step)
            except (OverflowError, ValueError):
                end = None
            payload['volume'].append({
                'x': bucket.isoformat(),
                'label': self.date_label(bucket, period, step),
                'y': row.get('_alc_count', 0),
                'url': self.admin.get_chart_link(self.request, date_name, bucket, end) if end else None,
            })
        for index, name in enumerate(rate_names):
            true_count = sum(row[f'_alc_true_{index}'] for row in rows)
            known_count = sum(row[f'_alc_known_{index}'] for row in rows)
            if not true_count or true_count == known_count:
                continue
            data = []
            for bucket in buckets:
                row = points.get(bucket, {})
                known = row.get(f'_alc_known_{index}', 0)
                value = row.get(f'_alc_true_{index}', 0) / known if known else None
                data.append({'x': bucket.isoformat(), 'y': value})
            payload['rates'].append({'field': name, 'label': self.label(name), 'data': data})
        for index, (name, expression) in enumerate(metrics.items()):
            default = 0 if isinstance(expression, models.Count) else None
            data = [{'x': bucket.isoformat(), 'y': points.get(bucket, {}).get(f'_alc_metric_{index}', default)}
                    for bucket in buckets]
            payload['metrics'].append({'field': name, 'label': self.label(name), 'data': data})

    @staticmethod
    def date_label(value, period, step):
        if period == 'hour':
            return formats.date_format(value, 'SHORT_DATETIME_FORMAT')
        if period in ('day', 'week'):
            return formats.date_format(value, 'DATE_FORMAT')
        if period in ('month', 'quarter'):
            return formats.date_format(value, 'F Y')
        return str(value.year) if step == 1 else f'{value.year}–{min(9999, value.year + step - 1)}'

    def distribution(self, name, limit, explicit):
        field = self.field(name)
        if field is None:
            return None
        limit = max(1, min(100, int(limit)))
        rows = list(self.queryset.order_by().values(name).annotate(_alc_count=Count('pk'))
                    .order_by('-_alc_count', name)[:limit + 1])
        if (not rows or all(row[name] in (None, '') for row in rows)
                or (not explicit and len(rows) < 2)):
            return None
        truncated = len(rows) > limit
        rows = rows[:limit]
        labels = {}
        if field.is_relation:
            related = field.related_model
            target = getattr(field, 'target_field', related._meta.pk).name
            # Avoid __str__ methods causing per-object queries: use a scalar label.
            label_field = next((candidate for candidate in ('name', 'label', 'title')
                                if any(f.name == candidate and not f.is_relation for f in related._meta.concrete_fields)), target)
            labels = dict(related._default_manager.using(self.source.db).filter(
                **{target + '__in': [row[name] for row in rows if row[name] is not None]}
            ).values_list(target, label_field))
        choices = dict(field.flatchoices) if getattr(field, 'choices', None) else {}
        data = []
        for row in rows:
            value = row[name]
            if value is None or value == '':
                label = _('(empty)')
            elif value in labels:
                label = labels[value]
            elif value in choices:
                label = choices[value]
            elif isinstance(value, bool):
                label = _('Yes') if value else _('No')
            else:
                label = value
            data.append({'x': str(label), 'y': row['_alc_count'],
                         'url': self.admin.get_chart_link(self.request, name, value)})
        return {'field': name, 'label': self.label(name), 'data': data, 'truncated': truncated}

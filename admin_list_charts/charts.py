"""Chart discovery and exact aggregation, independent of admin rendering."""
from bisect import bisect_right
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone

from django.db import models
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Trunc
from django.utils import formats, timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext


MAX_BUCKETS = 240


def next_bucket(value, period, step=1):
    if period == 'hour':
        result = value + timedelta(hours=step)
        # Skip nonexistent local hours while keeping Django's local-hour grouping.
        return result.astimezone(datetime_timezone.utc).astimezone(result.tzinfo) if timezone.is_aware(result) else result
    if period == 'day':
        return value + timedelta(days=step)
    if period == 'week':
        return value + timedelta(days=7 * step)
    if period in ('month', 'quarter'):
        month = value.month - 1 + (3 if period == 'quarter' else 1) * step
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
        self.queryset = queryset.order_by().select_related(None).prefetch_related(None)
        # Ordinary sources retain the direct 0.4 aggregation path. Only joins
        # which can multiply base objects, or existing grouping/distinctness,
        # need a semijoin to preserve one count per object.
        query = self.queryset.query
        self.wrapped = bool(query.distinct or query.group_by is not None or any(
            (getattr(join.join_field, 'one_to_many', False)
             or getattr(join.join_field, 'many_to_many', False))
            and query.alias_refcount.get(alias, 0)
            for alias, join in query.alias_map.items() if hasattr(join, 'join_field')
        ))
        if self.wrapped:
            self.queryset = queryset.model._base_manager.using(queryset.db).filter(
                pk__in=self.queryset.values('pk'))
        self.fields = {}

    def field(self, name):
        if name not in self.fields:
            self.fields[name] = self.admin.get_chart_field(self.request, self.source, name)
        return self.fields[name]

    def label(self, name):
        field = self.field(name)
        label = str(self.admin.chart_labels.get(name, getattr(field, 'verbose_name', None)
                                               or name.replace('__', ' / ').replace('_', ' '))).strip()
        if label.lower().startswith('chart '):
            label = label[6:].lstrip()
        return label[:1].upper() + label[1:]

    def selected_queryset(self, names):
        """Resolve only annotations actually used by the selected chart."""
        annotations = {}
        source = self.source.order_by().select_related(None).prefetch_related(None)
        for name in names:
            if name not in source.query.annotations:
                continue
            if self.wrapped:
                annotations[name] = Subquery(source.annotate(**{name: models.F(name)})
                                            .filter(pk=OuterRef('pk')).values(name)[:1])
            else:
                # Promote aliases so values(name) can group by them as well.
                annotations[name] = models.F(name)
        return self.queryset.annotate(**annotations) if annotations else self.queryset

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

    def build(self, period, total_rows, facets_on=False):
        payload = {'period': period, 'volume': [], 'rates': [],
                   'facets': [], 'total_count': total_rows,
                   'date_field': None, 'date_label': '', 'missing_dates': 0}
        if total_rows == 0:
            return payload
        date_name = self.admin.get_chart_date_field(self.request)
        if date_name and not isinstance(self.field(date_name), models.DateField):
            date_name = None
        candidates = self.candidates() if facets_on and self.admin.chart_auto_select else []
        rates = self.admin.get_chart_rate_fields(self.request) if facets_on else ()
        if not rates:
            rates = tuple(name for name in candidates if isinstance(self.field(name), models.BooleanField))[
                :self.admin.get_chart_auto_max_rate_fields(self.request)]
        rates = [name for name in dict.fromkeys(rates) if isinstance(self.field(name), models.BooleanField)]
        if date_name:
            payload['date_field'] = date_name
            payload['date_label'] = self.label(date_name)
            self.timeline(payload, date_name, period, rates)
        facets = self.admin.get_chart_facet_fields(self.request) if facets_on else ()
        explicit_facets = bool(facets)
        if not facets:
            facets = [name for name in candidates if not date_name or name not in rates][
                :self.admin.get_chart_auto_max_facet_fields(self.request)]
        for name in dict.fromkeys(facets):
            chart = self.distribution(name, self.admin.chart_facet_max_series, explicit_facets)
            if chart:
                payload['facets'].append(chart)
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
        rows = list(self.selected_queryset([date_name, *rate_names])
                    .annotate(_alc_bucket=Trunc(date_name, period)).values('_alc_bucket')
                    .annotate(**aggregates).order_by('_alc_bucket'))
        missing = next((row['_alc_count'] for row in rows if row['_alc_bucket'] is None), 0)
        rows = [row for row in rows if row['_alc_bucket'] is not None]
        payload['missing_dates'] = missing
        if payload['total_count'] is None:
            payload['total_count'] = sum(row['_alc_count'] for row in rows) + missing
        payload['period'] = period
        if not rows:
            return
        first, last = rows[0]['_alc_bucket'], rows[-1]['_alc_bucket']
        span = bucket_count(first, last, period)
        step = (span + MAX_BUCKETS - 1) // MAX_BUCKETS
        payload['bucket_step'] = step
        buckets = []
        # Fixed multiples of the requested period, anchored to the first bucket.
        # Build boundaries once, then combine counts before calculating rates.
        for offset in range(0, span, step):
            bucket = next_bucket(first, period, offset) if offset else first
            if bucket > last:
                break
            if not buckets or bucket > buckets[-1]:
                buckets.append(bucket)
        points = {bucket: {} for bucket in buckets}
        for row in rows:
            bucket = buckets[bisect_right(buckets, row['_alc_bucket']) - 1]
            combined = points[bucket]
            for name in aggregates:
                combined[name] = combined.get(name, 0) + row[name]
        for index, bucket in enumerate(buckets):
            row = points[bucket]
            try:
                end = (buckets[index + 1] if index + 1 < len(buckets)
                       else next_bucket(first, period, ((bucket_count(first, bucket, period) - 1) // step + 1) * step))
            except (OverflowError, ValueError):
                end = None
            label = self.date_label(bucket, period)
            if step > 1:
                if end:
                    delta = timedelta(microseconds=1) if isinstance(end, datetime) else timedelta(days=1)
                    label += '–' + self.date_label(end - delta, period)
                else:
                    label += '–9999'
            payload['volume'].append({
                'x': bucket.isoformat(), 'label': label,
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

    @staticmethod
    def date_label(value, period):
        if period == 'hour':
            return formats.date_format(value, 'SHORT_DATETIME_FORMAT')
        if period in ('day', 'week'):
            return formats.date_format(value, 'DATE_FORMAT')
        if period in ('month', 'quarter'):
            return formats.date_format(value, 'F Y')
        return str(value.year)

    def distribution(self, name, limit, explicit):
        field = self.field(name)
        if field is None:
            return None
        limit = max(1, min(100, int(limit)))
        rows = list(self.selected_queryset([name]).values(name).annotate(_alc_count=Count('pk'))
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

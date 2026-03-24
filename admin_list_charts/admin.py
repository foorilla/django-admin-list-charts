import json

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
    chart_auto_max_facet_fields = 2
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
        return max(0, int(getattr(self, 'chart_auto_max_facet_fields', 2)))

    def get_chart_auto_max_rate_fields(self, request):
        return max(0, int(getattr(self, 'chart_auto_max_rate_fields', 3)))

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

    def _select_auto_facet_fields(self, qs, request, total_rows):
        max_fields = self.get_chart_auto_max_facet_fields(request)
        if max_fields <= 0 or total_rows <= 0:
            return ()

        scored = []
        for field_name in self._get_auto_choice_facet_candidates():
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
            score = (coverage * 0.5) + (spread * 0.35) + (diversity * 0.15)
            scored.append((field_name, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return tuple(field_name for field_name, _ in scored[:max_fields])

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

    def _display_value(self, field, value):
        if value in (None, ''):
            return '(empty)'
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

        series = [
            {
                'key': key,
                'label': self._display_value(field, key),
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
            rows = (
                qs.values(field_name)
                .annotate(y=Count('pk'))
                .order_by('-y')[: max(1, int(limit))]
            )
            data = [
                {'x': self._display_value(field, row[field_name]), 'y': row['y']}
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

        facet_fields = self.get_chart_facet_fields(request)
        if not facet_fields and self.chart_auto_select:
            facet_fields = self._select_auto_facet_fields(qs, request, total_rows)

        for field_name in facet_fields:
            facet = self._get_facet_data(qs, period, field_name)
            if facet and facet['series']:
                payload['facets'].append(facet)

        rate_fields = self.get_chart_rate_fields(request)
        if not rate_fields and self.chart_auto_select:
            rate_fields = self._select_auto_rate_fields(qs, request)

        if rate_fields:
            payload['rates'] = self._get_rate_data(qs, period, rate_fields)

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

            response.context_data['chart_payload'] = json.dumps(payload, cls=DjangoJSONEncoder)
            response.context_data['chart_data'] = json.dumps(payload['volume'], cls=DjangoJSONEncoder)
            response.context_data['chart_period'] = period

        return response

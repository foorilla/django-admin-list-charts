import gzip
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection, models
from django.db.models import Avg, Count, Exists, OuterRef, Q, Sum
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone as django_timezone

from admin_list_charts.admin import ListChartMixin
from tests.models import Ambiguous, Company, CompanyProfile, Dated, Event, Tag, Undated


class MagicAdmin(ListChartMixin, admin.ModelAdmin):
    pass


class ExistingAdmin(MagicAdmin):
    date_hierarchy = 'created_at'
    list_filter = ('company__active', 'company__source', 'status', 'enabled')
    search_fields = ('title', 'tags__name')


class ExplicitAdmin(ExistingAdmin):
    chart_facet_fields = ('company',)
    chart_rate_fields = ('enabled',)
    chart_top_fields = (('status', 1),)
    chart_metrics = {'revenue': Sum('amount'), 'average': Avg('amount')}
    chart_labels = {'revenue': 'Revenue (USD)'}


class AnnotatedAdmin(MagicAdmin):
    chart_rate_fields = ('subscribed',)
    chart_facet_fields = ('subscribed',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            subscribed=Exists(Company.objects.filter(pk=OuterRef('company_id'), active=True)))


class LazyAdmin(MagicAdmin):
    chart_lazy = True


# Register separate models as needed for real authenticated endpoint tests.
admin.site.register(Event, LazyAdmin)


class ListChartMixinTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser('tester', 'test@example.com', 'password')
        cls.company = Company.objects.create(name='Example', active=True, source='a')
        cls.other_company = Company.objects.create(name='Other', active=False, source='d')
        cls.start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        Event.objects.bulk_create([
            Event(created_at=cls.start, status='a', enabled=True, amount=Decimal('10'), company=cls.company),
            Event(created_at=cls.start, status='b', enabled=None, amount=Decimal('10'), company=cls.company),
            Event(created_at=cls.start, status='a', enabled=False, amount=Decimal('40'), company=cls.other_company),
            Event(created_at=cls.start + timedelta(days=65), status='b', enabled=True, amount=None),
            Event(created_at=None, status='a', enabled=False),
        ])

    def setUp(self):
        self.request = RequestFactory().get('/admin/tests/event/')
        self.request.user = self.user
        self.request.session = {}
        cache.clear()

    def build(self, admin_class=MagicAdmin, model=Event, queryset=None, **kwargs):
        obj = admin_class(model, admin.site)
        return obj.get_chart_payload(self.request, queryset if queryset is not None else model.objects.all(),
                                     total_rows=kwargs.pop('total_rows', 5), **kwargs)

    def test_mixin_only_discovery_and_bounded_queries(self):
        with self.assertNumQueries(2):  # One combined timeline/rates and one status distribution.
            payload = self.build()
        self.assertEqual(payload['date_field'], 'created_at')
        self.assertEqual(len(payload['volume']), 3)
        self.assertEqual([row['y'] for row in payload['volume']], [3, 0, 1])
        self.assertEqual(payload['missing_dates'], 1)
        self.assertEqual([row['field'] for row in payload['facets']], ['status'])
        self.assertEqual([row['field'] for row in payload['rates']], ['enabled'])
        self.assertEqual([row['y'] for row in payload['rates'][0]['data']], [.5, None, 1.0])
        self.assertIsNone(MagicAdmin(Event, admin.site).date_hierarchy)

    def test_effective_filters_and_related_leaf_fields(self):
        class DynamicAdmin(ExistingAdmin):
            list_filter = ('title',)
            def get_list_filter(self, request):
                return ('company__source', 'company__active', 'status', 'tags__name', 'company', 'title')
        with self.assertNumQueries(4):
            payload = self.build(DynamicAdmin)
        self.assertEqual([chart['field'] for chart in payload['facets']], ['company__source', 'status'])
        self.assertEqual(payload['rates'][0]['field'], 'company__active')
        self.assertIn('Agency', [point['x'] for point in payload['facets'][0]['data']])

    def test_chart_labels_strip_prefix_and_capitalize_without_changing_acronyms(self):
        obj = MagicAdmin(Event, admin.site)
        names = ('chart_has_pro', 'chart_has_pro_plus')
        obj.chart_rate_fields = obj.chart_facet_fields = names
        obj.chart_metrics = {'chart_total': Count('pk')}
        queryset = Event.objects.annotate(**{
            name: models.ExpressionWrapper(models.F('enabled'), output_field=models.BooleanField())
            for name in names
        })
        payload = obj.get_chart_payload(self.request, queryset, total_rows=5)
        for group in ('rates', 'facets'):
            self.assertEqual([chart['label'] for chart in payload[group]], ['Has pro', 'Has pro plus'])
        self.assertEqual(payload['metrics'][0]['label'], 'Total')
        obj.chart_labels = dict(zip(names, (' chart has pro ', 'CHART API usage')))
        obj.chart_labels['chart_total'] = 'chartreuse revenue'
        payload = obj.get_chart_payload(self.request, queryset, total_rows=5)
        for group in ('rates', 'facets'):
            self.assertEqual([chart['label'] for chart in payload[group]], ['Has pro', 'API usage'])
        self.assertEqual(payload['metrics'][0]['label'], 'Chartreuse revenue')

    def test_ambiguous_and_updated_dates_are_not_inferred(self):
        for model in (Ambiguous, Undated):
            model.objects.bulk_create([model(state=True), model(state=False)])
            with self.assertNumQueries(1):
                payload = self.build(model=model, total_rows=2)
            self.assertIsNone(payload['date_field'])
            self.assertFalse(payload['volume'])
            self.assertEqual(payload['facets'][0]['field'], 'state')
        self.assertEqual(MagicAdmin(Dated, admin.site).get_chart_date_field(self.request), 'occurred')

    def test_date_field_and_nullable_history(self):
        Dated.objects.create(occurred=date(2026, 1, 1))
        payload = self.build(model=Dated, total_rows=1, period='hour')
        self.assertEqual(payload['period'], 'day')
        self.assertEqual(payload['volume'][0]['y'], 1)
        Event.objects.update(created_at=None)
        payload = self.build()
        self.assertFalse(payload['volume'])
        self.assertTrue(payload['facets'])

    def test_empty_and_constant_results(self):
        with self.assertNumQueries(0):
            self.assertFalse(self.build(total_rows=0)['volume'])
        Event.objects.update(status='a', enabled=True)
        with self.assertNumQueries(2):
            payload = self.build()
        self.assertFalse(payload['rates'])
        self.assertFalse(payload['facets'])

    def test_explicit_metrics_related_labels_and_top_n(self):
        with self.assertNumQueries(4):
            payload = self.build(ExplicitAdmin)
        self.assertEqual(payload['metrics'][0]['label'], 'Revenue (USD)')
        self.assertEqual(payload['metrics'][0]['data'][0]['y'], Decimal('60'))
        self.assertEqual(payload['metrics'][1]['data'][0]['y'], Decimal('20'))
        self.assertIsNone(payload['metrics'][0]['data'][1]['y'])
        self.assertEqual(len(payload['tops'][0]['data']), 1)
        self.assertTrue(payload['tops'][0]['truncated'])
        self.assertIn('Example', [row['x'] for row in payload['facets'][0]['data']])

    def test_scalar_annotations_and_link_hook(self):
        obj = AnnotatedAdmin(Event, admin.site)
        with self.assertNumQueries(2):
            payload = obj.get_chart_payload(self.request, obj.get_queryset(self.request), total_rows=5)
        self.assertEqual(payload['rates'][0]['field'], 'subscribed')
        self.assertTrue(all(row['url'] is None for row in payload['facets'][0]['data']))
        self.assertEqual(payload['rates'][0]['data'][0]['y'], 2 / 3)

    def test_duplicate_joins_do_not_inflate_any_aggregate(self):
        tags = [Tag.objects.create(name='match one'), Tag.objects.create(name='match two')]
        for event in Event.objects.all():
            event.tags.add(*tags)
        qs = Event.objects.filter(tags__name__contains='match')
        payload = self.build(ExplicitAdmin, queryset=qs)
        self.assertEqual(sum(point['y'] for point in payload['volume']), 4)
        self.assertEqual(payload['metrics'][0]['data'][0]['y'], Decimal('60'))
        self.assertEqual(payload['metrics'][1]['data'][0]['y'], Decimal('20'))
        self.assertEqual(payload['rates'][0]['data'][0]['y'], .5)
        self.assertEqual(sum(row['y'] for row in payload['facets'][0]['data']), 5)

    def test_no_pagination_and_no_extra_count_query(self):
        class PagedAdmin(MagicAdmin):
            list_per_page = 2
        response = PagedAdmin(Event, admin.site).changelist_view(self.request)
        self.assertEqual(len(response.context_data['cl'].result_list), 2)
        self.assertEqual(sum(p['y'] for p in response.context_data['chart_payload']['volume']), 4)
        self.assertEqual(response.context_data['chart_payload']['total_count'], 5)

    def test_filter_search_and_drill_down(self):
        self.request.GET = self.request.GET.copy()
        self.request.GET.update({'q': 'keep', 'p': '3', 'status__exact': 'a'})
        obj = ExistingAdmin(Event, admin.site)
        url = obj.get_chart_link(self.request, 'enabled', True)
        self.assertIn('q=keep', url)
        self.assertIn('status__exact=a', url)
        self.assertNotIn('p=', url)
        self.assertIn('enabled__exact=True', url)
        self.request.GET.pop('p')
        self.request.GET['q'] = ''
        payload = obj.changelist_view(self.request).context_data['chart_payload']
        self.assertEqual(sum(point['y'] for point in payload['volume']), 2)
        self.request.GET = RequestFactory().get('/', {'created_at__year': '2026', 'created_at__month': '1'}).GET
        self.assertEqual(obj._get_chart_period(self.request), 'day')

    def test_sparse_history_coarsens_without_truncation(self):
        Event.objects.all().delete()
        Event.objects.bulk_create([Event(created_at=datetime(year, 1, 1, tzinfo=timezone.utc), status='a')
                                   for year in (1700, 2026)])
        payload = self.build(total_rows=2, period='day')
        self.assertLessEqual(len(payload['volume']), 240)
        self.assertEqual(sum(point['y'] for point in payload['volume']), 2)
        self.assertGreater(payload['year_step'], 1)

    def test_dense_history_has_sql_limit(self):
        Event.objects.all().delete()
        Event.objects.bulk_create([Event(created_at=self.start + timedelta(days=i), status='ab'[i % 2])
                                   for i in range(500)])
        with CaptureQueriesContext(connection) as queries:
            payload = self.build(total_rows=500, period='day')
        self.assertLessEqual(len(payload['volume']), 240)
        self.assertEqual(sum(point['y'] for point in payload['volume']), 500)
        grouped = [q['sql'] for q in queries if '_alc_bucket' in q['sql']]
        self.assertTrue(all('LIMIT 242' in sql for sql in grouped))

    def test_timezone_changes_buckets(self):
        Event.objects.all().delete()
        Event.objects.create(created_at=datetime(2026, 1, 31, 23, tzinfo=timezone.utc), status='a')
        with django_timezone.override('Asia/Bangkok'):
            payload = self.build(total_rows=1)
        self.assertIn('2026-02', payload['volume'][0]['x'])

    def test_cache_isolation(self):
        obj = MagicAdmin(Event, admin.site)
        obj.chart_cache_timeout = 60
        cl = obj.get_changelist_instance(self.request)
        with self.assertNumQueries(2):
            obj._chart_payload(self.request, cl)
        with self.assertNumQueries(0):
            obj._chart_payload(self.request, cl)
        with django_timezone.override('Asia/Bangkok'), self.assertNumQueries(2):
            obj._chart_payload(self.request, cl)
        self.request.user = get_user_model().objects.create_superuser('other', '', 'password')
        with self.assertNumQueries(2):
            obj._chart_payload(self.request, cl)

    def test_lazy_endpoint_permissions_filters_and_search(self):
        url = '/admin/tests/event/chart-data/'
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(url, {'status__exact': 'a'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total_count'], 3)
        page = self.client.get('/admin/tests/event/')
        self.assertIn('chart_endpoint', page.context)
        self.assertNotIn('chart_payload', page.context)
        staff = get_user_model().objects.create_user('staff', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_parent_redirect_returned_unchanged(self):
        class Parent:
            def changelist_view(self, request, extra_context=None):
                return 'redirect'
        class Subject(ListChartMixin, Parent):
            pass
        self.assertEqual(Subject().changelist_view(self.request), 'redirect')

    def test_system_checks(self):
        obj = MagicAdmin(Event, admin.site)
        self.assertFalse(obj.check())
        obj.chart_metrics = {'bad': models.Value(1)}
        obj.chart_auto_max_rate_fields = -1
        self.assertEqual({check.id for check in obj.check()},
                         {'admin_list_charts.E001', 'admin_list_charts.E002'})


    def test_inline_render_uses_json_script_without_facets_switch(self):
        obj = MagicAdmin(Event, admin.site)
        attack = '</script><script>window.compromised=true</script>'
        obj.chart_labels = {'status': attack}
        response = obj.changelist_view(self.request)
        response.render()
        html = response.content.decode()
        self.assertIn('type="application/json"', html)
        self.assertNotIn('View chart data', html)
        self.assertLess(html.index('class="alc"'), html.index('id="changelist"'))
        self.assertNotIn(attack, html)
        self.assertIn('\\u003C/script\\u003E', html)
        self.assertTrue(response.context_data['chart_payload']['facets'])

    def test_only_mixin_overhead_reuses_changelist_counts(self):
        with CaptureQueriesContext(connection) as base_queries:
            admin.ModelAdmin(Event, admin.site).changelist_view(self.request)
        with CaptureQueriesContext(connection) as chart_queries:
            MagicAdmin(Event, admin.site).changelist_view(self.request)
        self.assertEqual(len(chart_queries) - len(base_queries), 2)
        with patch('django.db.models.query.QuerySet.count', side_effect=AssertionError('Extra count query')):
            self.assertTrue(self.build(total_rows=None)['volume'])

    def test_facets_do_not_change_chart_markup_or_aggregation(self):
        obj = MagicAdmin(Event, admin.site)
        obj.list_filter = ('status',)
        for policy, params in (
            (admin.ShowFacets.ALLOW, {}),
            (admin.ShowFacets.ALLOW, {'_facets': 'True'}),
            (admin.ShowFacets.ALWAYS, {}),
            (admin.ShowFacets.NEVER, {'_facets': 'True'}),
        ):
            with self.subTest(policy=policy, params=params):
                obj.show_facets = policy
                self.request.GET = RequestFactory().get('/', params).GET
                cl = obj.get_changelist_instance(self.request)
                with self.assertNumQueries(2):
                    payload = obj._chart_payload(self.request, cl)
                self.assertEqual(sum(point['y'] for point in payload['volume']), 4)
                self.assertEqual(payload['facets'][0]['field'], 'status')
                response = obj.changelist_view(self.request)
                response.render()
                html = response.content.decode()
                self.assertNotIn('data-expanded', html)
                self.assertIn('data-more-label="More charts"', html)

    def test_custom_filter_needs_explicit_link_hook(self):
        class StatusFilter(admin.SimpleListFilter):
            title = 'State'
            parameter_name = 'status'
            def lookups(self, request, model_admin):
                return [('a', 'A')]
            def queryset(self, request, queryset):
                return queryset
        obj = MagicAdmin(Event, admin.site)
        obj.list_filter = (StatusFilter,)
        self.assertIsNone(obj.get_chart_link(self.request, 'status', 'a'))
        obj = AnnotatedAdmin(Event, admin.site)
        with patch.object(obj, 'get_chart_field', return_value=models.BooleanField()):
            self.assertIsNone(obj.get_chart_link(self.request, 'subscribed', True))

    def test_metrics_cannot_introduce_multivalued_joins(self):
        obj = MagicAdmin(Event, admin.site)
        obj.chart_metrics = {'bad': models.Count('tags__name')}
        self.assertIn('admin_list_charts.E003', {check.id for check in obj.check()})
        payload = obj.get_chart_payload(self.request, Event.objects.all(), total_rows=5)
        self.assertFalse(payload['metrics'])
        self.assertEqual(sum(row['y'] for row in payload['volume']), 4)

    def test_custom_queryset_and_date_hook(self):
        class CustomAdmin(MagicAdmin):
            def get_chart_queryset(self, request, changelist):
                return super().get_chart_queryset(request, changelist).filter(enabled=True)
            def get_chart_date_field(self, request):
                return 'created_at'
        response = CustomAdmin(Event, admin.site).changelist_view(self.request)
        self.assertEqual(sum(row['y'] for row in response.context_data['chart_payload']['volume']), 2)
        self.assertEqual(response.context_data['chart_payload']['missing_dates'], 0)
        self.assertEqual(response.context_data['chart_payload']['total_count'], 2)

    def test_caching_language_and_configuration_isolation(self):
        from django.utils import translation
        obj = MagicAdmin(Event, admin.site)
        obj.chart_cache_timeout = 60
        cl = obj.get_changelist_instance(self.request)
        obj._chart_payload(self.request, cl)
        with translation.override('de'), self.assertNumQueries(2):
            obj._chart_payload(self.request, cl)
        obj.chart_labels = {'status': 'State'}
        with self.assertNumQueries(2):
            self.assertEqual(obj._chart_payload(self.request, cl)['facets'][0]['label'], 'State')


    def test_caching_empty_custom_queryset(self):
        class EmptyAdmin(MagicAdmin):
            chart_cache_timeout = 60
            def get_chart_queryset(self, request, changelist):
                return changelist.queryset.none()
        obj = EmptyAdmin(Event, admin.site)
        cl = obj.get_changelist_instance(self.request)
        with self.assertNumQueries(0):
            self.assertFalse(obj._chart_payload(self.request, cl)['volume'])

    def test_asset_and_payload_budgets(self):
        bundle = Path(__file__).resolve().parent.parent / 'admin_list_charts/static/admin_list_charts/js/chart.bundle.min.js'
        self.assertLess(len(gzip.compress(bundle.read_bytes(), mtime=0)), 70658)
        payload = self.build()
        from django.core.serializers.json import DjangoJSONEncoder
        self.assertLess(len(json.dumps(payload, cls=DjangoJSONEncoder).encode()), 10000)


    def test_single_valued_reverse_relation_labels_and_leaf(self):
        CompanyProfile.objects.create(company=self.company, name='Company profile', verified=True)
        obj = MagicAdmin(Event, admin.site)
        obj.chart_top_fields = (('company__profile', 6),)
        obj.chart_rate_fields = ('company__profile__verified',)
        payload = obj.get_chart_payload(self.request, Event.objects.all(), total_rows=5)
        self.assertIn('Company profile', [point['x'] for point in payload['tops'][0]['data']])
        self.assertEqual(payload['rates'], [])  # Only known values are true, so suppress the constant rate.


    def test_filter_aliases_are_preserved_and_can_be_selected(self):
        obj = MagicAdmin(Event, admin.site)
        queryset = Event.objects.alias(subscribed=Exists(
            Company.objects.filter(pk=OuterRef('company_id'), active=True)))
        # Filtering via an unselected alias must not break unrelated charts.
        payload = obj.get_chart_payload(self.request, queryset.filter(subscribed=True), total_rows=2)
        self.assertEqual(sum(point['y'] for point in payload['volume']), 2)
        obj.chart_rate_fields = ('subscribed',)
        payload = obj.get_chart_payload(self.request, queryset, total_rows=5)
        self.assertEqual(payload['rates'][0]['data'][0]['y'], 2 / 3)

    def test_count_metrics_resolve_primary_key_aliases_and_filtered_counts(self):
        obj = MagicAdmin(Event, admin.site)
        obj.chart_metrics = {'records': Count('pk'), 'active': Count('pk', filter=Q(enabled=True)),
                             'companies': Count('company__pk')}
        with self.assertNumQueries(2):
            payload = obj.get_chart_payload(self.request, Event.objects.all(), total_rows=5)
        self.assertEqual([metric['data'][0]['y'] for metric in payload['metrics']], [3, 1, 3])
        self.assertEqual([metric['data'][1]['y'] for metric in payload['metrics']], [0, 0, 0])

    def test_hourly_buckets_across_daylight_saving_transitions(self):
        cases = (
            ([datetime(2026, 3, 8, hour, 30, tzinfo=timezone.utc) for hour in range(5, 9)], [1, 1, 1, 1]),
            ([datetime(2026, 11, 1, hour, 30, tzinfo=timezone.utc) for hour in range(4, 9)], [1, 2, 1, 1]),
        )
        for values, expected in cases:
            with self.subTest(values=values), django_timezone.override(ZoneInfo('America/New_York')):
                Event.objects.all().delete()
                Event.objects.bulk_create([Event(created_at=value) for value in values])
                payload = self.build(total_rows=len(values), period='hour')
                self.assertEqual([point['y'] for point in payload['volume']], expected)
                instants = [datetime.fromisoformat(point['x']).astimezone(timezone.utc) for point in payload['volume']]
                self.assertEqual(len(instants), len(set(instants)))
                self.assertEqual(sum(point['y'] for point in payload['volume']), len(values))

    def test_hourly_buckets_in_fractional_offset_timezone(self):
        Event.objects.all().delete()
        Event.objects.create(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        with django_timezone.override(ZoneInfo('Asia/Kathmandu')):
            payload = self.build(total_rows=1, period='hour')
        self.assertTrue(payload['volume'][0]['x'].endswith('05:00:00+05:45'))

    @override_settings(USE_TZ=False)
    def test_naive_datetimes_and_metric_nulls(self):
        Event.objects.all().delete()
        Event.objects.bulk_create([Event(created_at=datetime(2026, 1, day), amount=None) for day in (1, 3)])
        obj = MagicAdmin(Event, admin.site)
        obj.chart_metrics = {'amount': Sum('amount'), 'count': Count('pk')}
        payload = obj.get_chart_payload(self.request, Event.objects.all(), period='day', total_rows=2)
        self.assertEqual([point['y'] for point in payload['volume']], [1, 0, 1])
        self.assertEqual([point['y'] for point in payload['metrics'][0]['data']], [None, None, None])
        self.assertEqual([point['y'] for point in payload['metrics'][1]['data']], [1, 0, 1])

    def test_all_automatic_charts_can_be_disabled_without_queries(self):
        obj = MagicAdmin(Event, admin.site)
        obj.chart_auto_select = False
        with self.assertNumQueries(0):
            payload = obj.get_chart_payload(self.request, Event.objects.all(), total_rows=5)
        self.assertFalse(any(payload[key] for key in ('volume', 'rates', 'facets', 'tops', 'metrics')))

    def test_automatic_limits_zero_leave_only_volume(self):
        obj = MagicAdmin(Event, admin.site)
        obj.chart_auto_max_facet_fields = obj.chart_auto_max_rate_fields = 0
        with self.assertNumQueries(1):
            payload = obj.get_chart_payload(self.request, Event.objects.all(), total_rows=5)
        self.assertTrue(payload['volume'])
        self.assertFalse(payload['rates'])
        self.assertFalse(payload['facets'])

    def test_explicit_top_n_is_bounded(self):
        Event.objects.all().delete()
        Event.objects.bulk_create([Event(title=f'Category {index:03}') for index in range(105)])
        obj = MagicAdmin(Event, admin.site)
        obj.chart_auto_select = False
        obj.chart_top_fields = (('title', 1000), ('company', 2))
        with self.assertNumQueries(2):
            payload = obj.get_chart_payload(self.request, Event.objects.all(), total_rows=105)
        self.assertEqual(len(payload['tops'][0]['data']), 100)
        self.assertTrue(payload['tops'][0]['truncated'])

    def test_timeline_links_respect_both_range_lookup_permissions(self):
        obj = MagicAdmin(Event, admin.site)
        obj.lookup_allowed = lambda lookup, value, request: not lookup.endswith('__lt')
        self.assertIsNone(obj.get_chart_link(self.request, 'created_at', self.start, self.start + timedelta(days=1)))

    def test_invalid_lazy_filters_return_a_private_client_error(self):
        self.client.force_login(self.user)
        response = self.client.get('/admin/tests/event/chart-data/', {'not_a_field': 'value'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('private', response.headers['Cache-Control'])
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_lazy_endpoint_allows_view_permission_and_rejects_post(self):
        from django.contrib.auth.models import Permission
        viewer = get_user_model().objects.create_user('viewer', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_event'))
        self.client.force_login(viewer)
        url = '/admin/tests/event/chart-data/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 405)
        head = self.client.head(url)
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b'')

    def test_nullable_boolean_distribution_links_distinguish_unknown_values(self):
        obj = MagicAdmin(Event, admin.site)
        obj.chart_auto_select = False
        obj.chart_facet_fields = ('enabled',)
        with self.assertNumQueries(1):
            payload = obj.get_chart_payload(self.request, Event.objects.all(), total_rows=5)
        values = {point['x']: point for point in payload['facets'][0]['data']}
        self.assertEqual({label: point['y'] for label, point in values.items()}, {'Yes': 2, 'No': 2, '(empty)': 1})
        self.assertIn('enabled__isnull=True', values['(empty)']['url'])
        self.assertIn('enabled__exact=False', values['No']['url'])

    def test_extreme_history_preserves_counts_without_overflowing_final_link(self):
        Dated.objects.bulk_create([Dated(occurred=date(year, 1, 1)) for year in (1600, 9999)])
        payload = self.build(model=Dated, total_rows=2, period='year')
        self.assertLessEqual(len(payload['volume']), 240)
        self.assertEqual(sum(point['y'] for point in payload['volume']), 2)
        self.assertIsNone(payload['volume'][-1]['url'])
        self.assertTrue(payload['volume'][-1]['label'].endswith('9999'))

    def test_palette_defaults_and_sanitized_colors(self):
        obj = MagicAdmin(Event, admin.site)
        for config in (None, [], {'palette': []}):
            with self.subTest(config=config), override_settings(ADMIN_LIST_CHARTS=config):
                self.assertEqual(obj.get_chart_palette(self.request), {})
        with override_settings(ADMIN_LIST_CHARTS={'palette': {'accent': ' #123456 ', 'series': ['', 12, ' rebeccapurple ']}}):
            self.assertEqual(obj.get_chart_palette(self.request), {'accent': '#123456', 'series': ['rebeccapurple']})


class DatabaseRoutingTests(TestCase):
    databases = {'default', 'charts'}

    def test_aggregates_and_related_labels_use_queryset_database(self):
        company = Company.objects.using('charts').create(name='Routed company', active=True, source='a')
        Event.objects.using('charts').create(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                                           company=company, status='a', enabled=True)
        obj = ExplicitAdmin(Event, admin.site)
        request = RequestFactory().get('/')
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(4, using='charts'):
            payload = obj.get_chart_payload(request, Event.objects.using('charts').all(), total_rows=1)
        self.assertEqual(payload['facets'][0]['data'][0]['x'], 'Routed company')

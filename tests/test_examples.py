from io import StringIO

from django.contrib import admin
from django.core.management import call_command
from django.test import RequestFactory, TestCase

from commerce.models import Order
from demo.models import Visit
from memberships.models import Account
from publishing.models import Job


class ExampleTests(TestCase):
    def test_repeatable_seed_and_all_mixin_only_admins(self):
        def seed():
            call_command('seed_demo', reset=True, preset='small', seed=42,
                         reference_date='2026-10-01', stdout=StringIO())
        seed()
        original = list(Order.objects.order_by('created_at', 'amount').values_list(
            'created_at', 'status', 'paid', 'amount'))
        seed()
        self.assertEqual(original, list(Order.objects.order_by('created_at', 'amount').values_list(
            'created_at', 'status', 'paid', 'amount')))
        request = RequestFactory().get('/')
        for model, name in ((Visit, 'created_at'), (Order, 'created_at'),
                            (Account, 'date_joined'), (Job, 'published_at')):
            with self.subTest(model=model):
                obj = admin.site.get_model_admin(model)
                self.assertIsNone(obj.date_hierarchy)
                count = model.objects.count()
                payload = obj.get_chart_payload(request, model.objects.all(), total_rows=count, facets_on=True)
                self.assertEqual(payload['date_field'], name)
                self.assertTrue(payload['volume'])
                self.assertTrue(payload['facets'])
                self.assertLessEqual(len(payload['facets']), 3)
                self.assertLessEqual(len(payload['rates']), 2)
                self.assertEqual(sum(point['y'] for point in payload['volume']) + payload['missing_dates'], count)

"""Measure synthetic chart overhead in an isolated Django test database."""
import argparse
import gzip
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')

import django

django.setup()
from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext, setup_databases, teardown_databases

from admin_list_charts.admin import ListChartMixin
from tests.models import Event


class Example(ListChartMixin, admin.ModelAdmin):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', type=int, nargs='+', default=[10000, 100000, 1000000])
    parser.add_argument('--output', default='.cache/benchmarks/sqlite.json')
    args = parser.parse_args()
    databases = setup_databases(verbosity=0, interactive=False)
    result = {'python': platform.python_version(), 'django': django.get_version(),
              'database': connection.vendor, 'platform': platform.platform(),
              'repeats': 3, 'measurements': []}
    try:
        request = RequestFactory().get('/admin/tests/event/')
        obj = Example(Event, admin.site)
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for size in args.sizes:
            Event.objects.all().delete()
            for offset in range(0, size, 5000):
                Event.objects.bulk_create([
                    Event(created_at=base + timedelta(days=i % 180), status='ab'[i % 2],
                          enabled=bool(i % 3), verified=bool(i % 5))
                    for i in range(offset, min(offset + 5000, size))
                ], batch_size=1000)
            durations = []
            for _ in range(3):
                with CaptureQueriesContext(connection) as queries:
                    started = time.perf_counter()
                    payload = obj.get_chart_payload(request, Event.objects.all(), total_rows=size)
                    durations.append((time.perf_counter() - started) * 1000)
            measurement = {'rows': size, 'chart_queries': len(queries),
                           'aggregation_rows': len(payload['volume']) + sum(len(chart['data']) for chart in payload['facets']),
                           'payload_bytes': len(json.dumps(payload, cls=DjangoJSONEncoder).encode()),
                           'median_ms': round(statistics.median(durations), 2),
                           'runs_ms': [round(value, 2) for value in durations]}
            print(json.dumps(measurement), flush=True)
            result['measurements'].append(measurement)
        bundle = ROOT / 'admin_list_charts/static/admin_list_charts/js/chart.bundle.min.js'
        result['asset_gzip_bytes'] = len(gzip.compress(bundle.read_bytes(), mtime=0))
        output = ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + '\n')
    finally:
        teardown_databases(databases, verbosity=0)


if __name__ == '__main__':
    main()

"""Measure synthetic chart overhead in an isolated Django test database."""
import argparse
import gzip
import importlib.util
import json
import os
import platform
import statistics
import subprocess
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
    parser.add_argument('--compare-04', action='store_true', help='Compare source from commit fadd278 on identical data.')
    parser.add_argument('--output', default='.cache/benchmarks/sqlite.json')
    args = parser.parse_args()
    implementations = [('0.5.1', Example)]
    if args.compare_04:
        baseline = ROOT / '.cache/benchmarks/admin_04.py'
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_bytes(subprocess.check_output(['git', 'show', 'fadd278:admin_list_charts/admin.py'], cwd=ROOT))
        spec = importlib.util.spec_from_file_location('dalc_admin_04', baseline)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        previous = type('Previous', (module.ListChartMixin, admin.ModelAdmin), {'date_hierarchy': 'created_at'})
        implementations.insert(0, ('0.4:fadd278', previous))
    databases = setup_databases(verbosity=0, interactive=False)
    result = {'python': platform.python_version(), 'django': django.get_version(),
              'database': connection.vendor, 'platform': platform.platform(),
              'repeats': 3, 'measurements': []}
    try:
        request = RequestFactory().get('/admin/tests/event/')
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for size in args.sizes:
            if connection.vendor == 'postgresql':
                # Seed large isolated datasets in SQL rather than constructing
                # millions of Python objects. Never touch the configured DB.
                with connection.cursor() as cursor:
                    cursor.execute('TRUNCATE tests_event CASCADE')
                    cursor.execute("""
                        INSERT INTO tests_event
                            (created_at, status, enabled, verified, title)
                        SELECT %s::timestamptz + (i %% 180) * interval '1 day',
                               CASE WHEN i %% 2 = 0 THEN 'a' ELSE 'b' END,
                               i %% 3 <> 0, i %% 5 <> 0, ''
                        FROM generate_series(0, %s - 1) AS i
                    """, [base, size])
                    cursor.execute('ANALYZE tests_event')
            else:
                Event.objects.all().delete()
                for offset in range(0, size, 5000):
                    Event.objects.bulk_create([
                        Event(created_at=base + timedelta(days=i % 180), status='ab'[i % 2],
                              enabled=bool(i % 3), verified=bool(i % 5))
                        for i in range(offset, min(offset + 5000, size))
                    ], batch_size=1000)
            print(f'Seeded {size} rows.', flush=True)
            # Alternate implementations on the same dataset; record all runs
            # rather than concealing warm/cold cache effects in one duration.
            runs = {(version, counts): [] for version, _ in implementations for counts in (False, True)}
            measurements = {}
            for repeat in range(3):
                for version, implementation in (implementations if repeat % 2 == 0 else implementations[::-1]):
                    obj = implementation(Event, admin.site)
                    for counts in (False, True):
                        with CaptureQueriesContext(connection) as queries:
                            started = time.perf_counter()
                            payload = obj.get_chart_payload(request, Event.objects.all(), period='month',
                                                            facets_on=counts, total_rows=size)
                            runs[version, counts].append((time.perf_counter() - started) * 1000)
                        measurements[version, counts] = {
                            'version': version, 'rows': size, 'counts': counts,
                            'chart_queries': len(queries),
                            'sql': [query['sql'] for query in queries],
                            'payload_bytes': len(json.dumps(payload, cls=DjangoJSONEncoder).encode()),
                        }
            for key, measurement in measurements.items():
                measurement.update(median_ms=round(statistics.median(runs[key]), 2),
                                   runs_ms=[round(value, 2) for value in runs[key]])
                print(json.dumps({key: value for key, value in measurement.items() if key != 'sql'}), flush=True)
                result['measurements'].append(measurement)
            output = ROOT / args.output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2) + '\n')
        bundle = ROOT / 'admin_list_charts/static/admin_list_charts/js/chart.bundle.min.js'
        result['asset_gzip_bytes'] = len(gzip.compress(bundle.read_bytes(), mtime=0))
        output = ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + '\n')
    finally:
        teardown_databases(databases, verbosity=0)


if __name__ == '__main__':
    main()

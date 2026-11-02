"""Verify release archives and install each artifact in a clean environment."""
import os
import runpy
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = runpy.run_path(ROOT / 'admin_list_charts/__init__.py')['__version__']
DIST = f'django_admin_list_charts-{VERSION}'
REQUIRED = {
    'admin_list_charts/__init__.py', 'admin_list_charts/apps.py',
    'admin_list_charts/admin.py', 'admin_list_charts/charts.py',
    'admin_list_charts/templates/admin_list_charts/change_list_with_chart.html',
    'admin_list_charts/static/admin_list_charts/js/chart.bundle.min.js',
    'admin_list_charts/static/admin_list_charts/css/charts.css',
    'admin_list_charts/static/admin_list_charts/CHARTJS-LICENSE.txt',
}
SMOKE = '''
from importlib.metadata import version
from importlib.resources import files
from types import SimpleNamespace
import sys
from admin_list_charts import __version__
assert version('django-admin-list-charts') == __version__ == sys.argv[1]
from django.conf import settings
settings.configure(SECRET_KEY='package-smoke', ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'],
    INSTALLED_APPS=['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
                   'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'admin_list_charts'],
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
    STATIC_URL='/static/', USE_TZ=True,
    TEMPLATES=[{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True}])
import django
django.setup()
from django.contrib import admin
from django.contrib.staticfiles import finders
from django.db import connection, models
from django.test import RequestFactory
from django.urls import path
from django.utils import timezone
from admin_list_charts.admin import ListChartMixin
class Entry(models.Model):
    created_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=1, choices=[('a', 'Active'), ('b', 'Blocked')])
    class Meta:
        app_label = 'admin_list_charts'
class EntryAdmin(ListChartMixin, admin.ModelAdmin):
    pass
admin.site.register(Entry, EntryAdmin)
urlpatterns = [path('admin/', admin.site.urls)]
with connection.schema_editor() as editor:
    editor.create_model(Entry)
Entry.objects.bulk_create([Entry(created_at=timezone.now(), status='a'), Entry(status='b')])
request = RequestFactory().get('/admin/admin_list_charts/entry/')
request.user = SimpleNamespace(is_active=True, is_staff=True, is_superuser=True,
    has_perm=lambda *args: True, has_module_perms=lambda *args: True)
request.session = {}
response = admin.site.get_model_admin(Entry).changelist_view(request)
response.render()
assert response.status_code == 200
assert response.context_data['chart_payload']['missing_dates'] == 1
assert b'admin-list-charts-data' in response.content
for asset in ('css/charts.css', 'js/chart.bundle.min.js', 'CHARTJS-LICENSE.txt'):
    assert files('admin_list_charts').joinpath('static/admin_list_charts/' + asset).is_file()
    assert finders.find('admin_list_charts/' + asset)
print('Installed package renders an admin changelist and resolves its static assets.')
'''


def main():
    wheel = ROOT / 'dist' / f'{DIST}-py3-none-any.whl'
    sdist = ROOT / 'dist' / f'{DIST}.tar.gz'
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert REQUIRED <= names, 'Wheel assets missing'
        assert all(name.startswith(('admin_list_charts/', DIST + '.dist-info/')) for name in names), 'Development files in wheel'
        for name in REQUIRED:
            assert archive.read(name) == (ROOT / name).read_bytes(), f'Stale wheel content: {name}'
        metadata = Parser().parsestr(archive.read(DIST + '.dist-info/METADATA').decode())
        assert metadata['Version'] == VERSION
        assert '(docs/' not in metadata.get_payload(), 'Relative documentation links in package description'
    with tarfile.open(sdist) as archive:
        members = {member.name.split('/', 1)[-1]: member for member in archive.getmembers()}
        assert REQUIRED <= members.keys(), 'Source assets missing'
        assert {'frontend/charts.js', 'package.json', 'package-lock.json', 'tests/test_admin.py'} <= members.keys()
        assert not any(name.startswith('docs/') and name.endswith('.json') for name in members), 'Diagnostic JSON in source archive'
        for name in (*REQUIRED, 'README.md', 'tests/browser/charts.spec.js'):
            assert archive.extractfile(members[name]).read() == (ROOT / name).read_bytes(), f'Stale source content: {name}'
    with tempfile.TemporaryDirectory(prefix='dalc-package-') as temporary:
        for artifact in (wheel, sdist):
            env = Path(temporary) / ('wheel' if artifact == wheel else 'source')
            venv.EnvBuilder(with_pip=True).create(env)
            python = env / 'bin' / 'python'
            if requirement := os.environ.get('DJANGO_REQUIREMENT'):
                subprocess.run([str(python), '-m', 'pip', 'install', requirement], check=True, cwd=temporary)
            subprocess.run([str(python), '-m', 'pip', 'install', str(artifact)], check=True, cwd=temporary)
            subprocess.run([str(python), '-m', 'pip', 'check'], check=True, cwd=temporary)
            subprocess.run([str(python), '-c', SMOKE, VERSION], check=True, cwd=temporary)
    print(f'{VERSION} wheel and source distribution verified.')


if __name__ == '__main__':
    main()

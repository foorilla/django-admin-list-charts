"""Start an isolated, repeatable admin for browser tests and gallery captures."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.browser_settings'

import django

django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command

path = Path(settings.DATABASES['default']['NAME'])
path.parent.mkdir(exist_ok=True)
path.unlink(missing_ok=True)
call_command('migrate', interactive=False, verbosity=0)
call_command('seed_demo', reset=True, preset='small', seed=42, reference_date='2026-10-01', verbosity=0)
get_user_model().objects.create_superuser('demo', 'demo@example.com', 'demo')
call_command('runserver', '127.0.0.1:8765', use_reloader=False)

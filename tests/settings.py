import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'example_project'))
from example_project.settings import *  # noqa: F403

SECRET_KEY = 'test-only-key'
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
INSTALLED_APPS = [*INSTALLED_APPS, 'tests']
ROOT_URLCONF = 'tests.urls'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
if os.environ.get('TEST_POSTGRES'):
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('PGDATABASE', 'dalc_tests'),
        'USER': os.environ.get('PGUSER', ''),
        'HOST': os.environ.get('PGHOST', ''),
        'PORT': os.environ.get('PGPORT', ''),
        'PASSWORD': os.environ.get('PGPASSWORD', ''),
    }
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DATABASES['charts'] = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}

from tests.settings import *  # noqa: F403

INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'tests']
ROOT_URLCONF = 'example_project.urls'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
                         'NAME': Path(__file__).resolve().parent.parent / '.cache' / 'browser.sqlite3'}}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {'django.server': {'handlers': [], 'level': 'ERROR', 'propagate': False}},
}

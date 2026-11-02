# Compatibility

| Python | Django |
| --- | --- |
| 3.12, 3.13, 3.14 | 5.2 LTS, 6.0, 6.1 |
| 3.15 | 6.1.3 onward; provisional until upstream release |

The matrix follows [Django's supported release schedule](https://www.djangoproject.com/download/) and [Python compatibility table](https://docs.djangoproject.com/en/dev/faq/install/#what-python-version-can-i-use-with-django). Django 5.0 and 5.1 have ended upstream support and are excluded from the 0.5 dependency range. Django 5.2 remains supported as an LTS.

Python 3.15 uses a conditional `Django>=6.1.3,<6.2` dependency. Python 3.15 installation requires Django 6.1.3, scheduled for [November 3, 2026](https://docs.djangoproject.com/en/dev/releases/6.1.3/); support remains provisional until that release. To develop against the Django maintenance branch:

```bash
python -m pip install https://github.com/django/django/archive/refs/heads/stable/6.1.x.zip
python -m pip install -e .
```

CI covers supported Python/Django combinations with SQLite, representative PostgreSQL combinations, package installation, and browser scenarios. The upcoming-Django job is advisory and does not expand the supported range.

Stock Django admin, SQLite and PostgreSQL are supported. Other admin skins and database backends are outside the support matrix. There are no required Redis, Celery, reporting models, or package migrations.

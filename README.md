# django-admin-list-charts

Super simple charts for Django admin changelist pages, driven by `date_hierarchy` and bundled with Chart.js.

It is built to be a drop-in enhancement: install, mix in `ListChartMixin`, and your admin list gets a compact timeline chart. When Django's facet counts are enabled, it also renders a dense sidebar of categorical distributions.

## Requirements

- `Python>=3.12,<3.15`
- `Django>=5,<7`

## Installation

```bash
pip install django-admin-list-charts
```

Add the app:

```python
INSTALLED_APPS = [
    # ...
    'admin_list_charts',
]
```

## Quick Start (60 seconds)

```python
from django.contrib import admin
from admin_list_charts.admin import ListChartMixin

from .models import Order


@admin.register(Order)
class OrderAdmin(ListChartMixin, admin.ModelAdmin):
    date_hierarchy = 'created_at'
    list_filter = ('status', 'source', 'is_paid', 'is_returning')
```

That is enough to get:

- a main timeline chart on changelist pages
- automatic facet sidebar charts when Django facet counts are enabled (`_facets`)

## How Facet Mode Works

When Django admin "Show counts" / facets are active:

- Main chart stays focused on timeline volume, with optional boolean rate overlays.
- Right sidebar is filled with compact absolute distributions for facet fields.
- Sidebar uses compact horizontal bar charts (no pie/donut) for better readability in limited space.
- Auto-selection is intentionally permissive so available `list_filter` choices are shown whenever there is data.

## Optional Tuning

You can explicitly control what gets charted.

```python
@admin.register(Order)
class OrderAdmin(ListChartMixin, admin.ModelAdmin):
    date_hierarchy = 'created_at'
    list_filter = ('status', 'source', 'channel', 'is_paid', 'is_returning')

    # Optional explicit picks (if omitted, auto-selection is used)
    chart_facet_fields = ('status', 'source', 'channel')
    chart_rate_fields = ('is_paid', 'is_returning')

    # Optional limits
    chart_facet_max_series = 6
    chart_auto_max_facet_fields = 4
    chart_auto_max_rate_fields = 3
```

### Config Reference

- `chart_facet_fields`: categorical/choice-like fields for facet charts
- `chart_rate_fields`: boolean fields to render as percentage overlays in main chart
- `chart_top_fields`: optional top-N charts (`[(field_name, limit), ...]`)
- `chart_facet_max_series`: max series per facet field (top-N values)
- `chart_auto_select`: default `True`; enables auto-field detection when explicit tuples are empty
- `chart_auto_max_facet_fields`: default `4`
- `chart_auto_max_rate_fields`: default `3`

## Theme / Palette (optional)

```python
ADMIN_LIST_CHARTS = {
    'palette': {
        'accent': '#1f5fa6',
        'series': [
            '#1f5fa6',
            '#2f9e44',
            '#d6336c',
            '#0c8599',
            '#e67700',
            '#6b7280',
        ],
    },
}
```

- `palette.accent`: primary bar/accent color
- `palette.series`: ordered series colors

If omitted, colors are derived from Django admin CSS variables.

## Agent-Friendly Integration Notes

If you are delegating setup to a coding agent, ask it to do exactly this:

1. Install package: `pip install django-admin-list-charts`
2. Add `'admin_list_charts'` to `INSTALLED_APPS`
3. For each admin class that needs charts:
   - mix in `ListChartMixin`
   - ensure `date_hierarchy` is set
   - keep meaningful `list_filter` fields for facet mode
4. Run migrations and start server
5. Verify in Django admin changelist:
   - base timeline appears
   - enabling facets shows sidebar distribution charts

This package is intentionally configuration-light, so most projects work with only those steps.

## Local Reference Project

This repository includes `example_project/` for manual testing.

```bash
python -m pip install -e .
python example_project/manage.py migrate
python example_project/manage.py createsuperuser
python example_project/manage.py seed_visits --truncate --days 180 --min-per-day 120 --max-per-day 450
python example_project/manage.py runserver
```

Then open `http://127.0.0.1:8000/admin/` and inspect the `Visits` changelist.

## Examples

![Example 1: Django admin list charts with bright theme](https://github.com/foorilla/django-admin-list-charts/raw/main/django-admin-list-charts_example_1_bright_screen.png)

![Example 2: Django admin list charts with dark theme](https://github.com/foorilla/django-admin-list-charts/raw/main/django-admin-list-charts_example_2_dark_screen.png)

## Acknowledgements

Inspired by Dani Hodovic's article on adding charts to Django admin:
https://findwork.dev/blog/adding-charts-to-django-admin/

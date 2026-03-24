# django-admin-list-charts
Super simple bar charts for django admin list views visualizing the number of objects based on date_hierarchy using Chart.js.

This package serves as a ready-made drop-in solution with Chart.js included.
This way you can super-charge your django admin with date-based bar charts in less than a minute :)

## Examples

![Example 1: Django admin list charts on with bright theme](https://github.com/foorilla/django-admin-list-charts/raw/main/django-admin-list-charts_example_1_bright_screen.png)

![Example 1: Django admin list charts on with dark theme](https://github.com/foorilla/django-admin-list-charts/raw/main/django-admin-list-charts_example_2_dark_screen.png)

## Requirements

* `Python>=3.12,<3.15`
* `Django>=5,<7`

## Compatibility update

This release updates package metadata for modern supported runtimes and is intended for Django 5.x-6.x projects running on Python 3.12-3.14.

## Installation

1. Install Django admin list charts from PyPI by using `pip`:

	`pip install django-admin-list-charts`

2. Add `'admin_list_charts'` entry to Django `INSTALLED_APPS` setting.

3. Sprinkle some `ListChartMixin` over every admin class where you want to display charts in the admin list view. For example:

```	
    ...
    from admin_list_charts.admin import ListChartMixin
    
    @admin.register(Foo)
    class FooAdmin(ListChartMixin, admin.ModelAdmin):
	    date_hierarchy = 'created'
	    ...
```

4. Done!

## Facets-enabled chart mode

When Django admin `Show counts` (`_facets`) is enabled in the changelist filters, the chart view switches to a denser mode:

- main mixed chart: volume bars + boolean rate overlays
- compact right context rail: selected facet composition and quick stats

This mode is designed to work with little or no extra config.

### Zero-config (recommended)

If your model has:

- one date field used by `date_hierarchy`
- a few `choices` fields
- a few boolean fields

the mixin auto-selects the most informative fields for overlays when facets are on.

### Optional tuning

You can still explicitly tune what appears:

```python
from django.contrib import admin
from admin_list_charts.admin import ListChartMixin


@admin.register(MyModel)
class MyModelAdmin(ListChartMixin, admin.ModelAdmin):
    date_hierarchy = 'created_at'
    list_filter = ('status', 'category', 'is_active', 'is_flagged')

    # Optional explicit field picks (override auto-selection)
    chart_facet_fields = ('status', 'category')
    chart_rate_fields = ('is_active', 'is_flagged')

    # Optional caps (used by auto-selection too)
    chart_facet_max_series = 6
    chart_auto_max_facet_fields = 2
    chart_auto_max_rate_fields = 3
```

### Configuration reference

- `chart_facet_fields`: tuple of categorical/choices fields to visualize in context charts
- `chart_rate_fields`: tuple of boolean fields to overlay as percentage trend lines
- `chart_facet_max_series`: max values per categorical field shown in charts (top-N)
- `chart_auto_select`: `True` by default; enables automatic field selection when explicit tuples are empty
- `chart_auto_max_facet_fields`: max auto-selected categorical fields (default: `2`)
- `chart_auto_max_rate_fields`: max auto-selected boolean fields (default: `3`)

### Global chart palette (settings.py)

You can define a global chart palette in Django settings to blend with your admin theme:

```python
ADMIN_LIST_CHARTS = {
    "palette": {
        "accent": "#1f5fa6",
        "series": [
            "#1f5fa6",
            "#2f9e44",
            "#d6336c",
            "#0c8599",
            "#9c36b5",
            "#e67700",
        ],
    }
}
```

- `palette.accent`: main bar color and primary chart accent
- `palette.series`: line/context series colors, in order

If omitted, colors are derived from Django admin CSS variables.

### Practical notes

- Keep `list_filter` meaningful; facet mode follows the currently filtered changelist queryset.
- If your model has many candidate fields, start with auto mode, then pin explicit fields for stable output.
- For best readability, keep boolean overlay fields to 2-3 and categorical fields to 1-2.

## Local reference project

This repository includes a tiny Django project at `example_project/` for manual testing while developing this package.

The demo app used by this project lives in `example_project/demo/` and exists for local testing purposes. It is not part of the reusable `admin_list_charts` package API.

1. Install this package in editable mode:

   `python -m pip install -e .`

2. Run migrations in the example project:

   `python example_project/manage.py migrate`

3. Create an admin user:

   `python example_project/manage.py createsuperuser`

4. Seed chartable demo data (high-volume, multi-facet):

   `python example_project/manage.py seed_visits --truncate --days 180 --min-per-day 120 --max-per-day 450`

5. Start the server and open admin:

   `python example_project/manage.py runserver`

Then browse to `http://127.0.0.1:8000/admin/` and open `Visits` to verify list charts and filter combinations.

When `Show counts` (`_facets`) is enabled in the changelist sidebar, additional high-density charts are rendered. By default, the mixin auto-selects the most informative choice and boolean fields, so this works with little or no per-admin configuration in most cases.

## Acknowledgements

This rather pragmatic solution was heavily inspired by the work of Dani Hodovic (see [https://findwork.dev/blog/adding-charts-to-django-admin/](https://findwork.dev/blog/adding-charts-to-django-admin/)).

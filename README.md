# django-admin-list-charts
Super simple bar charts for django admin list views visualizing the number of objects based on date_hierarchy using Chart.js.

This package serves as a ready-made drop-in solution with Chart.js included.
This way you can super-charge your django admin with date-based bar charts in less than a minute :)

## Examples

![Example 1: Django admin list charts on with bright theme](https://github.com/foorilla/django-admin-list-charts/raw/main/django-admin-list-charts_example_1_bright_screen.png)

![Example 1: Django admin list charts on with dark theme](https://github.com/foorilla/django-admin-list-charts/raw/main/django-admin-list-charts_example_2_dark_screen.png)

## Requirements

* `Django>=3.0`

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

## Acknowledgements

This rather pragmatic solution was heavily inspired by the work of Dani Hodovic (see [https://findwork.dev/blog/adding-charts-to-django-admin/](https://findwork.dev/blog/adding-charts-to-django-admin/)).

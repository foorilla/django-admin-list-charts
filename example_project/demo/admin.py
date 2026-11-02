from django.contrib import admin

from admin_list_charts.admin import ListChartMixin

from .models import Visit, VisitExplorer


@admin.register(Visit)
class VisitAdmin(ListChartMixin, admin.ModelAdmin):
    pass


@admin.register(VisitExplorer)
class VisitExplorerAdmin(ListChartMixin, admin.ModelAdmin):
    date_hierarchy = 'created_at'
    list_display = (
        'path',
        'source',
        'channel',
        'device_type',
        'is_authenticated',
        'is_returning',
        'is_conversion',
        'created_at',
    )
    list_filter = (
        'source',
        'channel',
        'device_type',
        'is_authenticated',
        'is_returning',
        'is_conversion',
    )
    search_fields = ('path', 'source')

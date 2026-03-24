from django.contrib import admin

from admin_list_charts.admin import ListChartMixin

from .models import Visit


@admin.register(Visit)
class VisitAdmin(ListChartMixin, admin.ModelAdmin):
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

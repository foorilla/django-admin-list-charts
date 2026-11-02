from django.contrib import admin

from admin_list_charts.admin import ListChartMixin

from .models import Job, JobExplorer


@admin.register(Job)
class JobAdmin(ListChartMixin, admin.ModelAdmin):
    pass


@admin.register(JobExplorer)
class JobExplorerAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('title', 'company', 'published_at', 'status', 'remote')
    list_filter = ('company__source', 'company__active', 'status', 'remote')
    search_fields = ('title', 'tags__name')

from django.contrib import admin

from admin_list_charts.admin import ListChartMixin

from .models import Order, OrderMetrics


@admin.register(Order)
class OrderAdmin(ListChartMixin, admin.ModelAdmin):
    pass


@admin.register(OrderMetrics)
class OrderMetricsAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('id', 'created_at', 'status', 'channel', 'amount')
    list_filter = ('status', 'channel', 'paid')

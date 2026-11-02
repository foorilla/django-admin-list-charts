from django.contrib import admin
from django.db.models import Avg, Sum

from admin_list_charts.admin import ListChartMixin

from .models import Order, OrderMetrics


@admin.register(Order)
class OrderAdmin(ListChartMixin, admin.ModelAdmin):
    pass


@admin.register(OrderMetrics)
class OrderMetricsAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('id', 'created_at', 'status', 'channel', 'amount')
    list_filter = ('status', 'channel', 'paid')
    chart_metrics = {'revenue': Sum('amount'), 'average_order': Avg('amount')}
    chart_labels = {'revenue': 'Revenue (USD)', 'average_order': 'Average order (USD)'}

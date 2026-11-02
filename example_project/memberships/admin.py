from django.contrib import admin
from django.db.models import BooleanField, Exists, OuterRef

from admin_list_charts.admin import ListChartMixin

from .models import Account, AccountSubscriptions, Subscription


@admin.register(Account)
class AccountAdmin(ListChartMixin, admin.ModelAdmin):
    pass


@admin.register(AccountSubscriptions)
class AccountSubscriptionsAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('name', 'date_joined', 'tier', 'active')
    list_filter = ('tier', 'active')
    chart_rate_fields = ('subscribed', 'active')
    chart_labels = {'subscribed': 'Current subscription'}
    chart_lazy = True

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(subscribed=Exists(
            Subscription.objects.filter(account_id=OuterRef('pk'), current=True)))

    def get_chart_field(self, request, queryset, name):
        if name == 'subscribed':
            return BooleanField()
        return super().get_chart_field(request, queryset, name)

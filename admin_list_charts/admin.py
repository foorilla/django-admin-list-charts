import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, DateTimeField
from django.db.models.functions import Trunc


class ListChartMixin(object):
    change_list_template = 'admin_list_charts/change_list_with_chart.html'
    
    def _get_chart_period(self, request):
        if self.date_hierarchy + '__day' in request.GET:
            return 'hour'
        if self.date_hierarchy + '__month' in request.GET:
            return 'day'
        if self.date_hierarchy + '__year' in request.GET:
            return 'week'
        return 'month'
    
    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(
            request, extra_context=extra_context)
        
        if hasattr(self, 'date_hierarchy'):
            try:
                qs = response.context_data['cl'].queryset
            except (AttributeError, KeyError):
                return response
            
            period = self._get_chart_period(request)
            data = qs.annotate(
                x=Trunc(
                    self.date_hierarchy,
                    period,
                    output_field=DateTimeField()
                )
            ).values('x').annotate(y=Count('pk')).order_by('y')
            
            response.context_data['chart_data'] = json.dumps(
                list(data), cls=DjangoJSONEncoder)
            
            response.context_data['chart_period'] = period
        
        return response

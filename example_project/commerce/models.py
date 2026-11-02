from django.db import models
from django.utils import timezone


class Order(models.Model):
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=20, choices=[('new', 'New'), ('paid', 'Paid'), ('sent', 'Shipped'), ('cancel', 'Cancelled')])
    channel = models.CharField(max_length=20, choices=[('web', 'Website'), ('app', 'Mobile app'), ('retail', 'Retail')])
    paid = models.BooleanField(default=False)
    returned = models.BooleanField(default=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f'Order #{self.pk}'


class OrderMetrics(Order):
    class Meta:
        proxy = True
        verbose_name_plural = 'Orders — filters'

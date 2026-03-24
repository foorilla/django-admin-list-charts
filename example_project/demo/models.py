from django.db import models
from django.utils import timezone


class Visit(models.Model):
    CHANNEL_ORGANIC = 'organic'
    CHANNEL_PAID = 'paid'
    CHANNEL_REFERRAL = 'referral'
    CHANNEL_NEWSLETTER = 'newsletter'
    CHANNEL_DIRECT = 'direct'
    CHANNEL_CHOICES = (
        (CHANNEL_ORGANIC, 'Organic'),
        (CHANNEL_PAID, 'Paid'),
        (CHANNEL_REFERRAL, 'Referral'),
        (CHANNEL_NEWSLETTER, 'Newsletter'),
        (CHANNEL_DIRECT, 'Direct'),
    )

    DEVICE_DESKTOP = 'desktop'
    DEVICE_MOBILE = 'mobile'
    DEVICE_TABLET = 'tablet'
    DEVICE_CHOICES = (
        (DEVICE_DESKTOP, 'Desktop'),
        (DEVICE_MOBILE, 'Mobile'),
        (DEVICE_TABLET, 'Tablet'),
    )

    path = models.CharField(max_length=200)
    source = models.CharField(max_length=50, blank=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_DIRECT, db_index=True)
    device_type = models.CharField(max_length=20, choices=DEVICE_CHOICES, default=DEVICE_DESKTOP, db_index=True)
    is_authenticated = models.BooleanField(default=False)
    is_returning = models.BooleanField(default=False)
    is_conversion = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.path} ({self.created_at.isoformat()})'

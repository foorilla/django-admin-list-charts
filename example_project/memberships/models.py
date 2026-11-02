from django.db import models
from django.utils import timezone


class Account(models.Model):
    name = models.CharField(max_length=100)
    date_joined = models.DateTimeField(default=timezone.now, db_index=True)
    tier = models.CharField(max_length=20, choices=[('free', 'Free'), ('pro', 'Professional'), ('team', 'Team')])
    active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    current = models.BooleanField(default=True)


class AccountSubscriptions(Account):
    class Meta:
        proxy = True
        verbose_name_plural = 'Accounts — annotated subscriptions (lazy)'

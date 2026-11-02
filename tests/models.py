from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=100)
    active = models.BooleanField(null=True)
    source = models.CharField(max_length=20, choices=[('a', 'Agency'), ('d', 'Direct')])

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=40)


class Event(models.Model):
    created_at = models.DateTimeField(null=True)
    updated_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, choices=[('a', 'Active'), ('b', 'Blocked')])
    enabled = models.BooleanField(null=True)
    verified = models.BooleanField(default=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    title = models.CharField(max_length=100, blank=True)
    company = models.ForeignKey(Company, null=True, on_delete=models.SET_NULL)
    tags = models.ManyToManyField(Tag)

    class Meta:
        ordering = ['-created_at']


class Ambiguous(models.Model):
    starts = models.DateField(null=True)
    ends = models.DateField(null=True)
    updated_at = models.DateField(null=True)
    state = models.BooleanField(default=False)


class Undated(models.Model):
    updated_at = models.DateTimeField(null=True)
    state = models.BooleanField(default=False)


class Dated(models.Model):
    occurred = models.DateField(null=True)


class CompanyProfile(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='profile')
    name = models.CharField(max_length=40)
    verified = models.BooleanField(default=False)

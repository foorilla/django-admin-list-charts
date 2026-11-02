from django.db import models
from django.utils import timezone


class Company(models.Model):
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    source = models.CharField(max_length=20, choices=[('direct', 'Direct'), ('agency', 'Agency'), ('partner', 'Partner')])

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=40)

    def __str__(self):
        return self.name


class Job(models.Model):
    title = models.CharField(max_length=100)
    published_at = models.DateTimeField(default=timezone.now, db_index=True, null=True)
    status = models.CharField(max_length=20, choices=[('draft', 'Draft'), ('live', 'Live'), ('closed', 'Closed')])
    remote = models.BooleanField(default=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag)

    def __str__(self):
        return self.title


class JobExplorer(Job):
    class Meta:
        proxy = True
        verbose_name_plural = 'Jobs — related filters and search'

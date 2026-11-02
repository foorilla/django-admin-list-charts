import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from commerce.models import Order
from memberships.models import Account, Subscription
from publishing.models import Company, Job, Tag


class Command(BaseCommand):
    help = 'Generate deterministic synthetic examples; never reads an external database.'

    def add_arguments(self, parser):
        parser.add_argument('--preset', choices=('small', '10000', '100000', '1000000'), default='small')
        parser.add_argument('--seed', type=int, default=42)
        parser.add_argument('--reference-date', default='2026-10-01')
        parser.add_argument('--reset', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        count = 600 if options['preset'] == 'small' else int(options['preset'])
        rng = random.Random(options['seed'])
        try:
            reference = timezone.make_aware(datetime.fromisoformat(options['reference_date']))
        except ValueError as error:
            raise CommandError('--reference-date must be an ISO date without a timezone.') from error
        if options['reset']:
            for model in (Subscription, Account, Order, Job, Company, Tag):
                model.objects.all().delete()
        companies = [Company.objects.create(name=name, active=index != 3,
                                            source=('direct', 'agency', 'partner')[index % 3])
                     for index, name in enumerate(('Acorn Studio', 'Beacon Labs', 'Cedar Works', 'Dawn Systems', 'Elm & Co.', 'Fern Group', 'Grove'))]
        tags = [Tag.objects.create(name=name) for name in ('python backend', 'python remote', 'design')]
        for offset in range(0, count, 1000):
            orders, accounts, jobs = [], [], []
            for index in range(offset, min(count, offset + 1000)):
                created = reference - timedelta(days=rng.randrange(180), hours=rng.randrange(24))
                status = rng.choices(('new', 'paid', 'sent', 'cancel'), (12, 28, 52, 8))[0]
                orders.append(Order(created_at=created, status=status,
                                    channel=rng.choices(('web', 'app', 'retail'), (55, 35, 10))[0],
                                    paid=status in ('paid', 'sent'), returned=rng.random() < .06,
                                    amount=Decimal(rng.randrange(500, 50000)) / 100))
                accounts.append(Account(name=f'Account {index + 1:06}', date_joined=created,
                                        tier=rng.choices(('free', 'pro', 'team'), (65, 27, 8))[0],
                                        active=rng.random() < .83, verified=rng.random() < .62))
                jobs.append(Job(title=f'{("Engineer", "Designer", "Analyst")[index % 3]} {index + 1}',
                                published_at=None if index % 29 == 0 else created - timedelta(days=index % 5 * 130),
                                status=rng.choices(('draft', 'live', 'closed'), (12, 58, 30))[0],
                                remote=rng.random() < .55, company=companies[index % len(companies)]))
            Order.objects.bulk_create(orders, batch_size=1000)
            Account.objects.bulk_create(accounts, batch_size=1000)
            Subscription.objects.bulk_create([Subscription(account=account, current=index % 4 != 0)
                                               for index, account in enumerate(accounts) if index % 3], batch_size=1000)
            Job.objects.bulk_create(jobs, batch_size=1000)
            through = Job.tags.through
            through.objects.bulk_create([through(job_id=job.pk, tag_id=tag.pk)
                                         for job in jobs for tag in tags[:2]], batch_size=1000)
        call_command('seed_visits', truncate=options['reset'], days=180,
                     min_per_day=4 if count == 600 else max(1, count // 180),
                     max_per_day=12 if count == 600 else max(1, count // 180),
                     seed=options['seed'], reference_date=options['reference_date'], stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS(f'Created {count} orders, accounts, and jobs.'))

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from demo.models import Visit


class Command(BaseCommand):
    help = 'Seed demo Visit rows spread across the last N days.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=180, help='How many days of data to generate.')
        parser.add_argument(
            '--min-per-day',
            type=int,
            default=120,
            help='Minimum number of records per day.',
        )
        parser.add_argument(
            '--max-per-day',
            type=int,
            default=450,
            help='Maximum number of records per day.',
        )
        parser.add_argument(
            '--truncate',
            action='store_true',
            help='Delete existing Visit rows before seeding.',
        )

    @staticmethod
    def _weighted_choice(options):
        values = [option[0] for option in options]
        weights = [option[1] for option in options]
        return random.choices(values, weights=weights, k=1)[0]

    def handle(self, *args, **options):
        days = max(1, options['days'])
        min_per_day = max(1, options['min_per_day'])
        max_per_day = max(1, options['max_per_day'])
        if min_per_day > max_per_day:
            min_per_day, max_per_day = max_per_day, min_per_day

        if options['truncate']:
            Visit.objects.all().delete()

        base_time = timezone.now()

        paths = [
            '/jobs/',
            '/jobs/software-engineer/',
            '/jobs/product-manager/',
            '/companies/',
            '/about/',
            '/pricing/',
            '/signup/',
            '/blog/how-to-hire-faster/',
            '/blog/remote-interview-guide/',
        ]
        sources = [
            ('direct', 34),
            ('search', 28),
            ('newsletter', 12),
            ('referral', 16),
            ('social', 10),
        ]
        channels = [
            (Visit.CHANNEL_ORGANIC, 32),
            (Visit.CHANNEL_PAID, 22),
            (Visit.CHANNEL_REFERRAL, 16),
            (Visit.CHANNEL_NEWSLETTER, 10),
            (Visit.CHANNEL_DIRECT, 20),
        ]
        devices = [
            (Visit.DEVICE_MOBILE, 55),
            (Visit.DEVICE_DESKTOP, 38),
            (Visit.DEVICE_TABLET, 7),
        ]

        visits = []
        total_rows = 0
        for day_offset in range(days):
            day_start = (base_time - timedelta(days=day_offset)).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

            baseline = random.randint(min_per_day, max_per_day)
            weekday = day_start.weekday()
            if weekday in (5, 6):
                baseline = max(min_per_day, int(baseline * random.uniform(0.6, 0.85)))
            elif weekday in (1, 2):
                baseline = min(max_per_day, int(baseline * random.uniform(1.1, 1.35)))

            if random.random() < 0.06:
                baseline = int(baseline * random.uniform(1.8, 2.8))

            count = max(1, baseline)
            for _ in range(count):
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                source = self._weighted_choice(sources)
                channel = self._weighted_choice(channels)
                device_type = self._weighted_choice(devices)

                is_authenticated = random.random() < 0.44
                is_returning = random.random() < (0.62 if is_authenticated else 0.27)
                conversion_bias = 0.015
                if is_authenticated:
                    conversion_bias += 0.03
                if is_returning:
                    conversion_bias += 0.02
                if channel == Visit.CHANNEL_PAID:
                    conversion_bias += 0.012
                if source == 'newsletter':
                    conversion_bias += 0.02
                is_conversion = random.random() < conversion_bias

                visits.append(
                    Visit(
                        path=random.choice(paths),
                        source=source,
                        channel=channel,
                        device_type=device_type,
                        is_authenticated=is_authenticated,
                        is_returning=is_returning,
                        is_conversion=is_conversion,
                        created_at=day_start + timedelta(hours=hour, minutes=minute),
                    )
                )

            if len(visits) >= 5000:
                Visit.objects.bulk_create(visits, batch_size=1000)
                total_rows += len(visits)
                visits = []

        if visits:
            Visit.objects.bulk_create(visits, batch_size=1000)
            total_rows += len(visits)

        self.stdout.write(self.style.SUCCESS(f'Created {total_rows} Visit rows.'))

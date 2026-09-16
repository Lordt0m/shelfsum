from django.core.management.base import BaseCommand, CommandError

from core.demo import (
    DEMO_BUSINESS_NAME,
    DEMO_OWNER_EMAIL,
    DEMO_OWNER_PASSWORD,
    DEMO_STAFF_EMAIL,
    DEMO_STAFF_PASSWORD,
    DemoSeedError,
    seed_demo_business,
)


class Command(BaseCommand):
    help = "Create or verify the deterministic fictional ShelfSum Demo Business."

    def handle(self, *args, **options):
        try:
            seed_demo_business()
        except DemoSeedError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS(f"{DEMO_BUSINESS_NAME} is ready (read-only)."))
        self.stdout.write(f"Owner: {DEMO_OWNER_EMAIL} / {DEMO_OWNER_PASSWORD}")
        self.stdout.write(f"Staff Member: {DEMO_STAFF_EMAIL} / {DEMO_STAFF_PASSWORD}")

from django.core.management.base import BaseCommand, CommandError

from core.demo import (
    DEMO_BUSINESS_NAME,
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
        self.stdout.write("Use the landing page for the published fictional Demo credentials.")

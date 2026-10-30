import shutil

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Remove generated watermarked image files."

    def handle(self, *args, **options):
        shutil.rmtree(settings.PRIVATE_STORAGE_DIR / "watermarked", ignore_errors=True)
        self.stdout.write(self.style.SUCCESS("Watermarked image cache cleared."))

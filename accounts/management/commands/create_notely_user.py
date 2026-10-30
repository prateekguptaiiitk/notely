from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from accounts.admin import generate_access_code


class Command(BaseCommand):
    help = "Create a Notely viewer and print a one-time access code."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        username = options["username"]
        if User.objects.filter(username=username).exists():
            raise CommandError("Username already exists")
        code = generate_access_code()
        User.objects.create_user(username=username, password=code, is_active=True)
        self.stdout.write(f"Username: {username}\nAccess code (shown once): {code}")

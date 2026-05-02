"""
Initial setup: branches, categories, locations, optional superuser.

Usage:
    python manage.py setup_initial_data
"""

import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Branch, Category, Location, UserProfile


class Command(BaseCommand):
    help = 'Set up initial data for the Asset Distribution System'

    def handle(self, *args, **options):
        self.stdout.write('Setting up initial data...')

        # Branches
        self.stdout.write('Creating branches...')
        branches = [
            ('A', 'Lynn', 1),
            ('B', 'Richard', 2),
            ('C', 'Rob', 3),
        ]
        branch_lookup = {}
        for code, name, order in branches:
            branch, _ = Branch.objects.get_or_create(
                code=code,
                defaults={'name': name, 'display_order': order},
            )
            branch_lookup[code] = branch

        # Categories
        self.stdout.write('Creating categories...')
        categories = [
            ('Jewelry', 1), ('Furniture', 2), ('Artwork', 3), ('Collectibles', 4),
            ('WWII Memorabilia', 5), ('China/Dishware', 6), ('Tools', 7),
            ('Electronics', 8), ('Books', 9), ('Clothing/Accessories', 10),
            ('Kitchenware', 11), ('Linens', 12), ('Outdoor/Garden', 13),
            ('Miscellaneous', 14),
        ]
        for name, order in categories:
            Category.objects.get_or_create(
                name=name,
                defaults={'display_order': order},
            )

        # Locations
        self.stdout.write('Creating locations...')
        locations = [
            ('Unspecified', 0), ('Kitchen', 1), ('Dining Room', 2), ('Living Room', 3),
            ('Family Room', 4), ('Bedroom', 5), ('Primary Bedroom', 6), ('Office', 7),
            ('Bathroom', 8), ('Laundry Room', 9), ('Garage', 10), ('Basement', 11),
            ('Attic', 12), ('Entryway', 13), ('Patio/Outdoor', 14), ('Storage', 15),
            ('Miscellaneous', 16),
        ]
        for name, order in locations:
            Location.objects.get_or_create(
                name=name,
                defaults={'display_order': order},
            )

        # Optional superuser from environment
        admin_username = os.environ.get('ASSET_ADMIN_USERNAME')
        admin_password = os.environ.get('ASSET_ADMIN_PASSWORD')
        admin_email = os.environ.get('ASSET_ADMIN_EMAIL', '')
        admin_branch_code = os.environ.get('ASSET_ADMIN_BRANCH', 'A')

        if admin_username and admin_password:
            user, created = User.objects.get_or_create(
                username=admin_username,
                defaults={'email': admin_email, 'is_staff': True, 'is_superuser': True},
            )
            if created:
                user.set_password(admin_password)
                user.save()
                branch = branch_lookup.get(admin_branch_code, branch_lookup['A'])
                UserProfile.objects.get_or_create(user=user, defaults={'branch': branch})
                self.stdout.write(self.style.SUCCESS(f'✓ Created admin user "{admin_username}".'))
            else:
                self.stdout.write(f'Admin user "{admin_username}" already exists; left untouched.')
        else:
            self.stdout.write(
                'No admin credentials in env (ASSET_ADMIN_USERNAME / ASSET_ADMIN_PASSWORD). '
                'Create one with: python manage.py createsuperuser'
            )

        self.stdout.write(self.style.SUCCESS('✓ Initial data setup complete!'))

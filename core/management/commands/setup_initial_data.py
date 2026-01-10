"""
Management command to initialize the database with family members, categories, and passwords.
Run with: python manage.py setup_initial_data
"""

import os
import hashlib

from django.core.management.base import BaseCommand
from core.models import Branch, FamilyMember, Category, SystemSettings, DistributionState


class Command(BaseCommand):
    help = 'Set up initial data for the Asset Distribution System'

    def handle(self, *args, **options):
        self.stdout.write('Setting up initial data...')
        
        # Create Branches
        self.stdout.write('Creating branches...')
        branch_a, _ = Branch.objects.get_or_create(
            code='A',
            defaults={'name': 'Branch A (Lynn)', 'display_order': 1}
        )
        branch_b, _ = Branch.objects.get_or_create(
            code='B',
            defaults={'name': 'Branch B (Richard)', 'display_order': 2}
        )
        branch_c, _ = Branch.objects.get_or_create(
            code='C',
            defaults={'name': 'Branch C (Rob)', 'display_order': 3}
        )
        
        # Create Family Members - Branch A
        self.stdout.write('Creating family members for Branch A...')
        branch_a_members = [
            ('Lynn', True, 0),
            ('Crystal', False, 1),
            ('April', False, 2),
            ('Rachel', False, 3),
            ('Jack', False, 4),
            ('Bonnie', False, 5),
            ('Eric', False, 6),
        ]
        for name, is_father, order in branch_a_members:
            FamilyMember.objects.get_or_create(
                name=name,
                branch=branch_a,
                defaults={'is_father': is_father, 'display_order': order}
            )
        
        # Create Family Members - Branch B
        self.stdout.write('Creating family members for Branch B...')
        branch_b_members = [
            ('Richard', True, 0),
            ('Shannon', False, 1),
            ('David', False, 2),
            ('Elise', False, 3),
            ('Jonathan', False, 4),
            ('Christiana', False, 5),
            ('Darren', False, 6),
        ]
        for name, is_father, order in branch_b_members:
            FamilyMember.objects.get_or_create(
                name=name,
                branch=branch_b,
                defaults={'is_father': is_father, 'display_order': order}
            )
        
        # Create Family Members - Branch C (no father, just Brian and Michael)
        self.stdout.write('Creating family members for Branch C...')
        branch_c_members = [
            ('Brian', False, 0),
            ('Michael', False, 1),
        ]
        for name, is_father, order in branch_c_members:
            FamilyMember.objects.get_or_create(
                name=name,
                branch=branch_c,
                defaults={'is_father': is_father, 'display_order': order}
            )
        
        # Create Categories
        self.stdout.write('Creating categories...')
        categories = [
            ('Jewelry', 1),
            ('Furniture', 2),
            ('Artwork', 3),
            ('Collectibles', 4),
            ('WWII Memorabilia', 5),
            ('China/Dishware', 6),
            ('Tools', 7),
            ('Electronics', 8),
            ('Books', 9),
            ('Clothing/Accessories', 10),
            ('Kitchenware', 11),
            ('Linens', 12),
            ('Outdoor/Garden', 13),
            ('Miscellaneous', 14),
        ]
        for name, order in categories:
            Category.objects.get_or_create(
                name=name,
                defaults={'display_order': order}
            )
        
        # Set default passwords from environment variables
        self.stdout.write('Setting default passwords...')
        
        family_password = os.environ.get('ASSET_FAMILY_PASSWORD', 'changeme')
        family_hash = hashlib.sha256(family_password.encode()).hexdigest()
        SystemSettings.objects.update_or_create(
            key='family_password_hash',
            defaults={'value': family_hash}
        )
        
        admin_password = os.environ.get('ASSET_ADMIN_PASSWORD', 'changeme')
        admin_hash = hashlib.sha256(admin_password.encode()).hexdigest()
        SystemSettings.objects.update_or_create(
            key='admin_password_hash',
            defaults={'value': admin_hash}
        )
        
        # Create initial distribution state
        self.stdout.write('Creating distribution state...')
        DistributionState.objects.get_or_create(pk=1)
        
        self.stdout.write(self.style.SUCCESS('✓ Initial data setup complete!'))
        self.stdout.write('')
        self.stdout.write('Passwords set from environment variables:')
        self.stdout.write('  ASSET_FAMILY_PASSWORD: ' + ('(set)' if os.environ.get('ASSET_FAMILY_PASSWORD') else '(using default "changeme")'))
        self.stdout.write('  ASSET_ADMIN_PASSWORD:  ' + ('(set)' if os.environ.get('ASSET_ADMIN_PASSWORD') else '(using default "changeme")'))
        self.stdout.write('')
        if not os.environ.get('ASSET_FAMILY_PASSWORD') or not os.environ.get('ASSET_ADMIN_PASSWORD'):
            self.stdout.write(self.style.WARNING('⚠ Set environment variables before running in production!'))

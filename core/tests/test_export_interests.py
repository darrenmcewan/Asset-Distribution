"""Tests for the interests CSV export."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Asset, Branch, Category, Interest, Location, UserProfile


class ExportInterestsCsvTests(TestCase):
    """Tests for admin_export_interests_csv_view."""

    def setUp(self):
        self.branch = Branch.objects.create(name='TestBranch', code='T', display_order=99)
        self.category = Category.objects.create(name='Test Furniture', display_order=99)
        self.location = Location.objects.create(name='Test Room', display_order=99)
        self.asset = Asset.objects.create(name='Oak Table', category=self.category, location=self.location)

        self.admin = User.objects.create_user('admin', email='admin@example.com', password='pw12345!')
        self.admin.is_staff = True
        self.admin.save()
        UserProfile.objects.create(user=self.admin, branch=self.branch)

        self.user = User.objects.create_user('alice', email='alice@example.com', password='pw12345!')
        UserProfile.objects.create(user=self.user, branch=self.branch)

    def test_successful_export_with_correct_columns(self):
        """3.1: CSV has correct headers and data."""
        Interest.objects.create(user=self.user, asset=self.asset, position=1)
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('admin_export_interests_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        content = resp.content.decode()
        lines = content.strip().split('\r\n')
        self.assertEqual(lines[0], 'User Name,Email,Branch,Item #,Asset,Interest Ranking')
        self.assertIn('alice', lines[1])
        self.assertIn('alice@example.com', lines[1])
        self.assertIn('TestBranch', lines[1])
        self.assertIn(self.asset.serial_number, lines[1])
        self.assertIn('Oak Table', lines[1])
        self.assertIn('1', lines[1])

    def test_user_without_profile_branch_empty(self):
        """3.2: Branch column is empty when user has no profile."""
        user_no_profile = User.objects.create_user('bob', email='bob@example.com', password='pw12345!')
        # Delete profile if auto-created, or just don't create one
        UserProfile.objects.filter(user=user_no_profile).delete()
        Interest.objects.create(user=user_no_profile, asset=self.asset, position=1)
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('admin_export_interests_csv'))
        content = resp.content.decode()
        lines = content.strip().split('\r\n')
        # Find the line for bob
        bob_line = [l for l in lines if 'bob' in l][0]
        # Branch should be empty (bob,bob@example.com,,JBM-...)
        parts = bob_line.split(',')
        self.assertEqual(parts[2], '')  # branch column empty

    def test_non_admin_access_denied(self):
        """3.3: Non-admin users cannot access the export."""
        self.client.force_login(self.user)
        resp = self.client.get(reverse('admin_export_interests_csv'))
        # Should redirect to login
        self.assertNotEqual(resp.status_code, 200)
        self.assertIn(resp.status_code, [302, 403])

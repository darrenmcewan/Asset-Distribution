"""Tests for the assign-other-user feature (admin assign modal shows all users)."""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Asset, Branch, Category, Interest, Location, UserProfile


class AdminAssignOtherUserTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='TestBranch', code='T', display_order=1)
        self.staff = User.objects.create_user(username='admin', password='pw12345!', is_staff=True)
        UserProfile.objects.create(user=self.staff, branch=self.branch)
        self.user_a = User.objects.create_user(username='alice', password='pw12345!')
        UserProfile.objects.create(user=self.user_a, branch=self.branch)
        self.user_b = User.objects.create_user(username='bob', password='pw12345!')
        UserProfile.objects.create(user=self.user_b, branch=self.branch)
        self.category, _ = Category.objects.get_or_create(name='Furniture')
        self.location, _ = Location.objects.get_or_create(name='Office')
        self.asset = Asset.objects.create(
            name='Desk', category=self.category, location=self.location
        )

    def _get_admin_assets_page(self):
        self.client.force_login(self.staff)
        return self.client.get(reverse('admin_assets'))

    def test_all_users_json_present_in_context(self):
        """The admin assets page includes all_users_json with all active users."""
        resp = self._get_admin_assets_page()
        self.assertEqual(resp.status_code, 200)
        self.assertIn('all_users_json', resp.context)
        all_users = json.loads(resp.context['all_users_json'])
        usernames = [u['username'] for u in all_users]
        self.assertIn('alice', usernames)
        self.assertIn('bob', usernames)
        self.assertIn('admin', usernames)

    def test_all_users_json_rendered_in_template(self):
        """The template renders allUsers JS variable."""
        resp = self._get_admin_assets_page()
        self.assertContains(resp, 'var allUsers =')

    def test_asset_with_interests_includes_other_option_data(self):
        """When an asset has interests, the JS data supports showing 'Other'."""
        Interest.objects.create(user=self.user_a, asset=self.asset, position=1)
        resp = self._get_admin_assets_page()
        # Verify interest data and all_users_json are both present
        self.assertContains(resp, 'var assetInterests =')
        self.assertContains(resp, 'var allUsers =')
        interests_data = json.loads(resp.context['asset_interests_json'])
        self.assertIn(str(self.asset.id), interests_data)

    def test_asset_no_interests_all_users_available(self):
        """When no interests, all_users_json still available for direct selection."""
        resp = self._get_admin_assets_page()
        interests_data = json.loads(resp.context['asset_interests_json'])
        # No interests for this asset
        self.assertNotIn(str(self.asset.id), interests_data)
        # But all users are available
        all_users = json.loads(resp.context['all_users_json'])
        self.assertTrue(len(all_users) >= 3)

    def test_assign_non_interested_user_succeeds(self):
        """Assigning to a user who hasn't expressed interest works (backend accepts any user)."""
        self.client.force_login(self.staff)
        resp = self.client.post(reverse('admin_direct_assign'), {
            'asset_id': self.asset.id,
            'user_id': self.user_b.id,
        })
        self.assertEqual(resp.status_code, 302)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.assigned_to, self.user_b)
        self.assertEqual(self.asset.status, 'claimed')

    def test_all_users_sorted_alphabetically(self):
        """The all_users_json list is sorted alphabetically by username."""
        resp = self._get_admin_assets_page()
        all_users = json.loads(resp.context['all_users_json'])
        usernames = [u['username'] for u in all_users]
        self.assertEqual(usernames, sorted(usernames))

    def test_inactive_users_excluded_from_all_users(self):
        """Inactive users should not appear in all_users_json."""
        inactive = User.objects.create_user(username='inactive', password='pw12345!', is_active=False)
        UserProfile.objects.create(user=inactive, branch=self.branch)
        resp = self._get_admin_assets_page()
        all_users = json.loads(resp.context['all_users_json'])
        usernames = [u['username'] for u in all_users]
        self.assertNotIn('inactive', usernames)

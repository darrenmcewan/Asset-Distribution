"""Tests for column sorting on browse and admin assets pages."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Asset, Branch, Category, Location, UserProfile


def _setup(self):
    """Create shared fixtures for sort tests."""
    self.branch = Branch.objects.create(name='Branch', code='B', display_order=1)
    self.cat_a = Category.objects.create(name='Alpha Cat', display_order=1)
    self.cat_b = Category.objects.create(name='Beta Cat', display_order=2)
    self.loc_x = Location.objects.create(name='X-Ray Loc', display_order=1)
    self.loc_y = Location.objects.create(name='Yankee Loc', display_order=2)

    self.asset1 = Asset.objects.create(name='Charlie', category=self.cat_a, location=self.loc_y)
    self.asset2 = Asset.objects.create(name='Alpha', category=self.cat_b, location=self.loc_x)
    self.asset3 = Asset.objects.create(name='Bravo', category=self.cat_a, location=self.loc_x)


class SortValidationTests(TestCase):
    """Task 6.1: whitelist enforcement, invalid values ignored."""

    def setUp(self):
        _setup(self)
        self.user = User.objects.create_user('tester', password='pw12345!')
        UserProfile.objects.create(user=self.user, branch=self.branch)
        self.client.force_login(self.user)

    def test_invalid_sort_key_ignored(self):
        resp = self.client.get(reverse('browse_assets'), {'sort': 'evil', 'dir': 'asc'})
        self.assertEqual(resp.status_code, 200)
        # context should have None for current_sort
        self.assertIsNone(resp.context['current_sort'])

    def test_invalid_dir_ignored(self):
        resp = self.client.get(reverse('browse_assets'), {'sort': 'name', 'dir': 'drop_table'})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context['current_sort'])

    def test_sort_without_dir_ignored(self):
        resp = self.client.get(reverse('browse_assets'), {'sort': 'name'})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context['current_sort'])

    def test_valid_sort_accepted(self):
        resp = self.client.get(reverse('browse_assets'), {'sort': 'name', 'dir': 'asc'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['current_sort'], 'name')
        self.assertEqual(resp.context['current_dir'], 'asc')

    def test_raw_field_name_rejected(self):
        """sort=pk should be rejected (must use 'item')."""
        resp = self.client.get(reverse('browse_assets'), {'sort': 'pk', 'dir': 'asc'})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context['current_sort'])


class BrowseOrderingTests(TestCase):
    """Task 6.2: correct ordering on browse page."""

    def setUp(self):
        _setup(self)
        self.user = User.objects.create_user('tester', password='pw12345!')
        UserProfile.objects.create(user=self.user, branch=self.branch)
        self.client.force_login(self.user)

    def _asset_names(self, resp):
        return [a.name for a in resp.context['assets']]

    def test_sort_name_asc(self):
        resp = self.client.get(reverse('browse_assets'), {'sort': 'name', 'dir': 'asc', 'status': 'all'})
        self.assertEqual(self._asset_names(resp), ['Alpha', 'Bravo', 'Charlie'])

    def test_sort_name_desc(self):
        resp = self.client.get(reverse('browse_assets'), {'sort': 'name', 'dir': 'desc', 'status': 'all'})
        self.assertEqual(self._asset_names(resp), ['Charlie', 'Bravo', 'Alpha'])

    def test_sort_item_asc(self):
        resp = self.client.get(reverse('browse_assets'), {'sort': 'item', 'dir': 'asc', 'status': 'all'})
        ids = [a.pk for a in resp.context['assets']]
        self.assertEqual(ids, sorted(ids))

    def test_sort_item_desc(self):
        resp = self.client.get(reverse('browse_assets'), {'sort': 'item', 'dir': 'desc', 'status': 'all'})
        ids = [a.pk for a in resp.context['assets']]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_sort_category_asc(self):
        resp = self.client.get(reverse('browse_assets'), {'sort': 'category', 'dir': 'asc', 'status': 'all'})
        cats = [a.category.name for a in resp.context['assets']]
        self.assertEqual(cats, sorted(cats))

    def test_sort_location_desc(self):
        resp = self.client.get(reverse('browse_assets'), {'sort': 'location', 'dir': 'desc', 'status': 'all'})
        locs = [a.location.name for a in resp.context['assets']]
        self.assertEqual(locs, sorted(locs, reverse=True))


class AdminOrderingTests(TestCase):
    """Task 6.3: correct ordering on admin page, default newest-first."""

    def setUp(self):
        _setup(self)
        self.admin = User.objects.create_user('admin', password='pw12345!', is_staff=True)
        UserProfile.objects.create(user=self.admin, branch=self.branch)
        self.client.force_login(self.admin)

    def _asset_names(self, resp):
        return [a.name for a in resp.context['assets']]

    def test_default_order_newest_first(self):
        resp = self.client.get(reverse('admin_assets'))
        ids = [a.pk for a in resp.context['assets']]
        # newest first = descending pk (since created sequentially)
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_sort_name_asc(self):
        resp = self.client.get(reverse('admin_assets'), {'sort': 'name', 'dir': 'asc'})
        self.assertEqual(self._asset_names(resp), ['Alpha', 'Bravo', 'Charlie'])

    def test_sort_name_desc(self):
        resp = self.client.get(reverse('admin_assets'), {'sort': 'name', 'dir': 'desc'})
        self.assertEqual(self._asset_names(resp), ['Charlie', 'Bravo', 'Alpha'])

    def test_sort_item_desc(self):
        resp = self.client.get(reverse('admin_assets'), {'sort': 'item', 'dir': 'desc'})
        ids = [a.pk for a in resp.context['assets']]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_sort_category_asc(self):
        resp = self.client.get(reverse('admin_assets'), {'sort': 'category', 'dir': 'asc'})
        cats = [a.category.name for a in resp.context['assets']]
        self.assertEqual(cats, sorted(cats))

    def test_invalid_sort_uses_default(self):
        resp = self.client.get(reverse('admin_assets'), {'sort': 'bogus', 'dir': 'asc'})
        self.assertIsNone(resp.context['current_sort'])


class SortPaginationTests(TestCase):
    """Task 6.4: sort preserved across pagination."""

    def setUp(self):
        _setup(self)
        self.user = User.objects.create_user('tester', password='pw12345!')
        UserProfile.objects.create(user=self.user, branch=self.branch)
        self.client.force_login(self.user)

    def test_sort_params_in_context_with_pagination(self):
        resp = self.client.get(reverse('browse_assets'), {
            'sort': 'name', 'dir': 'asc', 'page': '1', 'per_page': '12', 'status': 'all',
        })
        self.assertEqual(resp.context['current_sort'], 'name')
        self.assertEqual(resp.context['current_dir'], 'asc')

    def test_sort_preserved_with_filters(self):
        resp = self.client.get(reverse('browse_assets'), {
            'sort': 'location', 'dir': 'desc',
            'category': str(self.cat_a.id), 'status': 'all',
        })
        self.assertEqual(resp.context['current_sort'], 'location')
        self.assertEqual(resp.context['current_dir'], 'desc')
        self.assertEqual(resp.context['selected_category'], str(self.cat_a.id))

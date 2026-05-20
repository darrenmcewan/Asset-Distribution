"""Tests for the admin interest toggle feature."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Asset, Branch, Category, Interest, Location, SiteSetting, UserProfile


def _make_user(username='alice', branch=None, is_staff=False):
    user = User.objects.create_user(username=username, password='pw12345!')
    user.is_staff = is_staff
    user.save()
    UserProfile.objects.create(user=user, branch=branch)
    return user


class SiteSettingSingletonTests(TestCase):
    def test_get_creates_singleton_with_default(self):
        self.assertEqual(SiteSetting.objects.count(), 0)
        setting = SiteSetting.get()
        self.assertTrue(setting.interest_enabled)
        self.assertEqual(SiteSetting.objects.count(), 1)

    def test_get_returns_existing_instance(self):
        SiteSetting.objects.create(pk=1, interest_enabled=False)
        setting = SiteSetting.get()
        self.assertFalse(setting.interest_enabled)
        self.assertEqual(SiteSetting.objects.count(), 1)


class AdminToggleEndpointTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='Test', code='T')
        self.admin = _make_user('admin', branch=self.branch, is_staff=True)
        self.client.login(username='admin', password='pw12345!')

    def test_enable_interest(self):
        SiteSetting.objects.create(pk=1, interest_enabled=False)
        response = self.client.post(reverse('admin_panel'), {'interest_enabled': 'true'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SiteSetting.get().interest_enabled)

    def test_disable_interest(self):
        SiteSetting.objects.create(pk=1, interest_enabled=True)
        response = self.client.post(reverse('admin_panel'), {'interest_enabled': 'false'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SiteSetting.get().interest_enabled)


class ToggleInterestViewEnforcementTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='Test', code='T')
        self.category = Category.objects.create(name='Furniture')
        self.location = Location.objects.create(name='Room A')
        self.user = _make_user('bob', branch=self.branch)
        self.asset = Asset.objects.create(
            name='Test Chair',
            category=self.category,
            location=self.location,
            status='available',
        )
        self.client.login(username='bob', password='pw12345!')

    def test_toggle_interest_returns_403_when_disabled(self):
        SiteSetting.objects.create(pk=1, interest_enabled=False)
        response = self.client.post(reverse('toggle_interest', args=[self.asset.id]))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Interest.objects.count(), 0)

    def test_toggle_interest_works_when_enabled(self):
        SiteSetting.objects.create(pk=1, interest_enabled=True)
        response = self.client.post(
            reverse('toggle_interest', args=[self.asset.id]),
            {'confirmed': 'true'},
        )
        self.assertEqual(response.status_code, 200)


class InterestUIVisibilityTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='Test', code='T')
        self.category = Category.objects.create(name='Furniture')
        self.location = Location.objects.create(name='Room A')
        self.user = _make_user('carol', branch=self.branch)
        self.asset = Asset.objects.create(
            name='Test Table',
            category=self.category,
            location=self.location,
            status='available',
        )
        self.client.login(username='carol', password='pw12345!')

    def test_browse_hides_interest_button_when_disabled(self):
        SiteSetting.objects.create(pk=1, interest_enabled=False)
        response = self.client.get(reverse('browse_assets'))
        self.assertNotContains(response, 'I Want This')

    def test_browse_shows_interest_button_when_enabled(self):
        SiteSetting.objects.create(pk=1, interest_enabled=True)
        response = self.client.get(reverse('browse_assets'))
        self.assertContains(response, 'I Want This')

    def test_my_interests_shows_unavailable_message_when_disabled(self):
        SiteSetting.objects.create(pk=1, interest_enabled=False)
        response = self.client.get(reverse('my_interests'))
        self.assertContains(response, 'currently unavailable')

    def test_nav_hides_my_interests_link_when_disabled(self):
        SiteSetting.objects.create(pk=1, interest_enabled=False)
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'My Interests')

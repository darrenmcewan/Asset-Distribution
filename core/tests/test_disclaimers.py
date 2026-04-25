"""Tests for the disclaimers feature (welcome + claim confirmation)."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Asset, Branch, Category, DisclaimerMessage, Interest, UserProfile


def _make_user(username='alice', branch=None, is_staff=False):
    user = User.objects.create_user(username=username, password='pw12345!')
    user.is_staff = is_staff
    user.save()
    UserProfile.objects.create(user=user, branch=branch)
    return user


class DisclaimerMessageModelTests(TestCase):
    def test_body_html_renders_markdown(self):
        d = DisclaimerMessage.objects.get(slug='welcome')
        d.body = "**bold** and a [link](https://example.com)"
        d.save()
        html = d.body_html
        self.assertIn('<strong>bold</strong>', html)
        self.assertIn('href="https://example.com"', html)

    def test_body_html_strips_disallowed_tags(self):
        d = DisclaimerMessage.objects.get(slug='welcome')
        d.body = "Hello <script>alert(1)</script> world"
        d.save()
        html = d.body_html
        self.assertNotIn('<script>', html)


class DashboardWelcomeModalTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='Test', code='T', display_order=1)
        self.user = _make_user(branch=self.branch)
        self.client.force_login(self.user)

    def test_modal_rendered_when_not_dismissed(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertContains(resp, 'welcome-disclaimer-data')

    def test_modal_omitted_when_dismissed(self):
        self.user.profile.welcome_disclaimer_dismissed = True
        self.user.profile.save()
        resp = self.client.get(reverse('dashboard'))
        self.assertNotContains(resp, 'welcome-disclaimer-data')


class DismissWelcomeEndpointTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='Test', code='T', display_order=1)
        self.user = _make_user(branch=self.branch)
        self.other = _make_user(username='bob', branch=self.branch)

    def test_dismiss_flips_only_requesting_user(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('dismiss_welcome_disclaimer'))
        self.assertEqual(resp.status_code, 200)
        self.user.profile.refresh_from_db()
        self.other.profile.refresh_from_db()
        self.assertTrue(self.user.profile.welcome_disclaimer_dismissed)
        self.assertFalse(self.other.profile.welcome_disclaimer_dismissed)


class ToggleInterestConfirmationTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='Test', code='T', display_order=1)
        self.user = _make_user(branch=self.branch)
        self.client.force_login(self.user)
        self.cat = Category.objects.create(name='Cat')
        self.asset = Asset.objects.create(name='Lamp', category=self.cat)

    def _toggle(self, **post):
        return self.client.post(
            reverse('toggle_interest', args=[self.asset.id]),
            data=post,
        )

    def test_unconfirmed_create_returns_disclaimer(self):
        resp = self._toggle()
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body['success'])
        self.assertTrue(body['requires_confirmation'])
        self.assertIn('title', body['disclaimer'])
        self.assertIn('body_html', body['disclaimer'])
        self.assertFalse(Interest.objects.filter(user=self.user, asset=self.asset).exists())

    def test_confirmed_create_succeeds(self):
        resp = self._toggle(confirmed='true')
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertTrue(body['interested'])
        self.assertTrue(Interest.objects.filter(user=self.user, asset=self.asset).exists())

    def test_remove_does_not_require_confirmation(self):
        Interest.objects.create(user=self.user, asset=self.asset, position=1)
        resp = self._toggle()
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertFalse(body['interested'])
        self.assertFalse(Interest.objects.filter(user=self.user, asset=self.asset).exists())


class AdminDisclaimersViewTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='Test', code='T', display_order=1)
        self.staff = _make_user(username='staff', branch=self.branch, is_staff=True)
        self.regular = _make_user(username='regular', branch=self.branch)

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(reverse('admin_disclaimers'))
        self.assertEqual(resp.status_code, 302)

    def test_non_staff_denied(self):
        self.client.force_login(self.regular)
        resp = self.client.get(reverse('admin_disclaimers'))
        self.assertEqual(resp.status_code, 302)

    def test_staff_can_view(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_disclaimers'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Welcome message')
        self.assertContains(resp, 'Claim confirmation')

    def test_staff_can_update(self):
        self.client.force_login(self.staff)
        resp = self.client.post(reverse('admin_disclaimers'), data={
            'target': 'welcome',
            'welcome-title': 'New Title',
            'welcome-body': 'New body content.',
        })
        self.assertEqual(resp.status_code, 302)
        d = DisclaimerMessage.objects.get(slug='welcome')
        self.assertEqual(d.title, 'New Title')
        self.assertEqual(d.body, 'New body content.')
        self.assertEqual(d.updated_by, self.staff)

    def test_empty_body_rejected(self):
        self.client.force_login(self.staff)
        original = DisclaimerMessage.objects.get(slug='welcome')
        resp = self.client.post(reverse('admin_disclaimers'), data={
            'target': 'welcome',
            'welcome-title': 'Some title',
            'welcome-body': '   ',
        })
        self.assertEqual(resp.status_code, 200)
        original.refresh_from_db()
        self.assertNotEqual(original.body, '   ')

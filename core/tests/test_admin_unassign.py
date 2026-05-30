"""Tests for the admin unassign-to-available flow."""

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.models import (
    Asset,
    AssignmentEvent,
    Branch,
    Category,
    Location,
    UserProfile,
)
from core.views import admin_assets_view


class AdminUnassignItemTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='TestBranch', code='T', display_order=1)
        self.staff = User.objects.create_user(username='admin', password='pw12345!', is_staff=True)
        UserProfile.objects.create(user=self.staff, branch=self.branch)
        self.recipient = User.objects.create_user(username='alice', password='pw12345!')
        UserProfile.objects.create(user=self.recipient, branch=self.branch)
        self.other = User.objects.create_user(username='bob', password='pw12345!')
        UserProfile.objects.create(user=self.other, branch=self.branch)
        self.category, _ = Category.objects.get_or_create(name='Furniture')
        self.location, _ = Location.objects.get_or_create(name='Office')
        self.asset = Asset.objects.create(
            name='Desk',
            category=self.category,
            location=self.location,
            status='claimed',
            assigned_to=self.recipient,
        )

    def _unassign(self):
        return self.client.post(
            reverse('admin_mark_status', args=[self.asset.id]),
            {'status': 'available'},
        )

    def test_admin_unassign_clears_assignment_and_sets_available(self):
        self.client.force_login(self.staff)
        resp = self._unassign()
        self.assertEqual(resp.status_code, 302)
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.assigned_to)
        self.assertEqual(self.asset.status, 'available')

    def test_assigned_row_shows_reassign_and_mark_available_actions(self):
        factory = RequestFactory()
        request = factory.get(reverse('admin_assets'))
        request.user = self.staff
        resp = admin_assets_view(request)
        body = resp.content.decode()
        self.assertIn('Reassign', body)
        self.assertIn('Mark available', body)

    def test_available_row_does_not_show_unassign_action(self):
        self.asset.assigned_to = None
        self.asset.status = 'available'
        self.asset.save()
        factory = RequestFactory()
        request = factory.get(reverse('admin_assets'))
        request.user = self.staff
        resp = admin_assets_view(request)
        body = resp.content.decode()
        self.assertNotIn('Mark available', body)
        self.assertNotIn('Reassign', body)

    def test_non_admin_cannot_unassign(self):
        self.client.force_login(self.recipient)
        resp = self._unassign()
        self.assertIn(resp.status_code, (302, 403))
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.assigned_to, self.recipient)
        self.assertEqual(self.asset.status, 'claimed')

    def test_unassign_creates_assignment_event(self):
        self.client.force_login(self.staff)
        self._unassign()
        event = AssignmentEvent.objects.filter(asset=self.asset).order_by('-created_at').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, 'unassign')
        self.assertEqual(event.actor, self.staff)
        self.assertEqual(event.from_user, self.recipient)
        self.assertIsNone(event.to_user)
        self.assertEqual(event.from_status, 'claimed')
        self.assertEqual(event.to_status, 'available')

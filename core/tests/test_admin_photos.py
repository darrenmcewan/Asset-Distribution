"""Tests for admin photo management."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Asset, AssetPhoto, Category, Location


def _make_user(username='staff', is_staff=False):
    user = User.objects.create_user(username=username, password='pw12345!')
    user.is_staff = is_staff
    user.save()
    return user


class AdminPrimaryPhotoTests(TestCase):
    def setUp(self):
        self.staff = _make_user(is_staff=True)
        self.regular = _make_user(username='regular')
        self.category, _ = Category.objects.get_or_create(name='Furniture')
        self.location, _ = Location.objects.get_or_create(name='Living Room')
        self.asset = Asset.objects.create(
            name='Chair',
            category=self.category,
            location=self.location,
        )
        self.first, self.second, self.third, self.fourth = AssetPhoto.objects.bulk_create([
            AssetPhoto(asset=self.asset, image='assets/first.jpg', upload_order=0),
            AssetPhoto(asset=self.asset, image='assets/second.jpg', upload_order=1),
            AssetPhoto(asset=self.asset, image='assets/third.jpg', upload_order=2),
            AssetPhoto(asset=self.asset, image='assets/fourth.jpg', upload_order=3),
        ])

    def test_staff_can_make_any_photo_primary(self):
        self.client.force_login(self.staff)

        resp = self.client.post(reverse('admin_make_primary_photo', args=[self.third.id]))

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(self.asset.get_primary_photo(), self.third)
        self.assertEqual(
            list(self.asset.photos.values_list('id', 'upload_order')),
            [(self.third.id, 0), (self.first.id, 1), (self.second.id, 2), (self.fourth.id, 3)],
        )

    def test_non_staff_cannot_make_photo_primary(self):
        self.client.force_login(self.regular)

        resp = self.client.post(reverse('admin_make_primary_photo', args=[self.second.id]))

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.asset.get_primary_photo(), self.first)

    def test_staff_can_move_secondary_photo_earlier(self):
        self.client.force_login(self.staff)

        resp = self.client.post(
            reverse('admin_reorder_secondary_photo', args=[self.third.id]),
            data={'direction': 'earlier'},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(self.asset.get_primary_photo(), self.first)
        self.assertEqual(
            list(self.asset.photos.values_list('id', 'upload_order')),
            [(self.first.id, 0), (self.third.id, 1), (self.second.id, 2), (self.fourth.id, 3)],
        )

    def test_staff_can_move_secondary_photo_later(self):
        self.client.force_login(self.staff)

        resp = self.client.post(
            reverse('admin_reorder_secondary_photo', args=[self.second.id]),
            data={'direction': 'later'},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(self.asset.get_primary_photo(), self.first)
        self.assertEqual(
            list(self.asset.photos.values_list('id', 'upload_order')),
            [(self.first.id, 0), (self.third.id, 1), (self.second.id, 2), (self.fourth.id, 3)],
        )

    def test_secondary_reorder_does_not_move_main_photo(self):
        self.client.force_login(self.staff)

        resp = self.client.post(
            reverse('admin_reorder_secondary_photo', args=[self.first.id]),
            data={'direction': 'later'},
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.asset.get_primary_photo(), self.first)

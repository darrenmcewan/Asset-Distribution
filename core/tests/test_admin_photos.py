"""Tests for admin photo management."""

import shutil
import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from core.models import Asset, AssetPhoto, Category, Location


TEMP_MEDIA_ROOT = tempfile.mkdtemp()


def _make_user(username='staff', is_staff=False):
    user = User.objects.create_user(username=username, password='pw12345!')
    user.is_staff = is_staff
    user.save()
    return user


def _image_upload(name='clipboard.png', color='blue'):
    image = Image.new('RGB', (8, 8), color=color)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class AdminAssetPhotoUploadTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.staff = _make_user(is_staff=True)
        self.regular = _make_user(username='regular')
        self.category, _ = Category.objects.get_or_create(name='Furniture')
        self.location, _ = Location.objects.get_or_create(name='Living Room')

    def test_admin_asset_form_shows_clipboard_photo_uploader(self):
        self.client.force_login(self.staff)

        resp = self.client.get(reverse('admin_add_asset'))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Paste images here')
        self.assertContains(resp, 'clipboard-photos.js')

    def test_staff_can_create_asset_with_photo_upload(self):
        self.client.force_login(self.staff)

        resp = self.client.post(reverse('admin_add_asset'), {
            'name': 'Lamp',
            'description': '',
            'category': self.category.id,
            'location': self.location.id,
            'condition': '',
            'notes': '',
            'photos': [_image_upload()],
        })

        self.assertRedirects(resp, reverse('admin_assets'))
        asset = Asset.objects.get(name='Lamp')
        self.assertEqual(asset.photos.count(), 1)

    def test_staff_can_add_more_photos_when_editing_asset(self):
        self.client.force_login(self.staff)
        asset = Asset.objects.create(
            name='Chair',
            category=self.category,
            location=self.location,
        )

        resp = self.client.post(reverse('admin_edit_asset', args=[asset.id]), {
            'name': 'Chair',
            'description': '',
            'category': self.category.id,
            'location': self.location.id,
            'condition': '',
            'notes': '',
            'photos': [_image_upload('clipboard-edit.png', color='green')],
        })

        self.assertRedirects(resp, reverse('admin_assets'))
        self.assertEqual(asset.photos.count(), 1)


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

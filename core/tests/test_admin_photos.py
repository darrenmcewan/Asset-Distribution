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

from core.models import Asset, AssetComment, AssetPhoto, AssignmentEvent, Category, Interest, Location


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

    def test_admin_add_asset_form_includes_unsaved_details_guard(self):
        self.client.force_login(self.staff)

        resp = self.client.get(reverse('admin_add_asset'))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-unsaved-asset-form')
        self.assertContains(resp, 'Discard asset details?')
        self.assertContains(resp, 'beforeunload')

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

    def test_staff_can_prefill_add_form_from_cloned_asset_without_photos(self):
        self.client.force_login(self.staff)
        source = Asset.objects.create(
            name='Lamp',
            description='Tall brass lamp',
            category=self.category,
            location=self.location,
            condition='Good',
            notes='Keep shade with base',
            status='claimed',
            assigned_to=self.regular,
            created_by=self.staff,
        )
        AssetPhoto.objects.create(asset=source, image=_image_upload('source-photo.png'))
        Interest.objects.create(user=self.regular, asset=source, position=1)
        AssetComment.objects.create(asset=source, author=self.staff, body='Original comment')
        AssignmentEvent.objects.create(
            asset=source,
            actor=self.staff,
            event_type='assign',
            to_user=self.regular,
            to_status='claimed',
        )

        resp = self.client.get(f"{reverse('admin_add_asset')}?clone={source.id}")

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Clone Asset')
        self.assertContains(resp, 'data-unsaved-asset-form')
        self.assertContains(resp, 'Photos, assignment, status, interests, comments, and history are not copied.')
        self.assertNotContains(resp, 'Existing Photos')
        self.assertNotContains(resp, 'source-photo.jpg')
        form = resp.context['form']
        self.assertEqual(form.initial['name'], source.name)
        self.assertEqual(form.initial['description'], source.description)
        self.assertEqual(form.initial['category'], self.category)
        self.assertEqual(form.initial['location'], self.location)
        self.assertEqual(form.initial['condition'], source.condition)
        self.assertEqual(form.initial['notes'], source.notes)

    def test_posting_cloned_form_creates_fresh_asset_record(self):
        self.client.force_login(self.staff)
        source = Asset.objects.create(
            name='Lamp',
            description='Tall brass lamp',
            category=self.category,
            location=self.location,
            condition='Good',
            notes='Keep shade with base',
            status='claimed',
            assigned_to=self.regular,
            created_by=self.regular,
        )
        AssetPhoto.objects.create(asset=source, image=_image_upload('source-photo.png'))
        Interest.objects.create(user=self.regular, asset=source, position=1)
        AssetComment.objects.create(asset=source, author=self.staff, body='Original comment')
        AssignmentEvent.objects.create(
            asset=source,
            actor=self.staff,
            event_type='assign',
            to_user=self.regular,
            to_status='claimed',
        )

        resp = self.client.post(f"{reverse('admin_add_asset')}?clone={source.id}", {
            'name': source.name,
            'description': source.description,
            'category': source.category_id,
            'location': source.location_id,
            'condition': source.condition,
            'notes': source.notes,
        })

        self.assertRedirects(resp, reverse('admin_assets'))
        cloned = Asset.objects.exclude(pk=source.pk).get(name=source.name)
        self.assertNotEqual(cloned.serial_number, source.serial_number)
        self.assertEqual(cloned.description, source.description)
        self.assertEqual(cloned.category, source.category)
        self.assertEqual(cloned.location, source.location)
        self.assertEqual(cloned.condition, source.condition)
        self.assertEqual(cloned.notes, source.notes)
        self.assertEqual(cloned.status, 'available')
        self.assertIsNone(cloned.assigned_to)
        self.assertEqual(cloned.created_by, self.staff)
        self.assertEqual(cloned.photos.count(), 0)
        self.assertEqual(cloned.interests.count(), 0)
        self.assertEqual(cloned.comments.count(), 0)
        self.assertEqual(cloned.events.count(), 0)

    def test_admin_assets_list_has_clone_link(self):
        self.client.force_login(self.staff)
        asset = Asset.objects.create(
            name='Chair',
            category=self.category,
            location=self.location,
        )

        resp = self.client.get(reverse('admin_assets'))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'{reverse("admin_add_asset")}?clone={asset.id}')
        self.assertContains(resp, 'Clone')

    def test_admin_assets_list_has_assignment_return_anchor_fields(self):
        self.client.force_login(self.staff)
        asset = Asset.objects.create(
            name='Chair',
            category=self.category,
            location=self.location,
        )

        resp = self.client.get(reverse('admin_assets'))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'id="admin-asset-{asset.id}"')
        self.assertContains(resp, 'name="next" id="assignNext"')
        self.assertContains(resp, "window.location.pathname + window.location.search + '#admin-asset-' + assetId")

    def test_admin_assets_list_uses_top_and_bottom_jump_pagination(self):
        self.client.force_login(self.staff)
        for i in range(21):
            Asset.objects.create(
                name=f'Chair {i:02d}',
                category=self.category,
                location=self.location,
            )

        resp = self.client.get(reverse('admin_assets'))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'pagination--top', count=1)
        self.assertContains(resp, 'class="page-input"', count=2)
        self.assertContains(resp, 'onchange="goToPage(this)"', count=2)

    def test_admin_assets_pagination_preserves_filters(self):
        self.client.force_login(self.staff)
        for i in range(21):
            Asset.objects.create(
                name=f'Filtered Lamp {i:02d}',
                category=self.category,
                location=self.location,
                status='available',
            )

        resp = self.client.get(reverse('admin_assets'), {
            'category': self.category.id,
            'location': self.location.id,
            'status': 'available',
            'search': 'Filtered',
        })

        self.assertEqual(resp.status_code, 200)
        expected_link = (
            f'?page=2&category={self.category.id}&location={self.location.id}'
            '&search=Filtered&status=available'
        )
        self.assertContains(resp, expected_link, count=2)

    def test_invalid_clone_id_returns_not_found(self):
        self.client.force_login(self.staff)

        resp = self.client.get(f"{reverse('admin_add_asset')}?clone=not-a-number")

        self.assertEqual(resp.status_code, 404)

    def test_admin_edit_asset_form_does_not_enable_unsaved_add_guard(self):
        self.client.force_login(self.staff)
        asset = Asset.objects.create(
            name='Chair',
            category=self.category,
            location=self.location,
        )

        resp = self.client.get(reverse('admin_edit_asset', args=[asset.id]))

        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'data-unsaved-asset-form')

    def test_admin_direct_assign_redirects_to_safe_next_url(self):
        self.client.force_login(self.staff)
        asset = Asset.objects.create(
            name='Lamp',
            category=self.category,
            location=self.location,
        )
        next_url = f'{reverse("admin_assets")}?page=2&search=Lamp#admin-asset-{asset.id}'

        resp = self.client.post(reverse('admin_direct_assign'), {
            'asset_id': asset.id,
            'user_id': self.regular.id,
            'next': next_url,
        })

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], next_url)
        asset.refresh_from_db()
        self.assertEqual(asset.status, 'claimed')
        self.assertEqual(asset.assigned_to, self.regular)
        self.assertTrue(AssignmentEvent.objects.filter(
            asset=asset,
            event_type='assign',
            to_user=self.regular,
        ).exists())

    def test_admin_direct_assign_ignores_unsafe_next_url(self):
        self.client.force_login(self.staff)
        asset = Asset.objects.create(
            name='Lamp',
            category=self.category,
            location=self.location,
        )

        resp = self.client.post(reverse('admin_direct_assign'), {
            'asset_id': asset.id,
            'user_id': self.regular.id,
            'next': 'https://example.com/admin-panel/assets/',
        })

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], reverse('admin_assets'))


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

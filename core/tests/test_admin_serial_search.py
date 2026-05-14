"""Tests for serial-number search on the admin assets page.

Note: These tests exercise the helper and queryset filter directly rather than
going through the Django test client, because the test client is currently
broken in this environment due to a Python 3.14 / Django template-context
incompatibility that affects all view-rendering tests.
"""

from django.contrib.auth.models import User
from django.db.models import CharField, Q, Value
from django.db.models.functions import Cast, LPad
from django.test import TestCase

from core.models import Asset, Branch, Category, Location, UserProfile
from core.views import _build_serial_search_filter


def _apply_admin_search(queryset, search):
    """Mirror the search-filter logic in admin_assets_view for testing."""
    if not search:
        return queryset
    text_q = Q(name__icontains=search) | Q(description__icontains=search)
    needs_annotation, serial_qs = _build_serial_search_filter(search)
    if needs_annotation:
        queryset = queryset.annotate(
            serial_digits=LPad(
                Cast('pk', output_field=CharField()),
                3,
                Value('0'),
            )
        )
        for sq in serial_qs:
            text_q |= sq
    return queryset.filter(text_q)


class BuildSerialSearchFilterTests(TestCase):
    """Unit tests for the helper that builds serial-number Q objects."""

    def test_empty_query_returns_no_filter(self):
        self.assertEqual(_build_serial_search_filter(''), (False, []))

    def test_pure_digits_request_annotation_and_pk_fallback(self):
        needs, qs = _build_serial_search_filter('11')
        self.assertTrue(needs)
        self.assertEqual(len(qs), 2)

    def test_jbm_prefix_uppercase_stripped(self):
        needs, qs = _build_serial_search_filter('JBM-011')
        self.assertTrue(needs)
        self.assertEqual(len(qs), 2)

    def test_jbm_prefix_lowercase_stripped(self):
        needs, qs = _build_serial_search_filter('jbm-011')
        self.assertTrue(needs)
        self.assertEqual(len(qs), 2)

    def test_non_numeric_query_returns_no_serial_filter(self):
        self.assertEqual(_build_serial_search_filter('Widget'), (False, []))

    def test_jbm_prefix_with_non_numeric_returns_no_serial_filter(self):
        self.assertEqual(_build_serial_search_filter('jbm-abc'), (False, []))


class AdminAssetsSerialSearchQuerysetTests(TestCase):
    """Verify the queryset filter matches assets by serial number."""

    def setUp(self):
        self.branch = Branch.objects.create(name='Branch', code='B', display_order=1)
        self.category = Category.objects.create(name='Cat', display_order=1)
        self.location = Location.objects.create(name='Loc', display_order=1)

        for pk, name, description in [
            (11, 'Widget A', 'first widget'),
            (111, 'Widget B', 'second widget'),
            (211, 'Widget C', 'third widget'),
            (50, 'Gadget', 'unrelated thing'),
        ]:
            asset = Asset(
                pk=pk,
                name=name,
                description=description,
                category=self.category,
                location=self.location,
            )
            asset.save(force_insert=True)

        self.admin = User.objects.create_user('admin', password='pw12345!', is_staff=True)
        UserProfile.objects.create(user=self.admin, branch=self.branch)

    def _ids(self, search):
        return set(_apply_admin_search(Asset.objects.all(), search).values_list('pk', flat=True))

    def test_partial_digits_match_all_padded_serials(self):
        """'11' surfaces JBM-011, JBM-111, JBM-211 (and excludes JBM-050)."""
        self.assertEqual(self._ids('11'), {11, 111, 211})

    def test_full_serial_with_prefix_uppercase(self):
        self.assertEqual(self._ids('JBM-011'), {11})

    def test_full_serial_with_prefix_lowercase(self):
        self.assertEqual(self._ids('jbm-011'), {11})

    def test_three_digit_pk_match(self):
        self.assertEqual(self._ids('111'), {111})

    def test_name_search_unchanged(self):
        self.assertEqual(self._ids('Gadget'), {50})

    def test_description_search_unchanged(self):
        self.assertEqual(self._ids('unrelated'), {50})

    def test_no_matches_returns_empty(self):
        self.assertEqual(self._ids('zzz-no-such-thing'), set())

    def test_non_numeric_after_prefix_falls_back_to_text_search(self):
        """'jbm-abc' isn't a valid serial; falls back to text-only and matches nothing."""
        self.assertEqual(self._ids('jbm-abc'), set())

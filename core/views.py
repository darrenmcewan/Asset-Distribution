"""
Views for the Asset Distribution System.
"""

import csv
import json
import mimetypes
import os
import re
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import CharField, Count, OuterRef, Q, Subquery, Value
from django.db.models.functions import Cast, LPad
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

try:
    from django_ratelimit.decorators import ratelimit
except ImportError:  # pragma: no cover - optional dependency
    def ratelimit(*args, **kwargs):
        def decorator(view):
            return view
        return decorator

from .email import send_assignment_notification
from .forms import (
    AdminPasswordResetForm,
    AssetForm,
    CategoryForm,
    CommentForm,
    DisclaimerForm,
    LocationForm,
    SignupForm,
    StyledLoginForm,
)
from .models import (
    Asset,
    AssetComment,
    AssetPhoto,
    AssignmentEvent,
    Branch,
    Category,
    DisclaimerMessage,
    Interest,
    Location,
    SiteSetting,
    UserProfile,
)


# ============================================================================
# Decorators
# ============================================================================

def admin_required(view_func):
    """Allow only authenticated staff users."""
    return user_passes_test(lambda u: u.is_authenticated and u.is_staff, login_url='login')(view_func)


# ============================================================================
# Authentication
# ============================================================================

def login_view(request):
    """Username/password login. Admins use the same form (is_staff routes admin access)."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = StyledLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            prev = user.last_login.isoformat() if user.last_login else None
            auth_login(request, user)
            if prev:
                request.session['previous_login'] = prev
            return redirect('dashboard')
    else:
        form = StyledLoginForm(request)

    return render(request, 'login.html', {'form': form})


login_view = ratelimit(key='ip', rate='5/15m', block=True, method='POST')(login_view)


def signup_view(request):
    """Open signup gated by an invite code."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    expected_code = getattr(settings, 'SIGNUP_INVITE_CODE', '')

    if request.method == 'POST':
        form = SignupForm(request.POST, expected_invite_code=expected_code)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, f'Welcome, {user.username}! Your account has been created.')
            return redirect('dashboard')
    else:
        form = SignupForm(expected_invite_code=expected_code)

    return render(request, 'signup.html', {'form': form})


signup_view = ratelimit(key='ip', rate='5/15m', block=True, method='POST')(signup_view)


def logout_view(request):
    auth_logout(request)
    return redirect('login')


# ============================================================================
# Helpers
# ============================================================================

def _previous_login(request):
    """The user's previous last_login (now is the new one). Falls back to 7 days ago."""
    user = request.user
    prev = request.session.get('previous_login')
    if prev:
        try:
            return timezone.datetime.fromisoformat(prev)
        except ValueError:
            pass
    if user.last_login:
        return user.last_login
    return timezone.now() - timedelta(days=7)


def _safe_next_url(request, next_url):
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return ''


# ============================================================================
# User views
# ============================================================================

@login_required
def dashboard_view(request):
    user = request.user
    assigned = Asset.objects.filter(assigned_to=user).select_related('category', 'location')
    interests = (
        Interest.objects
        .filter(user=user)
        .select_related('asset', 'asset__category', 'asset__location')
        .order_by('position')
    )

    cutoff = _previous_login(request)
    recent = (
        Asset.objects
        .filter(created_at__gt=cutoff, status='available')
        .exclude(created_by=user)
        .select_related('category', 'location')
        .prefetch_related('photos')
        .annotate(interest_count=Count('interests'))
        .order_by('-created_at')[:10]
    )

    welcome = _welcome_disclaimer_for(user)
    welcome_payload = None
    if welcome is not None:
        welcome_payload = {
            'title': welcome.title,
            'body_html': welcome.body_html,
            'dismiss_url': reverse('dismiss_welcome_disclaimer'),
            'csrf': get_token(request),
        }

    context = {
        'assigned_items': assigned,
        'interests_preview': interests[:5],
        'interest_count': interests.count(),
        'assigned_count': assigned.count(),
        'recent_items': recent,
        'recent_cutoff': cutoff,
        'welcome_disclaimer': welcome,
        'welcome_disclaimer_payload': welcome_payload,
    }
    return render(request, 'dashboard.html', context)


def _welcome_disclaimer_for(user):
    """Return the welcome DisclaimerMessage for the user, or None if dismissed/missing."""
    profile = getattr(user, 'profile', None)
    if profile is not None and profile.welcome_disclaimer_dismissed:
        return None
    return DisclaimerMessage.objects.filter(slug=DisclaimerMessage.SLUG_WELCOME).first()


@login_required
@require_POST
def dismiss_welcome_disclaimer_view(request):
    profile = getattr(request.user, 'profile', None)
    if profile is None:
        return JsonResponse({'success': False, 'error': 'No profile'}, status=400)
    profile.welcome_disclaimer_dismissed = True
    profile.save(update_fields=['welcome_disclaimer_dismissed'])
    return JsonResponse({'success': True})


SORT_FIELD_MAP = {
    'item': 'pk',
    'name': 'name',
    'category': 'category__name',
    'location': 'location__name',
}


def _parse_sort_params(request):
    """Return validated (sort_key, direction) or (None, None)."""
    sort_key = request.GET.get('sort', '')
    direction = request.GET.get('dir', '')
    if sort_key not in SORT_FIELD_MAP or direction not in ('asc', 'desc'):
        return None, None
    return sort_key, direction


def _apply_sort(queryset, sort_key, direction, default_ordering):
    """Apply sort to queryset or fall back to default_ordering."""
    if sort_key is None:
        return queryset.order_by(*default_ordering) if default_ordering else queryset
    field = SORT_FIELD_MAP[sort_key]
    if direction == 'desc':
        field = '-' + field
    return queryset.order_by(field)


@login_required
def browse_assets_view(request):
    user = request.user
    category_id = request.GET.get('category')
    location_id = request.GET.get('location')
    search = (request.GET.get('search') or '').strip()
    status_filter = request.GET.get('status', 'available')

    ALLOWED_PER_PAGE = [12, 25, 50, 75, 100]
    try:
        per_page = int(request.GET.get('per_page', 25))
    except (ValueError, TypeError):
        per_page = 25
    if per_page not in ALLOWED_PER_PAGE:
        per_page = 25

    assets = Asset.objects.select_related('category', 'location', 'assigned_to').prefetch_related('photos').annotate(interest_count=Count('interests'))
    if category_id:
        assets = assets.filter(category_id=category_id)
    if location_id:
        assets = assets.filter(location_id=location_id)
    if search:
        assets = assets.filter(Q(name__icontains=search) | Q(description__icontains=search))
    if status_filter and status_filter != 'all':
        assets = assets.filter(status=status_filter)

    sort_key, sort_dir = _parse_sort_params(request)
    assets = _apply_sort(assets, sort_key, sort_dir, default_ordering=['-pk'])

    my_interest_asset_ids = set(
        Interest.objects.filter(user=user).values_list('asset_id', flat=True)
    )

    paginator = Paginator(assets, per_page)
    page = request.GET.get('page', 1)

    # Build the current browse query string for back-link preservation
    browse_params = request.GET.urlencode()

    return render(request, 'browse_assets.html', {
        'assets': paginator.get_page(page),
        'categories': Category.objects.annotate(asset_count=Count('assets')),
        'locations': Location.objects.annotate(asset_count=Count('assets')),
        'selected_category': category_id,
        'selected_location': location_id,
        'search': search,
        'status_filter': status_filter,
        'my_interest_asset_ids': my_interest_asset_ids,
        'browse_query': browse_params,
        'per_page': per_page,
        'per_page_choices': ALLOWED_PER_PAGE,
        'current_sort': sort_key,
        'current_dir': sort_dir,
    })


@login_required
def asset_detail_view(request, asset_id):
    asset = get_object_or_404(
        Asset.objects.select_related('category', 'location', 'assigned_to').prefetch_related('photos'),
        pk=asset_id,
    )
    interest = Interest.objects.filter(user=request.user, asset=asset).first()

    comments = list(
        AssetComment.objects
        .filter(asset=asset)
        .select_related('author', 'author__profile', 'author__profile__branch')
        .order_by('created_at')
    )

    # Build a per-asset alias map: first author -> 'A', second -> 'B', ...
    alias_map = {}
    for comment in comments:
        if comment.author_id not in alias_map:
            idx = len(alias_map)
            alias_map[comment.author_id] = _alias_for_index(idx)
    # Attach the alias to each comment for easy template rendering.
    for comment in comments:
        comment.alias = alias_map[comment.author_id]

    events = []
    if request.user.is_staff:
        events = list(
            AssignmentEvent.objects
            .filter(asset=asset)
            .select_related('actor', 'from_user', 'to_user')
            .order_by('-created_at')
        )

    # Preserve browse state for back link — only allow safe query string content
    back_query = request.GET.get('back', '')
    if back_query and not re.fullmatch(r'[a-zA-Z0-9&=_%+\-\.]*', back_query):
        back_query = ''

    return render(request, 'asset_detail.html', {
        'asset': asset,
        'interest': interest,
        'photos': asset.photos.all(),
        'comments': comments,
        'alias_map': alias_map,
        'comment_form': CommentForm(),
        'events': events,
        'back_query': back_query,
    })


def _alias_for_index(idx):
    """Return 'A', 'B', ... 'Z', 'AA', 'AB', ... for the given 0-based index."""
    label = ''
    n = idx
    while True:
        label = chr(ord('A') + (n % 26)) + label
        n = n // 26 - 1
        if n < 0:
            break
    return label


@login_required
@require_POST
def post_comment_view(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        AssetComment.objects.create(
            asset=asset,
            author=request.user,
            body=form.cleaned_data['body'],
        )
        messages.success(request, 'Your comment has been posted.')
    else:
        messages.error(request, form.errors.get('body', ['Could not post comment.'])[0])
    return redirect('asset_detail', asset_id=asset.id)


@admin_required
@require_POST
def admin_delete_comment_view(request, comment_id):
    comment = get_object_or_404(AssetComment, pk=comment_id)
    asset_id = comment.asset_id
    comment.delete()
    messages.success(request, 'Comment deleted.')
    return redirect('asset_detail', asset_id=asset_id)


@login_required
@require_POST
def toggle_interest_view(request, asset_id):
    if not SiteSetting.get().interest_enabled:
        return JsonResponse({'success': False, 'error': 'Interest feature is currently disabled'}, status=403)

    asset = get_object_or_404(Asset, pk=asset_id)
    if asset.status != 'available':
        return JsonResponse({'success': False, 'error': 'Item is no longer available'})

    user = request.user
    existing = Interest.objects.filter(user=user, asset=asset).first()

    if existing:
        with transaction.atomic():
            removed_position = existing.position
            existing.delete()
            # Renumber remaining interests to keep contiguous positions.
            remaining = list(
                Interest.objects.select_for_update()
                .filter(user=user, position__gt=removed_position)
                .order_by('position')
            )
            for interest in remaining:
                interest.position -= 1
                interest.save(update_fields=['position'])
        return JsonResponse({'success': True, 'interested': False})

    # Creating a new interest requires explicit disclaimer confirmation each time.
    if request.POST.get('confirmed') != 'true':
        disclaimer = DisclaimerMessage.objects.filter(
            slug=DisclaimerMessage.SLUG_CLAIM_CONFIRMATION
        ).first()
        return JsonResponse({
            'success': False,
            'requires_confirmation': True,
            'disclaimer': {
                'title': disclaimer.title if disclaimer else 'Confirm your interest',
                'body_html': disclaimer.body_html if disclaimer else '',
            },
        })

    with transaction.atomic():
        Interest.objects.create(
            user=user,
            asset=asset,
            position=Interest.next_position_for(user),
        )
    return JsonResponse({'success': True, 'interested': True})


@login_required
def my_interests_view(request):
    interests = (
        Interest.objects
        .filter(user=request.user)
        .select_related('asset', 'asset__category', 'asset__location')
        .prefetch_related('asset__photos')
        .order_by('position')
    )
    return render(request, 'my_interests.html', {'interests': interests})


@login_required
@require_POST
def reorder_interests_view(request):
    """Accept JSON {"order": [interest_id, ...]} and assign positions 1..N atomically."""
    try:
        payload = json.loads(request.body or '{}')
        ordered_ids = [int(x) for x in payload.get('order', [])]
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'error': 'Invalid payload'}, status=400)

    user = request.user
    user_interests = list(Interest.objects.filter(user=user, id__in=ordered_ids))

    if len(user_interests) != len(ordered_ids):
        return JsonResponse({'success': False, 'error': 'Interest does not belong to user'}, status=403)

    by_id = {i.id: i for i in user_interests}

    try:
        with transaction.atomic():
            # First move all rows to negative offsets to avoid unique violations during shuffle.
            for idx, iid in enumerate(ordered_ids, start=1):
                by_id[iid].position = -idx
                by_id[iid].save(update_fields=['position'])
            # Then assign final 1..N values.
            for idx, iid in enumerate(ordered_ids, start=1):
                by_id[iid].position = idx
                by_id[iid].save(update_fields=['position'])
    except IntegrityError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)

    return JsonResponse({'success': True})


@login_required
def my_items_view(request):
    items = Asset.objects.filter(assigned_to=request.user).select_related('category', 'location').prefetch_related('photos')
    return render(request, 'my_items.html', {'items': items})


@admin_required
def upload_asset_view(request):
    """Admin-only asset upload. Non-staff users are redirected to login."""
    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.created_by = request.user
            asset.save()
            for i, photo in enumerate(request.FILES.getlist('photos')):
                AssetPhoto.objects.create(asset=asset, image=photo, upload_order=i)
            messages.success(request, f'Asset "{asset.name}" has been added!')
            return redirect('asset_detail', asset_id=asset.id)
    else:
        form = AssetForm()

    return render(request, 'upload_asset.html', {
        'form': form,
        'categories': Category.objects.all(),
        'locations': Location.objects.all(),
    })


# ============================================================================
# Admin
# ============================================================================

@admin_required
def admin_panel_view(request):
    site_setting = SiteSetting.get()

    if request.method == 'POST' and 'interest_enabled' in request.POST:
        value = request.POST.get('interest_enabled') == 'true'
        site_setting.interest_enabled = value
        site_setting.save(update_fields=['interest_enabled'])
        messages.success(request, 'Interest feature ' + ('enabled' if value else 'disabled') + '.')
        return redirect('admin_panel')

    branch_stats = []
    for branch in Branch.objects.all():
        count = Asset.objects.filter(assigned_to__profile__branch=branch).count()
        branch_stats.append({'branch': branch, 'count': count})

    stats = {
        'total_assets': Asset.objects.count(),
        'available_assets': Asset.objects.filter(status='available').count(),
        'claimed_assets': Asset.objects.filter(status='claimed').count(),
        'total_interests': Interest.objects.count(),
        'total_users': User.objects.count(),
    }

    return render(request, 'admin/panel.html', {
        'stats': stats,
        'branch_stats': branch_stats,
        'site_setting': site_setting,
    })


def _build_serial_search_filter(search):
    """Translate an admin search query into serial-number Q objects.

    Strips an optional case-insensitive ``jbm-`` prefix and surrounding
    whitespace. If the remainder is purely numeric, returns:
      - a flag indicating the queryset should be annotated with
        ``serial_digits`` (zero-padded pk as text), and
      - a list of ``Q`` objects to OR into the existing search filter.

    Returns ``(needs_annotation, q_objects)``.
    """
    if not search:
        return False, []
    candidate = search.strip()
    if candidate.lower().startswith('jbm-'):
        candidate = candidate[4:]
    candidate = candidate.strip()
    if not candidate or not candidate.isdigit():
        return False, []
    q_objects = [Q(serial_digits__contains=candidate)]
    try:
        q_objects.append(Q(pk=int(candidate)))
    except ValueError:
        pass
    return True, q_objects


@admin_required
def admin_assets_view(request):
    assets = Asset.objects.select_related('category', 'location', 'assigned_to').prefetch_related('photos')

    category_id = request.GET.get('category')
    location_id = request.GET.get('location')
    status = request.GET.get('status')
    search = (request.GET.get('search') or '').strip()

    ALLOWED_PER_PAGE = [12, 25, 50, 75, 100]
    try:
        per_page = int(request.GET.get('per_page', 25))
    except (ValueError, TypeError):
        per_page = 25
    if per_page not in ALLOWED_PER_PAGE:
        per_page = 25

    if category_id:
        assets = assets.filter(category_id=category_id)
    if location_id:
        assets = assets.filter(location_id=location_id)
    if status:
        assets = assets.filter(status=status)
    if search:
        text_q = Q(name__icontains=search) | Q(description__icontains=search)
        needs_annotation, serial_qs = _build_serial_search_filter(search)
        if needs_annotation:
            assets = assets.annotate(
                serial_digits=LPad(
                    Cast('pk', output_field=CharField()),
                    3,
                    Value('0'),
                )
            )
            for sq in serial_qs:
                text_q |= sq
        assets = assets.filter(text_q)

    sort_key, sort_dir = _parse_sort_params(request)
    assets = _apply_sort(assets, sort_key, sort_dir, default_ordering=['-created_at'])

    paginator = Paginator(assets, per_page)
    page = paginator.get_page(request.GET.get('page', 1))

    # Build per-asset map of interested users for the assign modal
    page_asset_ids = [a.id for a in page]
    interests = Interest.objects.filter(asset_id__in=page_asset_ids).select_related('user__profile__branch').order_by('position')
    asset_interests = {}
    for interest in interests:
        asset_interests.setdefault(interest.asset_id, []).append({
            'user_id': interest.user_id,
            'username': interest.user.username,
            'branch': interest.user.profile.branch.name if hasattr(interest.user, 'profile') else '',
            'position': interest.position,
        })

    # All active users for the "Other" assign option
    all_users = User.objects.filter(is_active=True).select_related('profile__branch').order_by('username')
    all_users_list = [
        {
            'id': u.id,
            'username': u.username,
            'branch': u.profile.branch.name if hasattr(u, 'profile') and u.profile.branch else '',
        }
        for u in all_users
    ]

    return render(request, 'admin/assets.html', {
        'assets': page,
        'categories': Category.objects.all(),
        'locations': Location.objects.all(),
        'branches': Branch.objects.prefetch_related('users__user').all(),
        'asset_interests_json': json.dumps(asset_interests),
        'all_users_json': json.dumps(all_users_list),
        'admin_assets_return_url': request.get_full_path(),
        'selected_category': category_id,
        'selected_location': location_id,
        'selected_status': status,
        'status_filter': status,
        'search': search,
        'per_page': per_page,
        'per_page_choices': ALLOWED_PER_PAGE,
        'current_sort': sort_key,
        'current_dir': sort_dir,
    })


@admin_required
def admin_add_asset_view(request):
    clone_source = None
    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.created_by = request.user
            asset.save()
            for i, photo in enumerate(request.FILES.getlist('photos')):
                AssetPhoto.objects.create(asset=asset, image=photo, upload_order=i)
            messages.success(request, f'Asset "{asset.name}" has been added!')
            return redirect('admin_assets')
    else:
        clone_id = request.GET.get('clone')
        initial = None
        if clone_id:
            try:
                clone_pk = int(clone_id)
            except (TypeError, ValueError):
                raise Http404('Asset not found')
            clone_source = get_object_or_404(Asset, pk=clone_pk)
            initial = {
                'name': clone_source.name,
                'description': clone_source.description,
                'category': clone_source.category,
                'location': clone_source.location,
                'condition': clone_source.condition,
                'notes': clone_source.notes,
            }
        form = AssetForm(initial=initial)
    return render(request, 'admin/asset_form.html', {
        'form': form,
        'clone_source': clone_source,
        'categories': Category.objects.all(),
        'locations': Location.objects.all(),
    })


@admin_required
def admin_edit_asset_view(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    next_url = _safe_next_url(
        request,
        request.POST.get('next') if request.method == 'POST' else request.GET.get('next'),
    )
    if request.method == 'POST':
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            for i, photo in enumerate(request.FILES.getlist('photos')):
                order = asset.photos.count() + i
                AssetPhoto.objects.create(asset=asset, image=photo, upload_order=order)
            messages.success(request, f'Asset "{asset.name}" has been updated!')
            return redirect(next_url or 'admin_assets')
    else:
        form = AssetForm(instance=asset)
    return render(request, 'admin/asset_form.html', {
        'form': form,
        'asset': asset,
        'admin_assets_return_url': next_url or reverse('admin_assets'),
        'categories': Category.objects.all(),
        'locations': Location.objects.all(),
        'photos': asset.photos.all(),
    })


@admin_required
@require_POST
def admin_delete_asset_view(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    name = asset.name
    asset.delete()
    messages.success(request, f'Asset "{name}" has been deleted.')
    return redirect('admin_assets')


@admin_required
@require_POST
def admin_delete_photo_view(request, photo_id):
    photo = get_object_or_404(AssetPhoto, pk=photo_id)
    photo.delete()
    return JsonResponse({'success': True})


@admin_required
@require_POST
def admin_make_primary_photo_view(request, photo_id):
    photo = get_object_or_404(AssetPhoto.objects.select_related('asset'), pk=photo_id)

    with transaction.atomic():
        photos = list(
            AssetPhoto.objects.select_for_update()
            .filter(asset=photo.asset)
            .order_by('upload_order', 'uploaded_at', 'pk')
        )
        reordered = [p for p in photos if p.pk == photo.pk] + [p for p in photos if p.pk != photo.pk]
        for order, asset_photo in enumerate(reordered):
            if asset_photo.upload_order != order:
                AssetPhoto.objects.filter(pk=asset_photo.pk).update(upload_order=order)

    return JsonResponse({'success': True})


@admin_required
@require_POST
def admin_reorder_secondary_photo_view(request, photo_id):
    direction = request.POST.get('direction')
    if direction not in {'earlier', 'later'}:
        return JsonResponse({'success': False, 'error': 'Invalid direction.'}, status=400)

    photo = get_object_or_404(AssetPhoto.objects.select_related('asset'), pk=photo_id)

    with transaction.atomic():
        photos = list(
            AssetPhoto.objects.select_for_update()
            .filter(asset=photo.asset)
            .order_by('upload_order', 'uploaded_at', 'pk')
        )
        index = next((i for i, asset_photo in enumerate(photos) if asset_photo.pk == photo.pk), None)
        if index is None:
            return JsonResponse({'success': False, 'error': 'Photo not found.'}, status=404)
        if index == 0:
            return JsonResponse({'success': False, 'error': 'Use Make main to change the main photo.'}, status=400)

        secondary_photos = photos[1:]
        secondary_index = index - 1
        target_index = secondary_index - 1 if direction == 'earlier' else secondary_index + 1
        if 0 <= target_index < len(secondary_photos):
            secondary_photos[secondary_index], secondary_photos[target_index] = (
                secondary_photos[target_index],
                secondary_photos[secondary_index],
            )
            reordered = [photos[0], *secondary_photos]
            for order, asset_photo in enumerate(reordered):
                if asset_photo.upload_order != order:
                    AssetPhoto.objects.filter(pk=asset_photo.pk).update(upload_order=order)

    return JsonResponse({'success': True})


@admin_required
def admin_categories_view(request):
    categories = Category.objects.annotate(asset_count=Count('assets')).order_by('display_order', 'name')
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added!')
            return redirect('admin_categories')
    else:
        form = CategoryForm()
    return render(request, 'admin/categories.html', {'categories': categories, 'form': form})


@admin_required
@require_POST
def admin_delete_category_view(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if category.assets.exists():
        messages.error(request, 'Cannot delete category with existing assets.')
    else:
        category.delete()
        messages.success(request, 'Category deleted.')
    return redirect('admin_categories')


@admin_required
def admin_locations_view(request):
    locations = Location.objects.annotate(asset_count=Count('assets')).order_by('display_order', 'name')
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Location added!')
            return redirect('admin_locations')
    else:
        form = LocationForm()
    return render(request, 'admin/locations.html', {'locations': locations, 'form': form})


@admin_required
@require_POST
def admin_delete_location_view(request, location_id):
    location = get_object_or_404(Location, pk=location_id)
    if location.assets.exists():
        messages.error(request, 'Cannot delete location with existing assets.')
    else:
        location.delete()
        messages.success(request, 'Location deleted.')
    return redirect('admin_locations')


@admin_required
def admin_interests_view(request):
    view_by = request.GET.get('view', 'item')
    if view_by == 'person':
        users = (
            User.objects
            .filter(profile__isnull=False)
            .select_related('profile', 'profile__branch')
            .prefetch_related('interests__asset', 'interests__asset__category', 'interests__asset__location')
            .annotate(interest_count=Count('interests'))
            .order_by('profile__branch__display_order', 'username')
        )
        return render(request, 'admin/interests.html', {'view_by': 'person', 'users': users})

    assets = (
        Asset.objects
        .filter(status='available')
        .select_related('category', 'location')
        .prefetch_related('interests__user')
        .annotate(interest_count=Count('interests'))
        .filter(interest_count__gt=0)
        .order_by('-interest_count')
    )
    return render(request, 'admin/interests.html', {'view_by': 'item', 'assets': assets})


@admin_required
@require_POST
def admin_direct_assign_view(request):
    asset_id = request.POST.get('asset_id')
    user_id = request.POST.get('user_id')

    asset = get_object_or_404(Asset, pk=asset_id)
    user = get_object_or_404(User, pk=user_id)

    with transaction.atomic():
        prev_user = asset.assigned_to
        prev_status = asset.status
        asset.status = 'claimed'
        asset.assigned_to = user
        asset.save()
        AssignmentEvent.objects.create(
            asset=asset,
            actor=request.user,
            event_type='assign',
            from_user=prev_user,
            to_user=user,
            from_status=prev_status,
            to_status='claimed',
        )

    send_assignment_notification(user, asset)

    messages.success(request, f'"{asset.name}" assigned to {user.username}.')
    next_url = _safe_next_url(request, request.POST.get('next'))
    if next_url:
        return redirect(next_url)
    return redirect('admin_assets')


@admin_required
@require_POST
def admin_mark_status_view(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    status = request.POST.get('status')
    if status in ['sold', 'donated', 'available']:
        with transaction.atomic():
            prev_user = asset.assigned_to
            prev_status = asset.status
            if status == 'available':
                asset.assigned_to = None
            asset.status = status
            asset.save()
            event_type = 'unassign' if status == 'available' else 'status_change'
            AssignmentEvent.objects.create(
                asset=asset,
                actor=request.user,
                event_type=event_type,
                from_user=prev_user,
                to_user=asset.assigned_to,
                from_status=prev_status,
                to_status=status,
            )
        messages.success(request, f'"{asset.name}" marked as {status}.')
    next_url = _safe_next_url(request, request.POST.get('next'))
    if next_url:
        return redirect(next_url)
    return redirect('admin_assets')


@admin_required
def admin_users_view(request):
    branch_filter = request.GET.get('branch')
    users = (
        User.objects
        .select_related('profile', 'profile__branch')
        .annotate(
            assigned_count=Count('assigned_assets'),
            interest_count=Count('interests'),
        )
        .order_by('username')
    )
    if branch_filter:
        users = users.filter(profile__branch__code=branch_filter)

    # Build per-user assigned/interested item lists for popup JS
    user_ids = [u.id for u in users]
    assigned_assets = (
        Asset.objects
        .filter(assigned_to_id__in=user_ids)
        .select_related('assigned_to')
        .order_by('pk')
    )
    user_assigned = {}
    for asset in assigned_assets:
        user_assigned.setdefault(asset.assigned_to_id, []).append({
            'id': asset.id,
            'serial': asset.serial_number,
            'name': asset.name,
        })

    interested_assets = (
        Interest.objects
        .filter(user_id__in=user_ids)
        .select_related('asset')
        .order_by('asset__pk')
    )
    user_interested = {}
    for interest in interested_assets:
        user_interested.setdefault(interest.user_id, []).append({
            'id': interest.asset_id,
            'serial': interest.asset.serial_number,
            'name': interest.asset.name,
        })

    return render(request, 'admin/users.html', {
        'users': users,
        'branches': Branch.objects.all(),
        'selected_branch': branch_filter,
        'user_assigned_json': json.dumps(user_assigned),
        'user_interested_json': json.dumps(user_interested),
    })


@admin_required
def admin_reset_password_view(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        form = AdminPasswordResetForm(request.POST)
        if form.is_valid():
            target.set_password(form.cleaned_data['new_password'])
            target.save()
            messages.success(request, f'Password reset for {target.username}.')
            return redirect('admin_users')
    else:
        form = AdminPasswordResetForm()
    return render(request, 'admin/reset_password.html', {'form': form, 'target': target})


@admin_required
@require_POST
def admin_toggle_staff_view(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    target.is_staff = not target.is_staff
    target.save(update_fields=['is_staff'])
    return JsonResponse({'success': True, 'is_staff': target.is_staff})


@admin_required
@require_POST
def admin_toggle_active_view(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
    return JsonResponse({'success': True, 'is_active': target.is_active})


@admin_required
def admin_reports_view(request):
    categories = Category.objects.annotate(
        total=Count('assets'),
        available=Count('assets', filter=Q(assets__status='available')),
        claimed=Count('assets', filter=Q(assets__status='claimed')),
        sold=Count('assets', filter=Q(assets__status='sold')),
        donated=Count('assets', filter=Q(assets__status='donated')),
    )
    locations = Location.objects.annotate(
        total=Count('assets'),
        available=Count('assets', filter=Q(assets__status='available')),
        claimed=Count('assets', filter=Q(assets__status='claimed')),
        sold=Count('assets', filter=Q(assets__status='sold')),
        donated=Count('assets', filter=Q(assets__status='donated')),
    )
    users = (
        User.objects
        .select_related('profile', 'profile__branch')
        .annotate(items_received=Count('assigned_assets'))
        .order_by('profile__branch__display_order', 'username')
    )
    return render(request, 'admin/reports.html', {
        'categories': categories,
        'locations': locations,
        'users': users,
    })


@admin_required
def admin_export_csv_view(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="distribution_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Item #', 'Asset', 'Category', 'Location', 'Status', 'Assigned To', 'Assigned By', 'Assigned On', 'Branch'])

    latest_assign = AssignmentEvent.objects.filter(
        asset=OuterRef('pk'),
        event_type='assign',
    ).order_by('-created_at')

    qs = (
        Asset.objects
        .select_related('category', 'location', 'assigned_to', 'assigned_to__profile', 'assigned_to__profile__branch')
        .annotate(
            assigned_by_username=Subquery(latest_assign.values('actor__username')[:1]),
            assigned_on_date=Subquery(latest_assign.values('created_at')[:1]),
        )
    )
    for asset in qs:
        username = asset.assigned_to.username if asset.assigned_to else ''
        branch_name = ''
        if asset.assigned_to and hasattr(asset.assigned_to, 'profile'):
            branch_name = asset.assigned_to.profile.branch.name
        assigned_by = asset.assigned_by_username or ''
        assigned_on = asset.assigned_on_date.strftime('%Y-%m-%d') if asset.assigned_on_date else ''
        writer.writerow([
            asset.serial_number,
            asset.name,
            asset.category.name,
            asset.location.name,
            asset.get_status_display(),
            username,
            assigned_by,
            assigned_on,
            branch_name,
        ])
    return response


@admin_required
def admin_export_interests_csv_view(request):
    """Export all interest records as CSV with user details and ranking."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="interests_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['User Name', 'Email', 'Branch', 'Item #', 'Asset', 'Interest Ranking'])

    qs = (
        Interest.objects
        .select_related('user', 'user__profile', 'user__profile__branch', 'asset')
        .order_by('user__username', 'position')
    )
    for interest in qs:
        user = interest.user
        branch_name = ''
        if hasattr(user, 'profile'):
            branch_name = user.profile.branch.name
        writer.writerow([
            user.username,
            user.email,
            branch_name,
            interest.asset.serial_number,
            interest.asset.name,
            interest.position,
        ])
    return response


@admin_required
def admin_history_view(request):
    """Chronological log of assignment events; filterable by asset and user."""
    events = (
        AssignmentEvent.objects
        .select_related('actor', 'asset', 'asset__category', 'asset__location', 'from_user', 'to_user')
        .order_by('-created_at')
    )
    asset_id = request.GET.get('asset')
    user_id = request.GET.get('user')
    if asset_id:
        events = events.filter(asset_id=asset_id)
    if user_id:
        events = events.filter(Q(from_user_id=user_id) | Q(to_user_id=user_id))

    paginator = Paginator(events, 50)
    page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'admin/history.html', {
        'events': page,
        'assets': Asset.objects.order_by('name'),
        'users': User.objects.order_by('username'),
        'selected_asset': asset_id,
        'selected_user': user_id,
    })


@admin_required
def admin_disclaimers_view(request):
    welcome = DisclaimerMessage.objects.filter(slug=DisclaimerMessage.SLUG_WELCOME).first()
    claim = DisclaimerMessage.objects.filter(slug=DisclaimerMessage.SLUG_CLAIM_CONFIRMATION).first()

    welcome_form = DisclaimerForm(instance=welcome, prefix='welcome')
    claim_form = DisclaimerForm(instance=claim, prefix='claim')

    if request.method == 'POST':
        target = request.POST.get('target')
        if target == 'welcome' and welcome is not None:
            welcome_form = DisclaimerForm(request.POST, instance=welcome, prefix='welcome')
            if welcome_form.is_valid():
                obj = welcome_form.save(commit=False)
                obj.updated_by = request.user
                obj.save()
                messages.success(request, 'Welcome disclaimer updated.')
                return redirect('admin_disclaimers')
        elif target == 'claim' and claim is not None:
            claim_form = DisclaimerForm(request.POST, instance=claim, prefix='claim')
            if claim_form.is_valid():
                obj = claim_form.save(commit=False)
                obj.updated_by = request.user
                obj.save()
                messages.success(request, 'Claim confirmation disclaimer updated.')
                return redirect('admin_disclaimers')

    return render(request, 'admin/disclaimers.html', {
        'welcome': welcome,
        'claim': claim,
        'welcome_form': welcome_form,
        'claim_form': claim_form,
    })


@login_required
def serve_media_view(request, path):
    """Serve files under MEDIA_ROOT only to authenticated users.

    Rejects path traversal: the resolved real path must remain inside MEDIA_ROOT.
    """
    media_root = os.path.realpath(str(settings.MEDIA_ROOT))
    candidate = os.path.realpath(os.path.join(media_root, path))
    if not (candidate == media_root or candidate.startswith(media_root + os.sep)):
        raise Http404('Not found')
    if not os.path.isfile(candidate):
        raise Http404('Not found')
    content_type, _ = mimetypes.guess_type(candidate)
    return FileResponse(open(candidate, 'rb'), content_type=content_type or 'application/octet-stream')

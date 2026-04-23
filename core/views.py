"""
Views for the Asset Distribution System.
"""

import csv
import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .email import send_assignment_notification
from .forms import (
    AdminPasswordResetForm,
    AssetForm,
    CategoryForm,
    SignupForm,
    StyledLoginForm,
)
from .models import Asset, AssetPhoto, Branch, Category, Interest, UserProfile


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
            auth_login(request, user)
            return redirect('dashboard')
    else:
        form = StyledLoginForm(request)

    return render(request, 'login.html', {'form': form})


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


# ============================================================================
# User views
# ============================================================================

@login_required
def dashboard_view(request):
    user = request.user
    assigned = Asset.objects.filter(assigned_to=user).select_related('category')
    interests = (
        Interest.objects
        .filter(user=user)
        .select_related('asset', 'asset__category')
        .order_by('position')
    )

    cutoff = _previous_login(request)
    recent = (
        Asset.objects
        .filter(created_at__gt=cutoff, status='available')
        .exclude(created_by=user)
        .select_related('category')
        .order_by('-created_at')[:10]
    )

    context = {
        'assigned_items': assigned,
        'interests_preview': interests[:5],
        'interest_count': interests.count(),
        'assigned_count': assigned.count(),
        'recent_items': recent,
        'recent_cutoff': cutoff,
    }
    return render(request, 'dashboard.html', context)


@login_required
def browse_assets_view(request):
    user = request.user
    category_id = request.GET.get('category')
    search = (request.GET.get('search') or '').strip()
    status_filter = request.GET.get('status', 'available')

    assets = Asset.objects.select_related('category', 'assigned_to').prefetch_related('photos')
    if category_id:
        assets = assets.filter(category_id=category_id)
    if search:
        assets = assets.filter(Q(name__icontains=search) | Q(description__icontains=search))
    if status_filter and status_filter != 'all':
        assets = assets.filter(status=status_filter)

    my_interest_asset_ids = set(
        Interest.objects.filter(user=user).values_list('asset_id', flat=True)
    )

    paginator = Paginator(assets, 12)
    page = request.GET.get('page', 1)

    return render(request, 'browse_assets.html', {
        'assets': paginator.get_page(page),
        'categories': Category.objects.annotate(asset_count=Count('assets')),
        'selected_category': category_id,
        'search': search,
        'status_filter': status_filter,
        'my_interest_asset_ids': my_interest_asset_ids,
    })


@login_required
def asset_detail_view(request, asset_id):
    asset = get_object_or_404(
        Asset.objects.select_related('category', 'assigned_to').prefetch_related('photos'),
        pk=asset_id,
    )
    interest = Interest.objects.filter(user=request.user, asset=asset).first()
    return render(request, 'asset_detail.html', {
        'asset': asset,
        'interest': interest,
        'photos': asset.photos.all(),
    })


@login_required
@require_POST
def toggle_interest_view(request, asset_id):
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
        .select_related('asset', 'asset__category')
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
    items = Asset.objects.filter(assigned_to=request.user).select_related('category').prefetch_related('photos')
    return render(request, 'my_items.html', {'items': items})


@login_required
def upload_asset_view(request):
    """Anyone logged in can upload an asset (admin can deactivate accounts to prevent abuse)."""
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
    })


# ============================================================================
# Admin
# ============================================================================

@admin_required
def admin_panel_view(request):
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
    })


@admin_required
def admin_assets_view(request):
    assets = Asset.objects.select_related('category', 'assigned_to').prefetch_related('photos').order_by('-created_at')

    category_id = request.GET.get('category')
    status = request.GET.get('status')
    search = (request.GET.get('search') or '').strip()

    if category_id:
        assets = assets.filter(category_id=category_id)
    if status:
        assets = assets.filter(status=status)
    if search:
        assets = assets.filter(Q(name__icontains=search) | Q(description__icontains=search))

    paginator = Paginator(assets, 20)
    return render(request, 'admin/assets.html', {
        'assets': paginator.get_page(request.GET.get('page', 1)),
        'categories': Category.objects.all(),
        'branches': Branch.objects.prefetch_related('users__user').all(),
        'selected_category': category_id,
        'selected_status': status,
        'search': search,
    })


@admin_required
def admin_add_asset_view(request):
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
        form = AssetForm()
    return render(request, 'admin/asset_form.html', {
        'form': form,
        'categories': Category.objects.all(),
    })


@admin_required
def admin_edit_asset_view(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    if request.method == 'POST':
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            for i, photo in enumerate(request.FILES.getlist('photos')):
                order = asset.photos.count() + i
                AssetPhoto.objects.create(asset=asset, image=photo, upload_order=order)
            messages.success(request, f'Asset "{asset.name}" has been updated!')
            return redirect('admin_assets')
    else:
        form = AssetForm(instance=asset)
    return render(request, 'admin/asset_form.html', {
        'form': form,
        'asset': asset,
        'categories': Category.objects.all(),
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
def admin_interests_view(request):
    view_by = request.GET.get('view', 'item')
    if view_by == 'person':
        users = (
            User.objects
            .filter(profile__isnull=False)
            .select_related('profile', 'profile__branch')
            .prefetch_related('interests__asset', 'interests__asset__category')
            .annotate(interest_count=Count('interests'))
            .order_by('profile__branch__display_order', 'username')
        )
        return render(request, 'admin/interests.html', {'view_by': 'person', 'users': users})

    assets = (
        Asset.objects
        .filter(status='available')
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

    asset.status = 'claimed'
    asset.assigned_to = user
    asset.save()

    send_assignment_notification(user, asset)

    messages.success(request, f'"{asset.name}" assigned to {user.username}.')
    return redirect(request.POST.get('next') or 'admin_assets')


@admin_required
@require_POST
def admin_mark_status_view(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    status = request.POST.get('status')
    if status in ['sold', 'donated', 'available']:
        if status == 'available':
            asset.assigned_to = None
        asset.status = status
        asset.save()
        messages.success(request, f'"{asset.name}" marked as {status}.')
    return redirect('admin_assets')


@admin_required
def admin_users_view(request):
    branch_filter = request.GET.get('branch')
    users = (
        User.objects
        .select_related('profile', 'profile__branch')
        .annotate(assigned_count=Count('assigned_assets'))
        .order_by('username')
    )
    if branch_filter:
        users = users.filter(profile__branch__code=branch_filter)

    return render(request, 'admin/users.html', {
        'users': users,
        'branches': Branch.objects.all(),
        'selected_branch': branch_filter,
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
    users = (
        User.objects
        .select_related('profile', 'profile__branch')
        .annotate(items_received=Count('assigned_assets'))
        .order_by('profile__branch__display_order', 'username')
    )
    return render(request, 'admin/reports.html', {
        'categories': categories,
        'users': users,
    })


@admin_required
def admin_export_csv_view(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="distribution_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Asset', 'Category', 'Status', 'Assigned To', 'Branch'])

    qs = Asset.objects.select_related('category', 'assigned_to', 'assigned_to__profile', 'assigned_to__profile__branch')
    for asset in qs:
        username = asset.assigned_to.username if asset.assigned_to else ''
        branch_name = ''
        if asset.assigned_to and hasattr(asset.assigned_to, 'profile'):
            branch_name = asset.assigned_to.profile.branch.name
        writer.writerow([
            asset.name,
            asset.category.name,
            asset.get_status_display(),
            username,
            branch_name,
        ])
    return response

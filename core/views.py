"""
Views for the Asset Distribution System.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db.models import Q, Count
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator
import random
import csv
from functools import wraps

from .models import (
    Branch, FamilyMember, Category, Asset, AssetPhoto, 
    Interest, LegacySubmission, DistributionState, TurnOrder, SystemSettings
)
from .forms import (
    LoginForm, AdminLoginForm, AssetForm, LegacySubmissionForm,
    CategoryForm, FamilyMemberForm, PasswordChangeForm
)


# ============================================================================
# Decorators for access control
# ============================================================================

def login_required(view_func):
    """Decorator to require family member login."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('member_id'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """Decorator to require admin login."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('is_admin'):
            messages.error(request, 'Admin access required.')
            return redirect('admin_login')
        return view_func(request, *args, **kwargs)
    return wrapper


def upload_permission_required(view_func):
    """Decorator to require upload permission."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get('is_admin'):
            return view_func(request, *args, **kwargs)
        member_id = request.session.get('member_id')
        if member_id:
            member = FamilyMember.objects.filter(pk=member_id, can_upload=True).first()
            if member:
                return view_func(request, *args, **kwargs)
        messages.error(request, 'You do not have permission to upload assets.')
        return redirect('dashboard')
    return wrapper


def get_current_member(request):
    """Get the current logged-in family member."""
    member_id = request.session.get('member_id')
    if member_id:
        return FamilyMember.objects.filter(pk=member_id).first()
    return None


# ============================================================================
# Authentication Views
# ============================================================================

def login_view(request):
    """Family password login."""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password']
            if SystemSettings.check_password('family', password):
                request.session['authenticated'] = True
                return redirect('identity_select')
            else:
                messages.error(request, 'Incorrect password.')
    else:
        form = LoginForm()
    
    return render(request, 'login.html', {'form': form})


def identity_select_view(request):
    """Select family member identity."""
    if not request.session.get('authenticated'):
        return redirect('login')
    
    branches = Branch.objects.prefetch_related('members').all()
    
    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        if member_id:
            member = get_object_or_404(FamilyMember, pk=member_id)
            request.session['member_id'] = member.id
            request.session['member_name'] = member.name
            return redirect('dashboard')
    
    return render(request, 'identity_select.html', {'branches': branches})


def admin_login_view(request):
    """Admin password login."""
    if request.method == 'POST':
        form = AdminLoginForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password']
            if SystemSettings.check_password('admin', password):
                request.session['is_admin'] = True
                request.session['authenticated'] = True
                return redirect('admin_panel')
            else:
                messages.error(request, 'Incorrect admin password.')
    else:
        form = AdminLoginForm()
    
    return render(request, 'admin_login.html', {'form': form})


def logout_view(request):
    """Log out and clear session."""
    request.session.flush()
    return redirect('login')


# ============================================================================
# User Views
# ============================================================================

@login_required
def dashboard_view(request):
    """Main dashboard for logged-in users."""
    member = get_current_member(request)
    state = DistributionState.get_instance()
    
    # Get stats
    assigned_items = Asset.objects.filter(assigned_to=member)
    my_interests = Interest.objects.filter(family_member=member).select_related('asset')
    unavailable_wanted = my_interests.filter(
        Q(asset__status='claimed') | Q(asset__status='sold') | Q(asset__status='donated')
    ).exclude(asset__assigned_to=member)
    
    context = {
        'member': member,
        'state': state,
        'assigned_count': assigned_items.count(),
        'interest_count': my_interests.count(),
        'unavailable_wanted': unavailable_wanted[:5],  # Show up to 5
        'assigned_items': assigned_items[:5],  # Preview
    }
    
    return render(request, 'dashboard.html', context)


@login_required
def browse_assets_view(request):
    """Browse all assets with filtering."""
    member = get_current_member(request)
    
    # Get filter parameters
    category_id = request.GET.get('category')
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', 'available')
    
    # Base queryset
    assets = Asset.objects.select_related('category', 'assigned_to').prefetch_related('photos')
    
    # Apply filters
    if category_id:
        assets = assets.filter(category_id=category_id)
    if search:
        assets = assets.filter(Q(name__icontains=search) | Q(description__icontains=search))
    if status_filter and status_filter != 'all':
        assets = assets.filter(status=status_filter)
    
    # Get user's interests for marking
    my_interest_asset_ids = set(
        Interest.objects.filter(family_member=member).values_list('asset_id', flat=True)
    )
    
    # Pagination
    paginator = Paginator(assets, 12)
    page = request.GET.get('page', 1)
    assets_page = paginator.get_page(page)
    
    categories = Category.objects.annotate(asset_count=Count('assets'))
    
    context = {
        'assets': assets_page,
        'categories': categories,
        'selected_category': category_id,
        'search': search,
        'status_filter': status_filter,
        'my_interest_asset_ids': my_interest_asset_ids,
    }
    
    return render(request, 'browse_assets.html', context)


@login_required
def asset_detail_view(request, asset_id):
    """View single asset details."""
    member = get_current_member(request)
    asset = get_object_or_404(Asset.objects.select_related('category', 'assigned_to').prefetch_related('photos'), pk=asset_id)
    
    # Check if user is interested
    interest = Interest.objects.filter(family_member=member, asset=asset).first()
    
    context = {
        'asset': asset,
        'interest': interest,
        'photos': asset.photos.all(),
    }
    
    return render(request, 'asset_detail.html', context)


@login_required
@require_POST
def toggle_interest_view(request, asset_id):
    """Toggle interest in an asset."""
    member = get_current_member(request)
    asset = get_object_or_404(Asset, pk=asset_id)
    
    if asset.status != 'available':
        return JsonResponse({'success': False, 'error': 'Item is no longer available'})
    
    interest, created = Interest.objects.get_or_create(
        family_member=member,
        asset=asset,
        defaults={'ranking': 999}
    )
    
    if not created:
        interest.delete()
        return JsonResponse({'success': True, 'interested': False})
    
    return JsonResponse({'success': True, 'interested': True})


@login_required
@require_POST
def update_ranking_view(request, interest_id):
    """Update interest ranking."""
    member = get_current_member(request)
    interest = get_object_or_404(Interest, pk=interest_id, family_member=member)
    
    try:
        ranking = int(request.POST.get('ranking', 999))
        interest.ranking = max(1, ranking)
        interest.save()
        return JsonResponse({'success': True})
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid ranking'})


@login_required
def my_interests_view(request):
    """View and rank my interests."""
    member = get_current_member(request)
    interests = Interest.objects.filter(family_member=member).select_related('asset', 'asset__category').prefetch_related('asset__photos').order_by('ranking', 'created_at')
    
    if request.method == 'POST':
        # Bulk update rankings
        for interest in interests:
            new_rank = request.POST.get(f'rank_{interest.id}')
            if new_rank:
                try:
                    interest.ranking = int(new_rank)
                    interest.save()
                except ValueError:
                    pass
        messages.success(request, 'Rankings updated!')
        return redirect('my_interests')
    
    context = {
        'interests': interests,
    }
    
    return render(request, 'my_interests.html', context)


@login_required
def my_items_view(request):
    """View items assigned to me."""
    member = get_current_member(request)
    items = Asset.objects.filter(assigned_to=member).select_related('category').prefetch_related('photos')
    
    context = {
        'items': items,
    }
    
    return render(request, 'my_items.html', context)


@login_required
def legacy_round_view(request):
    """Legacy Priority Round submission."""
    member = get_current_member(request)
    state = DistributionState.get_instance()
    
    if state.current_phase != 'legacy_round':
        messages.info(request, 'The Legacy Priority Round is not currently active.')
        return redirect('dashboard')
    
    # Check for existing submission
    existing = LegacySubmission.objects.filter(family_member=member).first()
    
    if request.method == 'POST':
        form = LegacySubmissionForm(request.POST)
        if form.is_valid():
            submission, _ = LegacySubmission.objects.update_or_create(
                family_member=member,
                defaults={
                    'choice_1': form.cleaned_data['choice_1'],
                    'choice_2': form.cleaned_data.get('choice_2'),
                    'choice_3': form.cleaned_data.get('choice_3'),
                }
            )
            messages.success(request, 'Your Legacy Round choices have been submitted!')
            return redirect('dashboard')
    else:
        initial = {}
        if existing:
            initial = {
                'choice_1': existing.choice_1,
                'choice_2': existing.choice_2,
                'choice_3': existing.choice_3,
            }
        form = LegacySubmissionForm(initial=initial)
    
    context = {
        'form': form,
        'existing': existing,
    }
    
    return render(request, 'legacy_round.html', context)


# ============================================================================
# Asset Upload Views (for permitted users)
# ============================================================================

@login_required
@upload_permission_required
def upload_asset_view(request):
    """Upload a new asset."""
    member = get_current_member(request)
    
    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.created_by = member
            asset.save()
            
            # Handle photo uploads
            photos = request.FILES.getlist('photos')
            for i, photo in enumerate(photos):
                AssetPhoto.objects.create(asset=asset, image=photo, upload_order=i)
            
            messages.success(request, f'Asset "{asset.name}" has been added!')
            return redirect('asset_detail', asset_id=asset.id)
    else:
        form = AssetForm()
    
    context = {
        'form': form,
        'categories': Category.objects.all(),
    }
    
    return render(request, 'upload_asset.html', context)


# ============================================================================
# Admin Views
# ============================================================================

@admin_required
def admin_panel_view(request):
    """Main admin panel."""
    state = DistributionState.get_instance()
    
    stats = {
        'total_assets': Asset.objects.count(),
        'available_assets': Asset.objects.filter(status='available').count(),
        'claimed_assets': Asset.objects.filter(status='claimed').count(),
        'total_interests': Interest.objects.count(),
        'legacy_submissions': LegacySubmission.objects.count(),
        'total_members': FamilyMember.objects.count(),
    }
    
    context = {
        'state': state,
        'stats': stats,
    }
    
    return render(request, 'admin/panel.html', context)


@admin_required
def admin_assets_view(request):
    """Admin asset management."""
    assets = Asset.objects.select_related('category', 'assigned_to').prefetch_related('photos').order_by('-created_at')
    
    # Filtering
    category_id = request.GET.get('category')
    status = request.GET.get('status')
    search = request.GET.get('search', '').strip()
    
    if category_id:
        assets = assets.filter(category_id=category_id)
    if status:
        assets = assets.filter(status=status)
    if search:
        assets = assets.filter(Q(name__icontains=search) | Q(description__icontains=search))
    
    paginator = Paginator(assets, 20)
    page = request.GET.get('page', 1)
    
    context = {
        'assets': paginator.get_page(page),
        'categories': Category.objects.all(),
        'selected_category': category_id,
        'selected_status': status,
        'search': search,
    }
    
    return render(request, 'admin/assets.html', context)


@admin_required
def admin_add_asset_view(request):
    """Admin add new asset."""
    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save()
            
            # Handle photo uploads
            photos = request.FILES.getlist('photos')
            for i, photo in enumerate(photos):
                AssetPhoto.objects.create(asset=asset, image=photo, upload_order=i)
            
            messages.success(request, f'Asset "{asset.name}" has been added!')
            return redirect('admin_assets')
    else:
        form = AssetForm()
    
    context = {
        'form': form,
        'categories': Category.objects.all(),
    }
    
    return render(request, 'admin/asset_form.html', context)


@admin_required
def admin_edit_asset_view(request, asset_id):
    """Admin edit asset."""
    asset = get_object_or_404(Asset, pk=asset_id)
    
    if request.method == 'POST':
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            
            # Handle new photo uploads
            photos = request.FILES.getlist('photos')
            for i, photo in enumerate(photos):
                order = asset.photos.count() + i
                AssetPhoto.objects.create(asset=asset, image=photo, upload_order=order)
            
            messages.success(request, f'Asset "{asset.name}" has been updated!')
            return redirect('admin_assets')
    else:
        form = AssetForm(instance=asset)
    
    context = {
        'form': form,
        'asset': asset,
        'categories': Category.objects.all(),
        'photos': asset.photos.all(),
    }
    
    return render(request, 'admin/asset_form.html', context)


@admin_required
@require_POST
def admin_delete_asset_view(request, asset_id):
    """Admin delete asset."""
    asset = get_object_or_404(Asset, pk=asset_id)
    name = asset.name
    asset.delete()
    messages.success(request, f'Asset "{name}" has been deleted.')
    return redirect('admin_assets')


@admin_required
@require_POST
def admin_delete_photo_view(request, photo_id):
    """Admin delete a photo."""
    photo = get_object_or_404(AssetPhoto, pk=photo_id)
    asset_id = photo.asset.id
    photo.delete()
    return JsonResponse({'success': True})


@admin_required
def admin_categories_view(request):
    """Admin category management."""
    categories = Category.objects.annotate(asset_count=Count('assets')).order_by('display_order', 'name')
    
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added!')
            return redirect('admin_categories')
    else:
        form = CategoryForm()
    
    context = {
        'categories': categories,
        'form': form,
    }
    
    return render(request, 'admin/categories.html', context)


@admin_required
@require_POST
def admin_delete_category_view(request, category_id):
    """Admin delete category."""
    category = get_object_or_404(Category, pk=category_id)
    if category.assets.exists():
        messages.error(request, 'Cannot delete category with existing assets.')
    else:
        category.delete()
        messages.success(request, 'Category deleted.')
    return redirect('admin_categories')


@admin_required
def admin_members_view(request):
    """Admin family member management."""
    branches = Branch.objects.prefetch_related('members').all()
    
    context = {
        'branches': branches,
    }
    
    return render(request, 'admin/members.html', context)


@admin_required
@require_POST
def admin_toggle_upload_permission_view(request, member_id):
    """Toggle upload permission for a member."""
    member = get_object_or_404(FamilyMember, pk=member_id)
    member.can_upload = not member.can_upload
    member.save()
    return JsonResponse({'success': True, 'can_upload': member.can_upload})


@admin_required
def admin_interests_view(request):
    """View all interests."""
    view_by = request.GET.get('view', 'item')
    
    if view_by == 'person':
        members = FamilyMember.objects.prefetch_related(
            'interests__asset', 'interests__asset__category'
        ).annotate(interest_count=Count('interests')).order_by('branch__display_order', 'name')
        context = {
            'view_by': 'person',
            'members': members,
        }
    else:
        assets = Asset.objects.filter(status='available').prefetch_related(
            'interests__family_member'
        ).annotate(interest_count=Count('interests')).filter(interest_count__gt=0).order_by('-interest_count')
        context = {
            'view_by': 'item',
            'assets': assets,
        }
    
    return render(request, 'admin/interests.html', context)


@admin_required
def admin_distribution_view(request):
    """Admin distribution control."""
    state = DistributionState.get_instance()
    categories = Category.objects.all()
    branches = Branch.objects.all()
    
    # Current turn order for active category
    current_turns = None
    if state.current_phase == 'category_distribution' and state.current_category:
        current_turns = TurnOrder.objects.filter(
            category=state.current_category
        ).select_related('family_member', 'assigned_asset').order_by('sequence')
    
    context = {
        'state': state,
        'categories': categories,
        'branches': branches,
        'current_turns': current_turns,
        'members': FamilyMember.objects.all(),
    }
    
    return render(request, 'admin/distribution.html', context)


@admin_required
@require_POST
def admin_set_phase_view(request):
    """Set distribution phase."""
    state = DistributionState.get_instance()
    phase = request.POST.get('phase')
    
    if phase in dict(DistributionState.PHASE_CHOICES):
        state.current_phase = phase
        state.save()
        messages.success(request, f'Phase set to {state.get_current_phase_display()}')
    
    return redirect('admin_distribution')


@admin_required
@require_POST
def admin_set_category_view(request):
    """Set current distribution category."""
    state = DistributionState.get_instance()
    category_id = request.POST.get('category_id')
    
    if category_id:
        category = get_object_or_404(Category, pk=category_id)
        state.current_category = category
        state.save()
        messages.success(request, f'Now distributing: {category.name}')
    
    return redirect('admin_distribution')


@admin_required
@require_POST
def admin_randomize_branches_view(request):
    """Randomize branch order for current category."""
    state = DistributionState.get_instance()
    
    if not state.current_category:
        messages.error(request, 'Please select a category first.')
        return redirect('admin_distribution')
    
    # Randomize branch order
    branch_codes = list(Branch.objects.values_list('code', flat=True))
    random.shuffle(branch_codes)
    state.branch_order = branch_codes
    state.turn_index = 0
    state.save()
    
    # Generate turn order
    generate_turn_order(state.current_category, branch_codes)
    
    messages.success(request, f'Branch order randomized: {" → ".join(branch_codes)}')
    return redirect('admin_distribution')


def generate_turn_order(category, branch_order):
    """Generate the full turn order for a category based on branch order."""
    # Clear existing turn order for this category
    TurnOrder.objects.filter(category=category).delete()
    
    sequence = 0
    
    for branch_code in branch_order:
        branch = Branch.objects.get(code=branch_code)
        
        if branch_code in ['A', 'B']:
            # Father first
            father = branch.get_father()
            if father:
                TurnOrder.objects.create(category=category, sequence=sequence, family_member=father)
                sequence += 1
            
            # Randomize children
            children = list(branch.get_children())
            random.shuffle(children)
            for child in children:
                TurnOrder.objects.create(category=category, sequence=sequence, family_member=child)
                sequence += 1
            
            # Father last
            if father:
                TurnOrder.objects.create(category=category, sequence=sequence, family_member=father)
                sequence += 1
        
        else:  # Branch C - alternating
            children = list(branch.get_children())
            if len(children) >= 2:
                # Alternate to fill equivalent slots (8 picks like other branches)
                for i in range(8):
                    TurnOrder.objects.create(
                        category=category, 
                        sequence=sequence, 
                        family_member=children[i % 2]
                    )
                    sequence += 1


@admin_required
@require_POST
def admin_assign_item_view(request):
    """Assign an item to a member based on turn order."""
    turn_id = request.POST.get('turn_id')
    asset_id = request.POST.get('asset_id')
    
    turn = get_object_or_404(TurnOrder, pk=turn_id)
    
    if asset_id:
        asset = get_object_or_404(Asset, pk=asset_id)
        asset.status = 'claimed'
        asset.assigned_to = turn.family_member
        asset.save()
        
        turn.assigned_asset = asset
        turn.completed = True
        turn.save()
        
        messages.success(request, f'"{asset.name}" assigned to {turn.family_member.name}')
    else:
        # Pass - mark as completed without assignment
        turn.passed = True
        turn.completed = True
        turn.save()
        messages.info(request, f'{turn.family_member.name} passed.')
    
    return redirect('admin_distribution')


@admin_required
@require_POST
def admin_direct_assign_view(request):
    """Directly assign an item outside of turn order."""
    asset_id = request.POST.get('asset_id')
    member_id = request.POST.get('member_id')
    
    asset = get_object_or_404(Asset, pk=asset_id)
    member = get_object_or_404(FamilyMember, pk=member_id)
    
    asset.status = 'claimed'
    asset.assigned_to = member
    asset.save()
    
    messages.success(request, f'"{asset.name}" directly assigned to {member.name}')
    return redirect('admin_assets')


@admin_required
@require_POST
def admin_mark_status_view(request, asset_id):
    """Mark asset status (sold/donated)."""
    asset = get_object_or_404(Asset, pk=asset_id)
    status = request.POST.get('status')
    
    if status in ['sold', 'donated']:
        asset.status = status
        asset.save()
        messages.success(request, f'"{asset.name}" marked as {status}')
    
    return redirect('admin_assets')


@admin_required
def admin_legacy_view(request):
    """View and manage Legacy Round submissions."""
    submissions = LegacySubmission.objects.select_related(
        'family_member', 'choice_1', 'choice_2', 'choice_3'
    ).order_by('family_member__branch__display_order', 'family_member__name')
    
    # Find conflicts (same item as #1 choice)
    choice_1_counts = {}
    for sub in submissions:
        if sub.choice_1:
            if sub.choice_1.id not in choice_1_counts:
                choice_1_counts[sub.choice_1.id] = []
            choice_1_counts[sub.choice_1.id].append(sub.family_member.name)
    
    conflicts = {k: v for k, v in choice_1_counts.items() if len(v) > 1}
    
    context = {
        'submissions': submissions,
        'conflicts': conflicts,
        'total_members': FamilyMember.objects.count(),
    }
    
    return render(request, 'admin/legacy.html', context)


@admin_required
@require_POST
def admin_grant_legacy_view(request):
    """Grant a legacy item to a member."""
    member_id = request.POST.get('member_id')
    asset_id = request.POST.get('asset_id')
    
    member = get_object_or_404(FamilyMember, pk=member_id)
    asset = get_object_or_404(Asset, pk=asset_id)
    
    asset.status = 'claimed'
    asset.assigned_to = member
    asset.save()
    
    messages.success(request, f'Legacy item "{asset.name}" granted to {member.name}')
    return redirect('admin_legacy')


@admin_required
def admin_reports_view(request):
    """Admin reports and exports."""
    # Stats by category
    categories = Category.objects.annotate(
        total=Count('assets'),
        available=Count('assets', filter=Q(assets__status='available')),
        claimed=Count('assets', filter=Q(assets__status='claimed')),
        sold=Count('assets', filter=Q(assets__status='sold')),
        donated=Count('assets', filter=Q(assets__status='donated')),
    )
    
    # Stats by member
    members = FamilyMember.objects.annotate(
        items_received=Count('assigned_assets')
    ).order_by('branch__display_order', '-is_father', 'name')
    
    context = {
        'categories': categories,
        'members': members,
    }
    
    return render(request, 'admin/reports.html', context)


@admin_required
def admin_export_csv_view(request):
    """Export distribution data as CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="distribution_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Asset', 'Category', 'Status', 'Assigned To', 'Branch'])
    
    for asset in Asset.objects.select_related('category', 'assigned_to', 'assigned_to__branch'):
        writer.writerow([
            asset.name,
            asset.category.name,
            asset.get_status_display(),
            asset.assigned_to.name if asset.assigned_to else '',
            asset.assigned_to.branch.name if asset.assigned_to else '',
        ])
    
    return response


@admin_required
def admin_settings_view(request):
    """Admin settings (password changes)."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.POST)
        if form.is_valid():
            password_type = form.cleaned_data['password_type']
            new_password = form.cleaned_data['new_password']
            SystemSettings.set_password(password_type, new_password)
            messages.success(request, f'{password_type.title()} password has been changed.')
            return redirect('admin_settings')
    else:
        form = PasswordChangeForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'admin/settings.html', context)

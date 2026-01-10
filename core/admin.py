"""
Django admin configuration for the Asset Distribution System.
"""

from django.contrib import admin
from .models import (
    Branch, FamilyMember, Category, Asset, AssetPhoto,
    Interest, LegacySubmission, DistributionState, TurnOrder, SystemSettings
)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'display_order']
    ordering = ['display_order']


@admin.register(FamilyMember)
class FamilyMemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'branch', 'is_father', 'can_upload']
    list_filter = ['branch', 'is_father', 'can_upload']
    ordering = ['branch__display_order', '-is_father', 'name']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_order', 'get_asset_count']
    ordering = ['display_order', 'name']


class AssetPhotoInline(admin.TabularInline):
    model = AssetPhoto
    extra = 1


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'status', 'assigned_to', 'created_at']
    list_filter = ['status', 'category']
    search_fields = ['name', 'description']
    inlines = [AssetPhotoInline]


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ['family_member', 'asset', 'ranking', 'created_at']
    list_filter = ['family_member', 'asset__category']
    ordering = ['family_member', 'ranking']


@admin.register(LegacySubmission)
class LegacySubmissionAdmin(admin.ModelAdmin):
    list_display = ['family_member', 'choice_1', 'choice_2', 'choice_3', 'submitted_at']


@admin.register(DistributionState)
class DistributionStateAdmin(admin.ModelAdmin):
    list_display = ['current_phase', 'current_category', 'turn_index']


@admin.register(TurnOrder)
class TurnOrderAdmin(admin.ModelAdmin):
    list_display = ['category', 'sequence', 'family_member', 'completed', 'passed']
    list_filter = ['category', 'completed', 'passed']
    ordering = ['category', 'sequence']


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value']

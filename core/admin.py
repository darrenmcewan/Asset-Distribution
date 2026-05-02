"""
Django admin configuration.
"""

from django.contrib import admin

from .models import (
    Asset,
    AssetComment,
    AssetPhoto,
    AssignmentEvent,
    Branch,
    Category,
    Interest,
    Location,
    UserProfile,
)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'display_order']
    ordering = ['display_order']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'branch']
    list_filter = ['branch']
    search_fields = ['user__username', 'user__email']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_order', 'get_asset_count']
    ordering = ['display_order', 'name']


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_order', 'get_asset_count']
    ordering = ['display_order', 'name']


class AssetPhotoInline(admin.TabularInline):
    model = AssetPhoto
    extra = 1


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'location', 'status', 'assigned_to', 'created_at']
    list_filter = ['status', 'category', 'location']
    search_fields = ['name', 'description']
    inlines = [AssetPhotoInline]


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ['user', 'asset', 'position', 'created_at']
    list_filter = ['user', 'asset__category', 'asset__location']
    ordering = ['user', 'position']


@admin.register(AssignmentEvent)
class AssignmentEventAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'event_type', 'asset', 'actor', 'from_user', 'to_user', 'from_status', 'to_status']
    list_filter = ['event_type']
    search_fields = ['asset__name', 'actor__username', 'to_user__username', 'from_user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at']


@admin.register(AssetComment)
class AssetCommentAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'asset', 'author', 'body']
    search_fields = ['asset__name', 'author__username', 'body']
    ordering = ['-created_at']

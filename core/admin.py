"""
Django admin configuration.
"""

from django.contrib import admin

from .models import Asset, AssetPhoto, Branch, Category, Interest, UserProfile


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
    list_display = ['user', 'asset', 'position', 'created_at']
    list_filter = ['user', 'asset__category']
    ordering = ['user', 'position']

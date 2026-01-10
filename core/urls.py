"""
URL routing for the Asset Distribution System.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('', views.login_view, name='login'),
    path('identity/', views.identity_select_view, name='identity_select'),
    path('admin-login/', views.admin_login_view, name='admin_login'),
    path('logout/', views.logout_view, name='logout'),
    
    # User views
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('assets/', views.browse_assets_view, name='browse_assets'),
    path('assets/<int:asset_id>/', views.asset_detail_view, name='asset_detail'),
    path('assets/<int:asset_id>/toggle-interest/', views.toggle_interest_view, name='toggle_interest'),
    path('interests/', views.my_interests_view, name='my_interests'),
    path('interests/<int:interest_id>/update-ranking/', views.update_ranking_view, name='update_ranking'),
    path('my-items/', views.my_items_view, name='my_items'),
    path('legacy-round/', views.legacy_round_view, name='legacy_round'),
    path('upload/', views.upload_asset_view, name='upload_asset'),
    
    # Admin views
    path('admin/', views.admin_panel_view, name='admin_panel'),
    path('admin/assets/', views.admin_assets_view, name='admin_assets'),
    path('admin/assets/add/', views.admin_add_asset_view, name='admin_add_asset'),
    path('admin/assets/<int:asset_id>/edit/', views.admin_edit_asset_view, name='admin_edit_asset'),
    path('admin/assets/<int:asset_id>/delete/', views.admin_delete_asset_view, name='admin_delete_asset'),
    path('admin/assets/<int:asset_id>/status/', views.admin_mark_status_view, name='admin_mark_status'),
    path('admin/photos/<int:photo_id>/delete/', views.admin_delete_photo_view, name='admin_delete_photo'),
    path('admin/categories/', views.admin_categories_view, name='admin_categories'),
    path('admin/categories/<int:category_id>/delete/', views.admin_delete_category_view, name='admin_delete_category'),
    path('admin/members/', views.admin_members_view, name='admin_members'),
    path('admin/members/<int:member_id>/toggle-upload/', views.admin_toggle_upload_permission_view, name='admin_toggle_upload'),
    path('admin/interests/', views.admin_interests_view, name='admin_interests'),
    path('admin/distribution/', views.admin_distribution_view, name='admin_distribution'),
    path('admin/distribution/set-phase/', views.admin_set_phase_view, name='admin_set_phase'),
    path('admin/distribution/set-category/', views.admin_set_category_view, name='admin_set_category'),
    path('admin/distribution/randomize/', views.admin_randomize_branches_view, name='admin_randomize'),
    path('admin/distribution/assign/', views.admin_assign_item_view, name='admin_assign_item'),
    path('admin/distribution/direct-assign/', views.admin_direct_assign_view, name='admin_direct_assign'),
    path('admin/legacy/', views.admin_legacy_view, name='admin_legacy'),
    path('admin/legacy/grant/', views.admin_grant_legacy_view, name='admin_grant_legacy'),
    path('admin/reports/', views.admin_reports_view, name='admin_reports'),
    path('admin/reports/export/', views.admin_export_csv_view, name='admin_export_csv'),
    path('admin/settings/', views.admin_settings_view, name='admin_settings'),
]

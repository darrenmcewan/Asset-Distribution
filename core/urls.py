"""
URL routing for the core app.
"""

from django.contrib.auth import views as auth_views
from django.urls import path
from django.utils.decorators import method_decorator

try:
    from django_ratelimit.decorators import ratelimit
except ImportError:  # pragma: no cover
    def ratelimit(*args, **kwargs):
        def decorator(view):
            return view
        return decorator

from . import views

urlpatterns = [
    # Auth
    path('', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),

    # Password reset (Django built-in views with custom templates)
    path('password-reset/', method_decorator(
            ratelimit(key='ip', rate='3/15m', block=True, method='POST'), name='dispatch'
        )(auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.txt',
        subject_template_name='registration/password_reset_subject.txt',
        success_url='/password-reset/done/',
    )), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/reset/done/',
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),

    # User views
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('assets/', views.browse_assets_view, name='browse_assets'),
    path('assets/<int:asset_id>/', views.asset_detail_view, name='asset_detail'),
    path('assets/<int:asset_id>/toggle-interest/', views.toggle_interest_view, name='toggle_interest'),
    path('assets/<int:asset_id>/comments/', views.post_comment_view, name='post_comment'),
    path('interests/', views.my_interests_view, name='my_interests'),
    path('interests/reorder/', views.reorder_interests_view, name='reorder_interests'),
    path('my-items/', views.my_items_view, name='my_items'),
    path('upload/', views.upload_asset_view, name='upload_asset'),
    path('disclaimers/welcome/dismiss/', views.dismiss_welcome_disclaimer_view, name='dismiss_welcome_disclaimer'),

    # Admin
    path('admin-panel/', views.admin_panel_view, name='admin_panel'),
    path('admin-panel/assets/', views.admin_assets_view, name='admin_assets'),
    path('admin-panel/assets/add/', views.admin_add_asset_view, name='admin_add_asset'),
    path('admin-panel/assets/<int:asset_id>/edit/', views.admin_edit_asset_view, name='admin_edit_asset'),
    path('admin-panel/assets/<int:asset_id>/delete/', views.admin_delete_asset_view, name='admin_delete_asset'),
    path('admin-panel/assets/<int:asset_id>/status/', views.admin_mark_status_view, name='admin_mark_status'),
    path('admin-panel/photos/<int:photo_id>/delete/', views.admin_delete_photo_view, name='admin_delete_photo'),
    path('admin-panel/categories/', views.admin_categories_view, name='admin_categories'),
    path('admin-panel/categories/<int:category_id>/delete/', views.admin_delete_category_view, name='admin_delete_category'),
    path('admin-panel/locations/', views.admin_locations_view, name='admin_locations'),
    path('admin-panel/locations/<int:location_id>/delete/', views.admin_delete_location_view, name='admin_delete_location'),
    path('admin-panel/interests/', views.admin_interests_view, name='admin_interests'),
    path('admin-panel/assign/', views.admin_direct_assign_view, name='admin_direct_assign'),
    path('admin-panel/users/', views.admin_users_view, name='admin_users'),
    path('admin-panel/users/<int:user_id>/reset-password/', views.admin_reset_password_view, name='admin_reset_password'),
    path('admin-panel/users/<int:user_id>/toggle-staff/', views.admin_toggle_staff_view, name='admin_toggle_staff'),
    path('admin-panel/users/<int:user_id>/toggle-active/', views.admin_toggle_active_view, name='admin_toggle_active'),
    path('admin-panel/reports/', views.admin_reports_view, name='admin_reports'),
    path('admin-panel/reports/export/', views.admin_export_csv_view, name='admin_export_csv'),
    path('admin-panel/history/', views.admin_history_view, name='admin_history'),
    path('admin-panel/comments/<int:comment_id>/delete/', views.admin_delete_comment_view, name='admin_delete_comment'),
    path('admin-panel/disclaimers/', views.admin_disclaimers_view, name='admin_disclaimers'),
]

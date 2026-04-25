"""
URL configuration for asset_distribution project.
"""

from django.contrib import admin
from django.urls import path, include, re_path

from core import views as core_views

urlpatterns = [
    path('django-admin/', admin.site.urls),
    # Authenticated media: must be declared BEFORE the core include so it wins
    # over any catch-alls and is never shadowed by static() in DEBUG mode.
    re_path(r'^media/(?P<path>.+)$', core_views.serve_media_view, name='serve_media'),
    path('', include('core.urls')),
]

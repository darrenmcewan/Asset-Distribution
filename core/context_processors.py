"""
Context processors for the Asset Distribution System.
"""

from .models import SiteSetting


def user_branch(request):
    """Expose the current user's branch (if any) to all templates."""
    branch = None
    if getattr(request, 'user', None) and request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile:
            branch = profile.branch
    return {"user_branch": branch}


def site_settings(request):
    """Expose site-wide settings to all templates."""
    try:
        settings = SiteSetting.get()
        return {"interest_enabled": settings.interest_enabled}
    except Exception:
        return {"interest_enabled": True}

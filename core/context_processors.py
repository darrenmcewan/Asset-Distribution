"""
Context processors for the Asset Distribution System.
"""


def user_branch(request):
    """Expose the current user's branch (if any) to all templates."""
    branch = None
    if getattr(request, 'user', None) and request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile:
            branch = profile.branch
    return {"user_branch": branch}

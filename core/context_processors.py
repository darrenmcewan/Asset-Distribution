"""
Context processors for the Asset Distribution System.
"""

from .models import DistributionState, FamilyMember


def distribution_context(request):
    """Add distribution state and current member to all templates."""
    context = {
        'current_member': None,
        'distribution_state': None,
        'is_admin': request.session.get('is_admin', False),
    }
    
    # Get current member
    member_id = request.session.get('member_id')
    if member_id:
        try:
            context['current_member'] = FamilyMember.objects.select_related('branch').get(pk=member_id)
        except FamilyMember.DoesNotExist:
            pass
    
    # Get distribution state
    try:
        context['distribution_state'] = DistributionState.get_instance()
    except Exception:
        pass
    
    return context

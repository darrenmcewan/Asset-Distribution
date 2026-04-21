"""
Email helpers. All sends are best-effort: failure logs a warning and never raises.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_assignment_notification(user, asset):
    """Notify a user that an item has been assigned to them."""
    if not user.email:
        logger.warning('User %s has no email; skipping assignment notification.', user.username)
        return False

    subject = f'You have been assigned: {asset.name}'
    body = render_to_string('email/assignment_notification.txt', {
        'user': user,
        'asset': asset,
    })

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[user.email],
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.warning('Failed to send assignment notification to %s: %s', user.email, exc)
        return False

"""
WSGI config for asset_distribution project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asset_distribution.settings')

application = get_wsgi_application()

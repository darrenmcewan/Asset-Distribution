"""
Database models for the Asset Distribution System.
"""

import logging
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models
from django.db.models import Max
from django.db.models.signals import post_delete
from django.dispatch import receiver
from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()

logger = logging.getLogger(__name__)


class Branch(models.Model):
    """Represents a family branch (Lynn, Richard, or Rob)."""
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=1, unique=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order']
        verbose_name_plural = 'Branches'

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """Profile attached to each Django User. Holds the branch association."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='users')
    welcome_disclaimer_dismissed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} ({self.branch.name})"


class Category(models.Model):
    """Asset category."""
    name = models.CharField(max_length=100, unique=True)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def get_asset_count(self):
        return self.assets.count()

    def get_available_count(self):
        return self.assets.filter(status='available').count()


class Location(models.Model):
    """Physical location where an asset was found or stored."""
    name = models.CharField(max_length=100, unique=True)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def get_asset_count(self):
        return self.assets.count()

    def get_available_count(self):
        return self.assets.filter(status='available').count()


class Asset(models.Model):
    """An item in the estate to be distributed."""
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('claimed', 'Claimed'),
        ('sold', 'Sold'),
        ('donated', 'Donated'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='assets')
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='assets')
    condition = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_assets'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_assets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category__display_order', 'location__display_order', 'name']

    def __str__(self):
        return f"{self.name} ({self.category.name}, {self.location.name})"

    def get_primary_photo(self):
        return self.photos.first()

    def get_interest_count(self):
        return self.interests.count()

    def get_interested_users(self):
        return Interest.objects.filter(asset=self).select_related('user').order_by('position')

    @property
    def serial_number(self):
        """Human-friendly serial number derived from the auto-increment primary key.

        Format: ``JBM-001``, ``JBM-002``, ... Pads to 3 digits and grows naturally
        beyond 999 (e.g. ``JBM-1000``).
        """
        if self.pk is None:
            return ''
        return f'JBM-{self.pk:03d}'


class AssetPhoto(models.Model):
    """Photo attached to an asset."""
    MAX_DIMENSION = 1200
    JPEG_QUALITY = 75

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='assets/')
    upload_order = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['upload_order', 'uploaded_at']

    def __str__(self):
        return f"Photo for {self.asset.name}"

    def save(self, *args, **kwargs):
        is_new_upload = (
            self.image
            and hasattr(self.image, '_committed')
            and not self.image._committed
        )
        if is_new_upload:
            # Read the entire file into memory upfront so we never depend
            # on the FieldFile's internal state after PIL touches it.
            self.image.open()
            raw_data = self.image.read()
            original_name = self.image.name

            try:
                buf = BytesIO(raw_data)
                img = Image.open(buf)
                img.load()  # force full decode before we close buf

                # Strip EXIF by copying pixel data to a clean image
                clean = Image.new(img.mode, img.size)
                clean.putdata(list(img.getdata()))

                # Convert to RGB (handles PNG/RGBA transparency)
                clean = clean.convert('RGB')

                # Resize to fit within MAX_DIMENSION, preserving aspect ratio
                clean.thumbnail((self.MAX_DIMENSION, self.MAX_DIMENSION))

                buffer = BytesIO()
                clean.save(buffer, format='JPEG', quality=self.JPEG_QUALITY, optimize=True)
                buffer.seek(0)

                name = original_name.rsplit('.', 1)[0] + '.jpg'
                self.image = InMemoryUploadedFile(
                    buffer, 'image', name, 'image/jpeg', buffer.getbuffer().nbytes, None,
                )
            except Exception:
                magic = raw_data[:16] if raw_data else b''
                logger.exception(
                    'Failed to process image (size=%d, magic=%s), saving original',
                    len(raw_data), magic.hex(),
                )
                # Replace self.image with a fresh InMemoryUploadedFile from the
                # raw bytes so we don't depend on the original file's state.
                fallback_buf = BytesIO(raw_data)
                content_type = 'image/png' if raw_data[:4] == b'\x89PNG' else 'application/octet-stream'
                self.image = InMemoryUploadedFile(
                    fallback_buf, 'image', original_name, content_type, len(raw_data), None,
                )

        super().save(*args, **kwargs)


@receiver(post_delete, sender=AssetPhoto)
def delete_photo_file(sender, instance, **kwargs):
    """Remove the image file from disk when the AssetPhoto record is deleted."""
    if instance.image:
        try:
            instance.image.delete(save=False)
        except Exception:
            logger.exception('Failed to delete file for AssetPhoto %s', instance.pk)


class Interest(models.Model):
    """Tracks a user's interest in an asset, with strict position 1..N per user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interests')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='interests')
    position = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ('user', 'asset'),
            ('user', 'position'),
        ]
        ordering = ['position', 'created_at']

    def __str__(self):
        return f"{self.user.username} wants {self.asset.name} (position: {self.position})"

    @classmethod
    def next_position_for(cls, user):
        """Return the next position to use when appending a new interest for a user."""
        last = cls.objects.filter(user=user).aggregate(Max('position'))['position__max']
        return (last or 0) + 1


class AssignmentEvent(models.Model):
    """Audit-log row for every admin action that changes an asset's assignment or status."""
    EVENT_TYPES = [
        ('assign', 'Assign'),
        ('unassign', 'Unassign'),
        ('status_change', 'Status Change'),
    ]

    asset = models.ForeignKey(
        Asset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignment_events_performed',
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    from_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignment_events_from',
    )
    to_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignment_events_to',
    )
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['asset', '-created_at']),
        ]

    def __str__(self):
        actor = self.actor.username if self.actor else 'system'
        asset = self.asset.name if self.asset else '(deleted asset)'
        return f'{actor} {self.event_type} {asset} @ {self.created_at:%Y-%m-%d %H:%M}'


class AssetComment(models.Model):
    """A plain-text comment posted by a user on an asset."""
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment by {self.author.username} on {self.asset.name}'


class DisclaimerMessage(models.Model):
    """Admin-editable disclaimer messages, keyed by slug."""
    SLUG_WELCOME = 'welcome'
    SLUG_CLAIM_CONFIRMATION = 'claim_confirmation'
    SLUG_CHOICES = [
        (SLUG_WELCOME, 'Welcome'),
        (SLUG_CLAIM_CONFIRMATION, 'Claim Confirmation'),
    ]

    # Allow-list for sanitized HTML output of the disclaimer body.
    ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a', 'h2', 'h3']
    ALLOWED_ATTRIBUTES = {'a': ['href', 'title', 'rel', 'target']}

    slug = models.CharField(max_length=32, unique=True, choices=SLUG_CHOICES)
    title = models.CharField(max_length=200)
    body = models.TextField(help_text='Markdown supported. A safe subset of HTML is rendered.')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='disclaimer_edits',
    )

    def __str__(self):
        return f'{self.get_slug_display()} disclaimer'

    @property
    def body_html(self):
        """Render the body as Markdown then sanitize with the allow-list."""
        try:
            import bleach
            import markdown as md
        except ImportError:  # pragma: no cover - dependencies are required at runtime
            return self.body
        rendered = md.markdown(self.body or '', extensions=['extra', 'sane_lists'])
        cleaned = bleach.clean(
            rendered,
            tags=self.ALLOWED_TAGS,
            attributes=self.ALLOWED_ATTRIBUTES,
            strip=True,
        )
        return bleach.linkify(cleaned)

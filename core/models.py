"""
Database models for the Asset Distribution System.
"""

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Max


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
        ordering = ['category__display_order', 'name']

    def __str__(self):
        return f"{self.name} ({self.category.name})"

    def get_primary_photo(self):
        return self.photos.first()

    def get_interest_count(self):
        return self.interests.count()

    def get_interested_users(self):
        return Interest.objects.filter(asset=self).select_related('user').order_by('position')


class AssetPhoto(models.Model):
    """Photo attached to an asset."""
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='assets/')
    upload_order = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['upload_order', 'uploaded_at']

    def __str__(self):
        return f"Photo for {self.asset.name}"


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

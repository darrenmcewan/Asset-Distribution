"""
Database models for the Asset Distribution System.
"""

from django.db import models
from django.utils import timezone
import hashlib


class Branch(models.Model):
    """Represents a family branch (A, B, or C)."""
    name = models.CharField(max_length=50)  # e.g., "Branch A (Lynn)"
    code = models.CharField(max_length=1, unique=True)  # A, B, or C
    display_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['display_order']
        verbose_name_plural = 'Branches'
    
    def __str__(self):
        return self.name
    
    def get_father(self):
        """Returns the father of this branch, or None for Branch C."""
        return self.members.filter(is_father=True).first()
    
    def get_children(self):
        """Returns non-father members of this branch."""
        return self.members.filter(is_father=False).order_by('display_order')


class FamilyMember(models.Model):
    """Represents a family member who can participate in distribution."""
    name = models.CharField(max_length=100)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='members')
    is_father = models.BooleanField(default=False)
    can_upload = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['branch__display_order', '-is_father', 'display_order']
    
    def __str__(self):
        return f"{self.name} ({self.branch.code})"
    
    def get_assigned_items(self):
        """Returns all items assigned to this member."""
        return Asset.objects.filter(assigned_to=self)
    
    def get_interests(self):
        """Returns all interests for this member."""
        return self.interests.all().order_by('ranking', 'created_at')


class Category(models.Model):
    """Asset category (dynamic, created as needed)."""
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
        FamilyMember, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_assets'
    )
    created_by = models.ForeignKey(
        FamilyMember,
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
        """Returns the first photo for this asset."""
        return self.photos.first()
    
    def get_interest_count(self):
        """Returns number of people interested in this item."""
        return self.interests.count()
    
    def get_interested_members(self):
        """Returns all members interested in this item, ordered by ranking."""
        return Interest.objects.filter(asset=self).select_related('family_member').order_by('ranking')


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
    """Tracks a family member's interest in an asset."""
    family_member = models.ForeignKey(FamilyMember, on_delete=models.CASCADE, related_name='interests')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='interests')
    ranking = models.IntegerField(default=999)  # Lower = higher priority
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['family_member', 'asset']
        ordering = ['ranking', 'created_at']
    
    def __str__(self):
        return f"{self.family_member.name} wants {self.asset.name} (rank: {self.ranking})"


class LegacySubmission(models.Model):
    """Legacy Priority Round submission - Top 3 choices."""
    family_member = models.OneToOneField(
        FamilyMember, 
        on_delete=models.CASCADE, 
        related_name='legacy_submission'
    )
    choice_1 = models.ForeignKey(
        Asset, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='legacy_choice_1'
    )
    choice_2 = models.ForeignKey(
        Asset, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='legacy_choice_2'
    )
    choice_3 = models.ForeignKey(
        Asset, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='legacy_choice_3'
    )
    submitted_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Legacy submission by {self.family_member.name}"


class DistributionState(models.Model):
    """Singleton model to track the current state of distribution."""
    PHASE_CHOICES = [
        ('pre_distribution', 'Pre-Distribution'),
        ('legacy_round', 'Legacy Priority Round'),
        ('category_distribution', 'Category Distribution'),
        ('completed', 'Completed'),
    ]
    
    current_phase = models.CharField(max_length=30, choices=PHASE_CHOICES, default='pre_distribution')
    current_category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    branch_order = models.JSONField(default=list)  # e.g., ['B', 'A', 'C']
    turn_index = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Distribution State: {self.get_current_phase_display()}"
    
    @classmethod
    def get_instance(cls):
        """Returns the singleton instance, creating if necessary."""
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


class TurnOrder(models.Model):
    """Tracks turn order for a specific category distribution."""
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='turn_orders')
    sequence = models.IntegerField()
    family_member = models.ForeignKey(FamilyMember, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    assigned_asset = models.ForeignKey(
        Asset, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    passed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['category', 'sequence']
        unique_together = ['category', 'sequence']
    
    def __str__(self):
        status = "✓" if self.completed else "○"
        return f"{status} {self.sequence}. {self.family_member.name} - {self.category.name}"


class SystemSettings(models.Model):
    """Key-value store for system settings like passwords."""
    key = models.CharField(max_length=50, unique=True)
    value = models.TextField()
    
    class Meta:
        verbose_name_plural = 'System Settings'
    
    def __str__(self):
        return self.key
    
    @classmethod
    def get_value(cls, key, default=None):
        """Get a setting value by key."""
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_value(cls, key, value):
        """Set a setting value."""
        obj, _ = cls.objects.update_or_create(key=key, defaults={'value': value})
        return obj
    
    @classmethod
    def check_password(cls, password_type, password):
        """Check if password matches (password_type: 'family' or 'admin')."""
        stored = cls.get_value(f'{password_type}_password_hash')
        if not stored:
            return False
        return stored == hashlib.sha256(password.encode()).hexdigest()
    
    @classmethod
    def set_password(cls, password_type, password):
        """Set a password (password_type: 'family' or 'admin')."""
        hashed = hashlib.sha256(password.encode()).hexdigest()
        cls.set_value(f'{password_type}_password_hash', hashed)

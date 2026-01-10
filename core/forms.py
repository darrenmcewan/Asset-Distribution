"""
Forms for the Asset Distribution System.
"""

from django import forms
from django.forms.widgets import ClearableFileInput
from .models import Asset, Category, AssetPhoto, Interest, LegacySubmission, FamilyMember


class MultipleFileInput(forms.ClearableFileInput):
    """Custom widget to allow multiple file uploads."""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Custom field to handle multiple file uploads."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class LoginForm(forms.Form):
    """Form for family password login."""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter family password',
            'autofocus': True
        }),
        label='Family Password'
    )


class AdminLoginForm(forms.Form):
    """Form for admin password login."""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter admin password',
            'autofocus': True
        }),
        label='Admin Password'
    )


class AssetForm(forms.ModelForm):
    """Form for creating/editing assets."""
    new_category = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Or enter new category name'
        }),
        label='New Category'
    )
    
    class Meta:
        model = Asset
        fields = ['name', 'description', 'category', 'condition', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Item name'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'placeholder': 'Description of the item'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'condition': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Excellent, Good, Fair'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Special notes or history'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False
        self.fields['category'].empty_label = "Select existing category..."
    
    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        new_category = cleaned_data.get('new_category', '').strip()
        
        if not category and not new_category:
            raise forms.ValidationError('Please select an existing category or enter a new one.')
        
        if new_category:
            # Create new category if it doesn't exist
            cat, created = Category.objects.get_or_create(
                name__iexact=new_category,
                defaults={'name': new_category}
            )
            cleaned_data['category'] = cat
        
        return cleaned_data


class AssetPhotoForm(forms.Form):
    """Form for uploading photos."""
    photos = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'class': 'form-input',
            'accept': 'image/*'
        }),
        required=False
    )


class MultiplePhotoForm(forms.Form):
    """Form for handling multiple photo uploads."""
    photos = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'class': 'form-input',
            'accept': 'image/*'
        }),
        required=False
    )


class InterestRankingForm(forms.Form):
    """Form for ranking interests."""
    def __init__(self, *args, family_member=None, **kwargs):
        super().__init__(*args, **kwargs)
        if family_member:
            interests = Interest.objects.filter(family_member=family_member).select_related('asset')
            for interest in interests:
                self.fields[f'rank_{interest.id}'] = forms.IntegerField(
                    initial=interest.ranking,
                    min_value=1,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-input rank-input',
                        'style': 'width: 60px;'
                    })
                )


class LegacySubmissionForm(forms.Form):
    """Form for Legacy Priority Round submission."""
    choice_1 = forms.ModelChoiceField(
        queryset=Asset.objects.filter(status='available'),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='#1 Choice (Most Wanted)'
    )
    choice_2 = forms.ModelChoiceField(
        queryset=Asset.objects.filter(status='available'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='#2 Choice'
    )
    choice_3 = forms.ModelChoiceField(
        queryset=Asset.objects.filter(status='available'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='#3 Choice'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        available_assets = Asset.objects.filter(status='available').order_by('category__name', 'name')
        self.fields['choice_1'].queryset = available_assets
        self.fields['choice_2'].queryset = available_assets
        self.fields['choice_3'].queryset = available_assets
        
        self.fields['choice_1'].empty_label = "Select your #1 choice..."
        self.fields['choice_2'].empty_label = "Select your #2 choice (optional)..."
        self.fields['choice_3'].empty_label = "Select your #3 choice (optional)..."
    
    def clean(self):
        cleaned_data = super().clean()
        choices = [
            cleaned_data.get('choice_1'),
            cleaned_data.get('choice_2'),
            cleaned_data.get('choice_3')
        ]
        
        # Remove None values for duplicate checking
        selected = [c for c in choices if c is not None]
        
        if len(selected) != len(set(selected)):
            raise forms.ValidationError('You cannot select the same item more than once.')
        
        return cleaned_data


class CategoryForm(forms.ModelForm):
    """Form for creating/editing categories."""
    class Meta:
        model = Category
        fields = ['name', 'display_order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Category name'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-input', 'style': 'width: 80px;'}),
        }


class FamilyMemberForm(forms.ModelForm):
    """Form for editing family member settings."""
    class Meta:
        model = FamilyMember
        fields = ['name', 'can_upload']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'can_upload': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class PasswordChangeForm(forms.Form):
    """Form for changing passwords."""
    password_type = forms.ChoiceField(
        choices=[('family', 'Family Password'), ('admin', 'Admin Password')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'New password'}),
        min_length=4
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm password'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError('Passwords do not match.')
        
        return cleaned_data

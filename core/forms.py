"""
Forms for the Asset Distribution System.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from .models import Asset, AssetComment, Category, Branch, UserProfile


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return single_file_clean(data, initial)


class StyledLoginForm(AuthenticationForm):
    """Login form styled to match the app."""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Username',
            'autofocus': True,
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Password',
        }),
    )


class SignupForm(UserCreationForm):
    """Signup form gated by an invite code, requires branch selection."""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'you@example.com'}),
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label='Select your branch...',
    )
    invite_code = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Invite code',
            'autocomplete': 'off',
        }),
        help_text='Ask a family member for the invite code.',
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'branch', 'invite_code')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Username'}),
        }

    def __init__(self, *args, expected_invite_code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._expected_invite_code = expected_invite_code
        for fname in ('password1', 'password2'):
            self.fields[fname].widget.attrs.update({'class': 'form-input'})
        self.fields['username'].widget.attrs.update({'class': 'form-input'})

    def clean_invite_code(self):
        code = self.cleaned_data.get('invite_code', '')
        if self._expected_invite_code and code != self._expected_invite_code:
            raise forms.ValidationError('Invalid invite code.')
        return code

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            UserProfile.objects.create(user=user, branch=self.cleaned_data['branch'])
        return user


class AdminPasswordResetForm(forms.Form):
    """Form for an admin to set a temporary password for a user."""
    new_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'New temporary password'}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm password'}),
    )

    def clean(self):
        cleaned = super().clean()
        new_password = cleaned.get('new_password')
        confirm_password = cleaned.get('confirm_password')
        if new_password and confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError('Passwords do not match.')
            try:
                validate_password(new_password)
            except forms.ValidationError as exc:
                self.add_error('new_password', exc)
        return cleaned


class AssetForm(forms.ModelForm):
    """Form for creating/editing assets."""
    new_category = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Or enter new category name',
        }),
        label='New Category',
    )

    class Meta:
        model = Asset
        fields = ['name', 'description', 'category', 'condition', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Item name'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'condition': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Excellent, Good, Fair'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False
        self.fields['category'].empty_label = 'Select existing category...'

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get('category')
        new_category = (cleaned.get('new_category') or '').strip()
        if not category and not new_category:
            raise forms.ValidationError('Please select an existing category or enter a new one.')
        if new_category:
            cat, _ = Category.objects.get_or_create(
                name__iexact=new_category,
                defaults={'name': new_category},
            )
            cleaned['category'] = cat
        return cleaned


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'display_order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Category name'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-input', 'style': 'width: 80px;'}),
        }


class CommentForm(forms.ModelForm):
    """Plain-text comment on an asset."""
    class Meta:
        model = AssetComment
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Share why this matters to you...',
                'maxlength': 2000,
            }),
        }
        labels = {'body': ''}

    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        if not body:
            raise forms.ValidationError('Comment cannot be empty.')
        return body

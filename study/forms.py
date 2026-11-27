from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import Permission, User
from django.contrib.auth.password_validation import validate_password

from .models import StudyPeriod

DOCUMENT_PERMISSIONS = ['add_studydocument', 'change_studydocument', 'delete_studydocument']
ROLE_CHOICES = [('staff', 'Study staff'), ('admin', 'Administrator')]


class StudyPeriodForm(forms.ModelForm):
    class Meta:
        model = StudyPeriod
        fields = ['number', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
        help_texts = {'number': '1 to 8. Each period lasts about 3 months.'}


class UserForm(forms.ModelForm):
    """Add or edit a study user. Everyone here is staff (they can open the study pages); an administrator
    can also manage users and the admin. "Manage documents" lets them upload, replace and delete in Resources."""

    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect(attrs={'class': 'radio'}))
    manage_documents = forms.BooleanField(required=False, label='Can upload, replace and delete documents in Resources')
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput, strip=False, required=False)
    password2 = forms.CharField(label='Repeat the password', widget=forms.PasswordInput, strip=False, required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        labels = {'is_active': 'Account active (can log in)'}
        help_texts = {'is_active': 'Untick to stop someone logging in. Their history is kept.'}

    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user
        self.fields['email'].required = True
        user = self.instance
        if user.pk:
            del self.fields['password1'], self.fields['password2']   # changed on its own page
            self.initial['role'] = 'admin' if user.is_superuser else 'staff'
            self.initial['manage_documents'] = user.is_superuser or user.user_permissions.filter(
                codename__in=DOCUMENT_PERMISSIONS).count() == len(DOCUMENT_PERMISSIONS)
        else:
            self.fields['password1'].required = self.fields['password2'].required = True
            self.initial.setdefault('role', 'staff')
            self.initial.setdefault('is_active', True)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.exclude(pk=self.instance.pk).filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean(self):
        data = super().clean()
        if self.instance.pk and self.instance == self.acting_user:
            if data.get('role') != 'admin' or not data.get('is_active'):
                raise forms.ValidationError('You cannot remove your own administrator role or deactivate yourself.')
        if 'password1' in self.fields and data.get('password1'):
            if data['password1'] != data.get('password2'):
                self.add_error('password2', 'The two passwords do not match.')
            else:
                try:
                    validate_password(data['password1'], self.instance)
                except forms.ValidationError as error:
                    self.add_error('password1', error)
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = self.cleaned_data['role'] == 'admin'
        if 'password1' in self.fields:
            user.set_password(self.cleaned_data['password1'])
        user.save()
        permissions = Permission.objects.filter(content_type__app_label='resources', codename__in=DOCUMENT_PERMISSIONS)
        if self.cleaned_data['manage_documents']:
            user.user_permissions.add(*permissions)
        else:
            user.user_permissions.remove(*permissions)
        return user


class AdminSetPasswordForm(SetPasswordForm):
    """Set a new password for someone else (they should change it after logging in)."""

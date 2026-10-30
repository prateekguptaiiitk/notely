from django import forms
from django.contrib.auth.models import User


class AccessLoginForm(forms.Form):
    username = forms.CharField(max_length=150, strip=True)
    access_code = forms.CharField(max_length=12, widget=forms.PasswordInput)


class NotelyUserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "is_active")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_unusable_password()
        if commit:
            user.save()
        return user

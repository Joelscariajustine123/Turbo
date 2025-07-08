from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'placeholder': 'test@saberali.co',
        'class': 'form-input'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': '**********',
        'class': 'form-input'
    }))

class SignupForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'password1', 'password2']


class EditRiderForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'phone']
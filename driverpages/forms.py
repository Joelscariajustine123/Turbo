from django import forms
from account.models import CustomUser
from .models import DriverProfile

class DriverProfileForm(forms.ModelForm):
    full_name = forms.CharField(max_length=100)
    phone = forms.CharField(max_length=10)
    email = forms.EmailField()

    class Meta:
        model = DriverProfile
        fields = ['license_number', 'vehicle_info', 'availability_status', 'profile_photo']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(DriverProfileForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['full_name'].initial = user.full_name
            self.fields['phone'].initial = user.phone
            self.fields['email'].initial = user.email

    def save(self, commit=True):
        driver = super().save(commit=False)
        if commit:
            driver.save()
            # Update user info
            user = driver.user
            user.full_name = self.cleaned_data['full_name']
            user.phone = self.cleaned_data['phone']
            user.email = self.cleaned_data['email']
            user.save()
        return driver

from django import forms
from .models import LeadRoutingSettings, WebhookSettings, UserProfile
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class LeadRoutingSettingsForm(forms.ModelForm):
    class Meta:
        model = LeadRoutingSettings
        fields = [
            'send_non_spam_to_inbox',
            'send_spam_to_inbox',
            'non_spam_subject',
            'spam_subject',
            'notification_email',
        ]
        widgets = {
            'send_non_spam_to_inbox': forms.CheckboxInput(),
            'send_spam_to_inbox': forms.CheckboxInput(),
            'non_spam_subject': forms.TextInput(attrs={'class': 'form-control'}),
            'spam_subject': forms.TextInput(attrs={'class': 'form-control'}),
            'notification_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class EmailUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }

class WebhookSettingsForm(forms.ModelForm):
    class Meta:
        model = WebhookSettings
        fields = ['webhook_url', 'send_non_spam', 'send_spam']
        widgets = {
            'webhook_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://your-webhook-url.com/'}),
            'send_non_spam': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'send_spam': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class GHLApiKeyForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['ghl_api_key']
        widgets = {
            'ghl_api_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your GoHighLevel API key'}),
        } 
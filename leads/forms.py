from django import forms
from .models import LeadRoutingSettings

class LeadRoutingSettingsForm(forms.ModelForm):
    class Meta:
        model = LeadRoutingSettings
        fields = ['send_to_gmail', 'spam_labeling_enabled', 'good_lead_subject', 'spam_lead_subject']
        widgets = {
            'send_to_gmail': forms.CheckboxInput(),
            'spam_labeling_enabled': forms.CheckboxInput(),
            'good_lead_subject': forms.TextInput(attrs={'class': 'form-control'}),
            'spam_lead_subject': forms.TextInput(attrs={'class': 'form-control'}),
        } 
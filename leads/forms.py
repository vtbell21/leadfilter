from django import forms
from .models import LeadRoutingSettings

class LeadRoutingSettingsForm(forms.ModelForm):
    class Meta:
        model = LeadRoutingSettings
        fields = ['send_to_gmail', 'spam_labeling_enabled']
        widgets = {
            'send_to_gmail': forms.CheckboxInput(),
            'spam_labeling_enabled': forms.CheckboxInput(),
        } 
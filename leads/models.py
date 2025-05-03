from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .hubspot_utils import create_hubspot_contact

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    hubspot_access_token = models.TextField(blank=True, null=True)
    hubspot_refresh_token = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        # If the user already exists, ensure they have a profile
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Get or create the profile before saving
    profile, created = UserProfile.objects.get_or_create(user=instance)
    profile.save()

# Create your models here.

class FacebookLead(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leads', null=True, blank=True)
    leadgen_id = models.CharField(max_length=100, unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField(null=True, blank=True)
    custom_fields = models.JSONField(default=dict)
    gpt_score = models.FloatField(default=0.0)
    gpt_reason = models.TextField(blank=True)
    total_score = models.FloatField(default=0.0)
    is_spam = models.BooleanField(default=False)
    is_valid_email = models.BooleanField(default=False)
    is_valid_phone = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.leadgen_id})"

    class Meta:
        ordering = ['-received_at']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # If this is a new lead and it's not spam, send to HubSpot
        if is_new and not self.is_spam and self.user and hasattr(self.user, 'hubspot_access_token'):
            create_hubspot_contact(self.user, self)

class FacebookPageConnection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='facebook_pages')
    page_id = models.CharField(max_length=100, unique=True)
    page_name = models.CharField(max_length=255)
    page_access_token = models.TextField()
    connected_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.page_name} ({self.page_id})"

    class Meta:
        ordering = ['-connected_at']
        verbose_name = 'Facebook Page Connection'
        verbose_name_plural = 'Facebook Page Connections'

class GmailCredentials(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gmail_credentials')
    token = models.TextField()
    refresh_token = models.TextField()
    token_uri = models.CharField(max_length=255)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    scopes = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"GmailCredentials for {self.user.username}"

class LeadRoutingSettings(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lead_routing_settings')
    send_to_gmail = models.BooleanField(default=False)
    spam_labeling_enabled = models.BooleanField(default=True)
    good_lead_subject = models.CharField(max_length=100, default="New Lead")
    spam_lead_subject = models.CharField(max_length=100, default="Spam Lead")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"LeadRoutingSettings for {self.user.username}"

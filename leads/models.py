from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .hubspot_utils import create_hubspot_contact
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import json
import logging

logger = logging.getLogger(__name__)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    hubspot_access_token = models.TextField(blank=True, null=True)
    hubspot_refresh_token = models.TextField(blank=True, null=True)
    pipedrive_access_token = models.TextField(blank=True, null=True)
    pipedrive_refresh_token = models.TextField(blank=True, null=True)
    pipedrive_token_expires_at = models.DateTimeField(blank=True, null=True)
    lead_filter_count = models.IntegerField(default=0)
    lead_filter_quota = models.IntegerField(default=0)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    subscription_status = models.CharField(max_length=50, default='inactive')
    subscription_id = models.CharField(max_length=100, null=True, blank=True)
    salesforce_access_token = models.TextField(blank=True, null=True)
    salesforce_refresh_token = models.TextField(blank=True, null=True)
    salesforce_instance_url = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    phone = models.CharField(max_length=50, blank=True)
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
        # If this is a new lead and it's not spam, send to Pipedrive if connected
        if is_new and not self.is_spam and hasattr(self.user, 'profile') and self.user.profile.pipedrive_access_token:
            from leads.services.pipedrive import send_lead_to_pipedrive
            send_lead_to_pipedrive(self.user, self)

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

class LeadRoutingSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='lead_routing_settings')
    send_non_spam_to_inbox = models.BooleanField(default=True)
    send_spam_to_inbox = models.BooleanField(default=True)
    non_spam_subject = models.CharField(max_length=100, default="✅ New Qualified Lead")
    spam_subject = models.CharField(max_length=100, default="🚫 New Spam Lead Detected")
    notification_email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Optionally, add daily_summary and include_lead_details fields for future use
    # daily_summary = models.BooleanField(default=False)
    # include_lead_details = models.BooleanField(default=True)

    def __str__(self):
        return f"LeadRoutingSettings for {self.user.username}"

class WebhookSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='webhook_settings')
    webhook_url = models.URLField(blank=True, null=True)
    send_non_spam = models.BooleanField(default=True)
    send_spam = models.BooleanField(default=False)

    def __str__(self):
        return f"WebhookSettings for {self.user.username}"

class HubSpotCredentials(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - HubSpot Credentials"

class PipedriveCredentials(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - Pipedrive Credentials"

class StripeCustomer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    customer_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.customer_id}"

class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stripe_subscription_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.status}"

class Price(models.Model):
    stripe_price_id = models.CharField(max_length=100)
    product_name = models.CharField(max_length=100)
    amount = models.IntegerField()
    currency = models.CharField(max_length=3)
    interval = models.CharField(max_length=20)
    lead_filter_quota = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product_name} - {self.amount} {self.currency}"

class LeadFilterCount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    count = models.IntegerField(default=0)
    last_reset = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.count}"

    def reset_if_new_month(self):
        now = timezone.now()
        if now.month != self.last_reset.month or now.year != self.last_reset.year:
            self.count = 0
            self.last_reset = now
            self.save()
            return True
        return False

class SalesforceCredentials(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.TextField()
    refresh_token = models.TextField()
    instance_url = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - Salesforce Credentials"

from django.db import models
from django.contrib.auth.models import User

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

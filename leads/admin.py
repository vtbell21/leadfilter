from django.contrib import admin
from .models import FacebookLead, FacebookPageConnection

@admin.register(FacebookLead)
class FacebookLeadAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone', 'is_spam', 'received_at')
    list_filter = ('is_spam', 'is_valid_email', 'is_valid_phone', 'received_at')
    search_fields = ('full_name', 'email', 'phone', 'leadgen_id')
    readonly_fields = ('received_at',)
    ordering = ('-received_at',)

@admin.register(FacebookPageConnection)
class FacebookPageConnectionAdmin(admin.ModelAdmin):
    list_display = ('page_name', 'page_id', 'user', 'connected_at')
    list_filter = ('connected_at',)
    search_fields = ('page_name', 'page_id', 'user__username')
    readonly_fields = ('connected_at',)
    ordering = ('-connected_at',)

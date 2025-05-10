import requests
from django.conf import settings
import logging

def refresh_hubspot_token(user):
    token_url = 'https://api.hubapi.com/oauth/v1/token'
    data = {
        'grant_type': 'refresh_token',
        'client_id': settings.HUBSPOT_CLIENT_ID,
        'client_secret': settings.HUBSPOT_CLIENT_SECRET,
        'refresh_token': user.profile.hubspot_refresh_token,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(token_url, data=data, headers=headers)

    if response.status_code == 200:
        tokens = response.json()
        user.profile.hubspot_access_token = tokens['access_token']

        # HubSpot may return a new refresh token — save it if it exists
        if 'refresh_token' in tokens:
            user.profile.hubspot_refresh_token = tokens['refresh_token']

        user.profile.save()
    else:
        raise Exception('Failed to refresh HubSpot token')

def create_hubspot_contact(user, lead):
    logger = logging.getLogger(__name__)
    logger.info(f"[HubSpot Sync] Attempting to send lead {lead.id} (email: {lead.email}) for user {user.id} ({user.email}) to HubSpot.")
    try:
        refresh_hubspot_token(user)
        url = "https://api.hubapi.com/crm/v3/objects/contacts"
        headers = {
            'Authorization': f'Bearer {user.profile.hubspot_access_token}',
            'Content-Type': 'application/json'
        }
        data = {
            "properties": {
                "email": lead.email,
                "firstname": getattr(lead, 'first_name', ''),
                "lastname": getattr(lead, 'last_name', ''),
                "phone": lead.phone,
            }
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            logger.info(f"[HubSpot Sync] Successfully sent lead {lead.id} to HubSpot.")
            return True
        else:
            logger.error(f"[HubSpot Sync] Failed to send lead {lead.id} to HubSpot. Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"[HubSpot Sync] Exception while sending lead {lead.id} to HubSpot: {e}")
        return False 
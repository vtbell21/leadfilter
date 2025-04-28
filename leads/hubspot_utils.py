import requests
from django.conf import settings

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
    refresh_hubspot_token(user)

    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    headers = {
        'Authorization': f'Bearer {user.profile.hubspot_access_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "properties": {
            "email": lead.email,
            "firstname": lead.first_name,
            "lastname": lead.last_name,
            "phone": lead.phone,
        }
    }
    response = requests.post(url, headers=headers, json=data)
    return response.status_code == 201 
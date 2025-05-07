import requests
from django.utils import timezone
from django.conf import settings

def send_lead_to_zoho(user, lead):
    access_token = getattr(user.profile, 'zoho_access_token', None)
    if not access_token:
        return None
    url = 'https://www.zohoapis.com/crm/v2/Leads'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'Content-Type': 'application/json',
    }
    data = {
        "data": [
            {
                "Last_Name": lead.full_name.split()[-1] if lead.full_name else "Lead",
                "First_Name": lead.full_name.split()[0] if lead.full_name and len(lead.full_name.split()) > 1 else "",
                "Email": lead.email,
                "Phone": lead.phone,
                "Company": "SpamGuard Lead"
            }
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    return response

def refresh_zoho_token_if_expired(profile):
    if not profile.zoho_access_token or not profile.zoho_refresh_token or not profile.zoho_token_expires_at:
        return
    if profile.zoho_token_expires_at > timezone.now():
        return  # Token is still valid
    # Token expired, refresh it
    data = {
        'refresh_token': profile.zoho_refresh_token,
        'client_id': getattr(profile, 'zoho_client_id', None) or getattr(settings, 'ZOHO_CLIENT_ID', None),
        'client_secret': getattr(profile, 'zoho_client_secret', None) or getattr(settings, 'ZOHO_CLIENT_SECRET', None),
        'grant_type': 'refresh_token',
    }
    response = requests.post('https://accounts.zoho.com/oauth/v2/token', data=data)
    if response.status_code == 200:
        token_data = response.json()
        profile.zoho_access_token = token_data['access_token']
        expires_in = token_data.get('expires_in')
        if expires_in:
            profile.zoho_token_expires_at = timezone.now() + timezone.timedelta(seconds=int(expires_in))
        profile.save() 
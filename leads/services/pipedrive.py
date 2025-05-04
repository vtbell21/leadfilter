import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

PIPEDRIVE_API_BASE = "https://api.pipedrive.com/v1"


def refresh_pipedrive_token(user):
    """
    Refresh the Pipedrive access token using the refresh token and update the user's profile.
    Returns True if successful, False otherwise.
    """
    refresh_token = getattr(user.profile, 'pipedrive_refresh_token', None)
    if not refresh_token:
        logger.error(f"User {user.id} does not have a Pipedrive refresh token.")
        return False
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': settings.PIPEDRIVE_CLIENT_ID,
        'client_secret': settings.PIPEDRIVE_CLIENT_SECRET,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        resp = requests.post('https://oauth.pipedrive.com/oauth/token', data=data, headers=headers)
        resp.raise_for_status()
        tokens = resp.json()
        user.profile.pipedrive_access_token = tokens.get('access_token')
        user.profile.pipedrive_refresh_token = tokens.get('refresh_token', refresh_token)
        expires_in = tokens.get('expires_in')
        if expires_in:
            user.profile.pipedrive_token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
        user.profile.save()
        logger.info(f"Refreshed Pipedrive token for user {user.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to refresh Pipedrive token for user {user.id}: {e}")
        return False


def send_lead_to_pipedrive(user, lead):
    """
    Create a contact (person) and a lead (opportunity) in Pipedrive for the given user and lead.
    Returns a dict with success status and any error/info messages.
    """
    access_token = getattr(user.profile, 'pipedrive_access_token', None)
    if not access_token:
        logger.error(f"User {user.id} does not have a Pipedrive access token.")
        return {"success": False, "error": "No Pipedrive access token."}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # 1. Create Person (Contact)
    person_payload = {
        "name": lead.full_name or lead.email or "Unknown",
        "email": lead.email,
        "phone": lead.phone,
    }
    try:
        person_resp = requests.post(f"{PIPEDRIVE_API_BASE}/persons", headers=headers, json=person_payload)
        if person_resp.status_code == 401:
            logger.warning(f"Pipedrive access token expired for user {user.id}, attempting refresh.")
            if refresh_pipedrive_token(user):
                headers["Authorization"] = f"Bearer {user.profile.pipedrive_access_token}"
                person_resp = requests.post(f"{PIPEDRIVE_API_BASE}/persons", headers=headers, json=person_payload)
            else:
                return {"success": False, "error": "Failed to refresh Pipedrive token."}
        person_resp.raise_for_status()
        person_data = person_resp.json().get('data')
        if not person_data or not person_data.get('id'):
            logger.error(f"Failed to create Pipedrive person: {person_resp.text}")
            return {"success": False, "error": "Failed to create contact in Pipedrive."}
        person_id = person_data['id']
        logger.info(f"Created Pipedrive person with ID {person_id} for user {user.id}")
    except Exception as e:
        logger.error(f"Error creating Pipedrive person: {e}")
        return {"success": False, "error": str(e)}

    # 2. Create Lead (Opportunity)
    lead_payload = {
        "title": f"Lead from {lead.full_name or lead.email or 'Unknown'}",
        "person_id": person_id,
        # Optionally add more fields here
    }
    try:
        lead_resp = requests.post(f"{PIPEDRIVE_API_BASE}/leads", headers=headers, json=lead_payload)
        if lead_resp.status_code == 401:
            logger.warning(f"Pipedrive access token expired for user {user.id} (lead creation), attempting refresh.")
            if refresh_pipedrive_token(user):
                headers["Authorization"] = f"Bearer {user.profile.pipedrive_access_token}"
                lead_resp = requests.post(f"{PIPEDRIVE_API_BASE}/leads", headers=headers, json=lead_payload)
            else:
                return {"success": False, "error": "Failed to refresh Pipedrive token."}
        lead_resp.raise_for_status()
        lead_data = lead_resp.json().get('data')
        if not lead_data or not lead_data.get('id'):
            logger.error(f"Failed to create Pipedrive lead: {lead_resp.text}")
            return {"success": False, "error": "Failed to create lead in Pipedrive."}
        logger.info(f"Created Pipedrive lead with ID {lead_data['id']} for user {user.id}")
        return {"success": True, "person_id": person_id, "lead_id": lead_data['id']}
    except Exception as e:
        logger.error(f"Error creating Pipedrive lead: {e}")
        return {"success": False, "error": str(e)} 
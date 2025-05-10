import requests
import logging
from django.conf import settings
from leads.hubspot_utils import refresh_hubspot_token

def send_lead_to_hubspot(user, lead):
    """
    Create or update a contact in HubSpot for the given user and lead.
    Returns a dict with success status and any error/info messages.
    """
    logging.getLogger(__name__).info(f"[HubSpot Sync] Attempting to send lead {lead.id} (email: {lead.email}) for user {user.id} ({user.email}) to HubSpot.")
    def do_sync(access_token):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        properties = {
            "email": lead.email,
            "firstname": lead.full_name.split()[0] if lead.full_name else "",
            "lastname": lead.full_name.split()[-1] if lead.full_name and len(lead.full_name.split()) > 1 else "",
            "phone": lead.phone,
        }
        if hasattr(lead, 'custom_fields') and isinstance(lead.custom_fields, dict):
            for k, v in lead.custom_fields.items():
                properties[k.lower().replace(' ', '_')] = v
        search_url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
        search_payload = {
            "filterGroups": [
                {"filters": [{"propertyName": "email", "operator": "EQ", "value": lead.email}]}
            ],
            "properties": ["email"]
        }
        search_resp = requests.post(search_url, headers=headers, json=search_payload)
        if search_resp.status_code == 401:
            return '401', None
        search_resp.raise_for_status()
        results = search_resp.json().get('results', [])
        if results:
            contact_id = results[0]['id']
            update_url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
            update_payload = {"properties": properties}
            update_resp = requests.patch(update_url, headers=headers, json=update_payload)
            if update_resp.status_code == 401:
                return '401', None
            update_resp.raise_for_status()
            return 'ok', {"success": True, "action": "updated", "contact_id": contact_id}
        else:
            create_url = "https://api.hubapi.com/crm/v3/objects/contacts"
            create_payload = {"properties": properties}
            create_resp = requests.post(create_url, headers=headers, json=create_payload)
            if create_resp.status_code == 401:
                return '401', None
            create_resp.raise_for_status()
            contact_id = create_resp.json().get('id')
            return 'ok', {"success": True, "action": "created", "contact_id": contact_id}

    access_token = getattr(user.profile, 'hubspot_access_token', None)
    if not access_token:
        return {"success": False, "error": "No HubSpot access token."}
    try:
        status, result = do_sync(access_token)
        if status == '401':
            logging.getLogger(__name__).warning("HubSpot token expired, attempting refresh and retry.")
            try:
                refresh_hubspot_token(user)
            except Exception as e:
                logging.getLogger(__name__).error(f"Failed to refresh HubSpot token: {e}")
                return {"success": False, "error": "Failed to refresh HubSpot token."}
            access_token = getattr(user.profile, 'hubspot_access_token', None)
            if not access_token:
                return {"success": False, "error": "No HubSpot access token after refresh."}
            status, result = do_sync(access_token)
            if status == '401':
                return {"success": False, "error": "HubSpot access token is invalid even after refresh."}
        if result:
            return result
        return {"success": False, "error": "Unknown error during HubSpot sync."}
    except Exception as e:
        logging.getLogger(__name__).error(f"HubSpot contact sync error: {e}")
        return {"success": False, "error": str(e)} 
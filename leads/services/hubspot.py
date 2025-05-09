import requests
import logging
from django.conf import settings

def send_lead_to_hubspot(user, lead):
    """
    Create or update a contact in HubSpot for the given user and lead.
    Returns a dict with success status and any error/info messages.
    """
    access_token = getattr(user.profile, 'hubspot_access_token', None)
    if not access_token:
        return {"success": False, "error": "No HubSpot access token."}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # Prepare contact properties
    properties = {
        "email": lead.email,
        "firstname": lead.full_name.split()[0] if lead.full_name else "",
        "lastname": lead.full_name.split()[-1] if lead.full_name and len(lead.full_name.split()) > 1 else "",
        "phone": lead.phone,
    }
    # Add custom fields if present
    if hasattr(lead, 'custom_fields') and isinstance(lead.custom_fields, dict):
        for k, v in lead.custom_fields.items():
            properties[k.lower().replace(' ', '_')] = v

    # Check if contact exists by email
    search_url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    search_payload = {
        "filterGroups": [
            {"filters": [{"propertyName": "email", "operator": "EQ", "value": lead.email}]}
        ],
        "properties": ["email"]
    }
    try:
        search_resp = requests.post(search_url, headers=headers, json=search_payload)
        search_resp.raise_for_status()
        results = search_resp.json().get('results', [])
        if results:
            # Update existing contact
            contact_id = results[0]['id']
            update_url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
            update_payload = {"properties": properties}
            update_resp = requests.patch(update_url, headers=headers, json=update_payload)
            update_resp.raise_for_status()
            return {"success": True, "action": "updated", "contact_id": contact_id}
        else:
            # Create new contact
            create_url = "https://api.hubapi.com/crm/v3/objects/contacts"
            create_payload = {"properties": properties}
            create_resp = requests.post(create_url, headers=headers, json=create_payload)
            create_resp.raise_for_status()
            contact_id = create_resp.json().get('id')
            return {"success": True, "action": "created", "contact_id": contact_id}
    except Exception as e:
        logging.getLogger(__name__).error(f"HubSpot contact sync error: {e}")
        return {"success": False, "error": str(e)} 
from django.conf import settings
import requests

def send_lead_to_ghl(user, lead):
    api_key = user.profile.ghl_api_key
    if not api_key:
        return

    base_url = getattr(settings, "GHL_API_BASE_URL", "https://rest.gohighlevel.com/v1")

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    contact_data = {
        "firstName": lead.full_name or "SpamGuard Lead",
        "email": lead.email,
        "phone": lead.phone,
    }

    try:
        contact_response = requests.post(
            f"{base_url}/contacts/",
            headers=headers,
            json=contact_data,
            timeout=5
        )
        contact_response.raise_for_status()
        contact_id = contact_response.json().get("contact", {}).get("id")

        # Optional: create opportunity
        if contact_id:
            opportunity_data = {
                "contactId": contact_id,
                "pipelineId": "YOUR_PIPELINE_ID",  # Optional
                "stageId": "YOUR_STAGE_ID",        # Optional
                "status": "open",
                "title": f"Lead from Spam Guard: {lead.full_name}"
            }
            requests.post(
                f"{base_url}/opportunities/",
                headers=headers,
                json=opportunity_data,
                timeout=5
            )

    except Exception as e:
        print(f"[GHL] Failed to send lead: {e}") 
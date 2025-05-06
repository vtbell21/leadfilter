import requests

def send_lead_to_salesforce(user, lead):
    url = f"{user.profile.salesforce_instance_url}/services/data/v58.0/sobjects/Lead/"
    headers = {
        "Authorization": f"Bearer {user.profile.salesforce_access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "LastName": lead.full_name or "No Name",
        "Email": lead.email,
        "Phone": lead.phone,
        "Company": "SpamGuard",  # Required by Salesforce
        "Description": lead.message or "",
    }
    response = requests.post(url, headers=headers, json=payload)
    if not response.ok:
        import logging
        logging.getLogger(__name__).warning(f"Salesforce lead push failed: {response.text}") 
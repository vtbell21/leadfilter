import requests
from django.conf import settings
import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat

def normalize_phone_number(raw_number, default_region="US"):
    """
    Parse and validate a phone number. Return E.164 format if valid, else None.
    """
    try:
        parsed = phonenumbers.parse(raw_number, default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
        else:
            return None
    except NumberParseException:
        return None

def validate_phone_twilio(phone_number):
    """Validate phone number using Twilio Lookup API."""
    try:
        import requests
        from base64 import b64encode
        import os

        account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        if not account_sid or not auth_token:
            raise ValueError("Twilio credentials not found in environment variables.")

        if not phone_number.startswith('+'):
            phone_number = '+1' + phone_number

        auth_str = f"{account_sid}:{auth_token}"
        headers = {
            "Authorization": "Basic " + b64encode(auth_str.encode("ascii")).decode("ascii")
        }

        url = f"https://lookups.twilio.com/v1/PhoneNumbers/{phone_number}?Type=carrier"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        return {
            "valid": True,
            "line_type": data.get("carrier", {}).get("type"),
            "carrier": data.get("carrier", {}).get("name"),
            "country_code": data.get("country_code"),
            "is_us_number": data.get("country_code") == "US"
        }

    except Exception as e:
        return {
            "valid": False,
            "line_type": None,
            "carrier": None,
            "country_code": None,
            "is_us_number": False,
            "error": str(e),
        } 
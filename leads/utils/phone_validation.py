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

def validate_phone_with_numverify(phone_number):
    """
    Validate a phone number using the NumVerify API.
    Returns a dict with keys: valid, line_type, carrier, location, country_name, is_us_number
    """
    api_url = "http://apilayer.net/api/validate"
    params = {
        'access_key': settings.NUMVERIFY_API_KEY,
        'number': phone_number,
        'country_code': 'US',
        'format': 1
    }
    try:
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            'valid': data.get('valid', False),
            'line_type': data.get('line_type'),
            'carrier': data.get('carrier'),
            'location': data.get('location'),
            'country_name': data.get('country_name'),
            'is_us_number': data.get('country_code', '').upper() == 'US',
        }
    except Exception as e:
        return {
            'valid': False,
            'line_type': None,
            'carrier': None,
            'location': None,
            'country_name': None,
            'is_us_number': False,
            'error': str(e),
        } 
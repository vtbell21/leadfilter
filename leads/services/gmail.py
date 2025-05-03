from email.mime.text import MIMEText
import base64
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from leads.models import GmailCredentials

def send_gmail_message(user, to_email, subject, body_text):
    # 1. Load credentials from the database
    try:
        creds_obj = GmailCredentials.objects.filter(user=user).first()
        if not creds_obj:
            raise Exception("No Gmail credentials found for this user.")
    except GmailCredentials.DoesNotExist:
        raise Exception("No Gmail credentials found for this user.")

    creds = Credentials(
        token=creds_obj.token,
        refresh_token=creds_obj.refresh_token,
        token_uri=creds_obj.token_uri,
        client_id=creds_obj.client_id,
        client_secret=creds_obj.client_secret,
        scopes=creds_obj.scopes.split() if isinstance(creds_obj.scopes, str) else creds_obj.scopes,
    )

    # 2. Build the message
    message = MIMEText(body_text)
    message['to'] = to_email
    message['from'] = user.email
    message['subject'] = subject

    # 3. Encode the message
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # 4. Send the message via Gmail API
    service = build('gmail', 'v1', credentials=creds)
    send_result = service.users().messages().send(
        userId='me',
        body={'raw': raw_message}
    ).execute()

    return send_result 
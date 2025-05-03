from email.mime.text import MIMEText
import base64
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from leads.models import GmailCredentials

def send_gmail_message(user, to_email, subject, body_text, is_spam=False):
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

    # Refresh the token if expired or about to expire
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save the new token to the database
        creds_obj.token = creds.token
        creds_obj.refresh_token = creds.refresh_token
        creds_obj.token_uri = creds.token_uri
        creds_obj.client_id = creds.client_id
        creds_obj.client_secret = creds.client_secret
        creds_obj.scopes = " ".join(creds.scopes) if isinstance(creds.scopes, (list, tuple)) else creds.scopes
        creds_obj.save()

    # 2. Build the message
    message = MIMEText(body_text)
    message['to'] = to_email
    message['from'] = user.email
    message['subject'] = subject

    # 3. Encode the message
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # 4. Send the message via Gmail API
    service = build('gmail', 'v1', credentials=creds)

    label_ids = []
    if is_spam:
        # Check if the label exists
        label_name = "SpamGuard-Spam"
        labels = service.users().labels().list(userId='me').execute().get('labels', [])
        label_id = None
        for label in labels:
            if label['name'] == label_name:
                label_id = label['id']
                break
        if not label_id:
            # Create the label
            label_obj = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show',
                'color': {
                    'backgroundColor': '#ff0000',
                    'textColor': '#ffffff'
                }
            }
            created_label = service.users().labels().create(userId='me', body=label_obj).execute()
            label_id = created_label['id']
        label_ids.append(label_id)

    send_body = {'raw': raw_message}
    if label_ids:
        send_body['labelIds'] = label_ids

    send_result = service.users().messages().send(
        userId='me',
        body=send_body
    ).execute()

    return send_result 
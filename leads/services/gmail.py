from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from leads.models import GmailCredentials
import logging

logger = logging.getLogger(__name__)

def send_gmail_message(user, to_email, subject, body_text, is_spam=False, lead_details=None):
    # 1. Load credentials from the database
    try:
        creds_obj = GmailCredentials.objects.filter(user=user).first()
        if not creds_obj:
            raise Exception("No Gmail credentials found for this user.")
    except GmailCredentials.DoesNotExist:
        logger.error("No Gmail credentials found for user %s", user)
        raise

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
        try:
            creds.refresh(Request())
            # Save the new token to the database
            creds_obj.token = creds.token
            creds_obj.refresh_token = creds.refresh_token
            creds_obj.token_uri = creds.token_uri
            creds_obj.client_id = creds.client_id
            creds_obj.client_secret = creds.client_secret
            creds_obj.scopes = " ".join(creds.scopes) if isinstance(creds.scopes, (list, tuple)) else creds.scopes
            creds_obj.save()
        except Exception as e:
            logger.error(f"Failed to refresh Gmail token for user {user}: {e}")
            raise

    # 2. Build the HTML message
    msg = MIMEMultipart('alternative')
    msg['to'] = to_email
    msg['from'] = user.email
    msg['subject'] = subject

    # Build HTML table for lead details if provided
    html_table = ""
    if lead_details and isinstance(lead_details, dict):
        html_table = "<table style='border-collapse:collapse;width:100%;margin-top:10px;'>"
        for k, v in lead_details.items():
            html_table += f"<tr><td style='border:1px solid #ccc;padding:6px 12px;font-weight:bold;background:#f9f9f9'>{k}</td>"
            html_table += f"<td style='border:1px solid #ccc;padding:6px 12px'>{v}</td></tr>"
        html_table += "</table>"

    html_body = f"""
    <div style='font-family:sans-serif;'>
        <h2 style='color:#333;margin-bottom:0'>{subject}</h2>
        <p style='margin-top:0;color:#555;'>You have a new lead from Facebook.</p>
        {html_table}
        <div style='margin-top:20px;color:#888;font-size:0.9em;'>
            <em>This message was sent automatically by Spam Guard.</em>
        </div>
    </div>
    """
    # Attach both plain text and HTML (for compatibility)
    msg.attach(MIMEText(body_text, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    # 3. Encode the message
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    try:
        # 4. Send the message via Gmail API
        service = build('gmail', 'v1', credentials=creds)

        label_ids = []
        if is_spam:
            # Check if the label exists
            label_name = "SpamGuard-Spam"
            try:
                labels = service.users().labels().list(userId='me').execute().get('labels', [])
            except HttpError as e:
                logger.error(f"Failed to list Gmail labels for user {user}: {e}")
                raise
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
                try:
                    created_label = service.users().labels().create(userId='me', body=label_obj).execute()
                    label_id = created_label['id']
                except HttpError as e:
                    logger.error(f"Failed to create Gmail label for user {user}: {e}")
                    raise
            label_ids.append(label_id)

        send_body = {'raw': raw_message}
        if label_ids:
            send_body['labelIds'] = label_ids

        try:
            send_result = service.users().messages().send(
                userId='me',
                body=send_body
            ).execute()
        except HttpError as e:
            logger.error(f"Failed to send Gmail message for user {user}: {e}")
            raise

        return send_result
    except HttpError as e:
        logger.error(f"Gmail API error for user {user}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending Gmail message for user {user}: {e}")
        raise 
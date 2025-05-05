from leads.services.sendgrid_email import send_email
from leads.models import LeadRoutingSettings

def send_spam_lead_notification_email(lead, user):
    try:
        settings = user.lead_routing_settings
    except LeadRoutingSettings.DoesNotExist:
        # Default: send to user.email, subject as before
        settings = None
    if settings:
        if not settings.send_spam_to_inbox:
            return  # Do not send if user opted out
        subject = settings.spam_subject or "🚫 New Spam Lead Detected"
        recipient = settings.notification_email or user.email
    else:
        subject = "🚫 New Spam Lead Detected"
        recipient = user.email
    html_content = f"""
        <p>SpamGuard flagged a lead as spam:</p>
        <p><strong>Name:</strong> {lead.full_name}<br>
        <strong>Email:</strong> {lead.email}<br>
        <strong>Phone:</strong> {lead.phone}<br>
        <strong>Message:</strong> {lead.message}</p>
    """
    send_email(subject, html_content, recipient)

def send_non_spam_lead_notification_email(lead, user):
    try:
        settings = user.lead_routing_settings
    except LeadRoutingSettings.DoesNotExist:
        settings = None
    if settings:
        if not settings.send_non_spam_to_inbox:
            return  # Do not send if user opted out
        subject = settings.non_spam_subject or "✅ New Qualified Lead"
        recipient = settings.notification_email or user.email
    else:
        subject = "✅ New Qualified Lead"
        recipient = user.email
    html_content = f"""
        <p>SpamGuard filtered and passed a new lead:</p>
        <p><strong>Name:</strong> {lead.full_name}<br>
        <strong>Email:</strong> {lead.email}<br>
        <strong>Phone:</strong> {lead.phone}<br>
        <strong>Message:</strong> {lead.message}</p>
    """
    send_email(subject, html_content, recipient) 
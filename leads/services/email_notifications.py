from leads.services.sendgrid_email import send_email

def send_spam_lead_notification_email(lead, user):
    subject = "🚫 New Spam Lead Detected"
    html_content = f"""
        <p>SpamGuard flagged a lead as spam:</p>
        <p><strong>Name:</strong> {lead.full_name}<br>
        <strong>Email:</strong> {lead.email}<br>
        <strong>Phone:</strong> {lead.phone}<br>
        <strong>Message:</strong> {lead.message}</p>
    """
    send_email(subject, html_content, user.email)

def send_non_spam_lead_notification_email(lead, user):
    subject = "✅ New Qualified Lead"
    html_content = f"""
        <p>SpamGuard filtered and passed a new lead:</p>
        <p><strong>Name:</strong> {lead.full_name}<br>
        <strong>Email:</strong> {lead.email}<br>
        <strong>Phone:</strong> {lead.phone}<br>
        <strong>Message:</strong> {lead.message}</p>
    """
    send_email(subject, html_content, user.email) 
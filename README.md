# SpamGuard

SpamGuard is a lightweight middleware tool that filters spam, deduplicates leads, and improves lead quality before syncing them into your CRM. It was built for high-noise channels like **Facebook Lead Ads** and web forms, integrating cleanly with **HubSpot**, **Salesforce**, and **Zapier**.

---

## Features

- **Real-time validation** – Checks email and phone fields using syntax, MX lookup, and known disposable lists.  
- **Duplicate detection** – Fuzzy matching across email, phone, and name to prevent redundant CRM entries.  
- **Lead scoring** – Combines rule-based logic and optional GPT-assisted analysis to grade lead quality.  
- **Seamless integrations** – Syncs clean leads directly to CRMs or automations while quarantining bad submissions.  
- **Transparent audit log** – Every filtered lead includes detailed reasons and metadata for easy review.  

---

## How It Works

Lead Source → Validation Pipeline → Scoring → Deduplication → CRM Sync

1. **Collect** leads from Facebook Lead Ads, web forms, or automations.  
2. **Validate and score** each record using rule-based logic and AI signals.  
3. **Filter and route** qualified leads into CRMs or external workflows, while logging or rejecting low-quality entries.

---

## Tech Stack

- **Backend:** Django + Django REST Framework  
- **Database:** PostgreSQL  
- **Integrations:** HubSpot, Salesforce, Zapier  
- **Language:** Python 3.11  

---

API Example

POST /api/ingest/lead/

{
  "source": "facebook",
  "campaign_id": "spring-launch",
  "email": "test@example.com",
  "phone": "+1-385-555-1212",
  "name": "John Doe"
}

{
  "score": 82,
  "status": "accepted",
  "reasons": ["email_valid", "not_duplicate"],
  "synced": ["hubspot"]
}


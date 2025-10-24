# HelpChain Dead Letter Queue (DLQ) Management

## Overview

The Dead Letter Queue (DLQ) system handles emails that have permanently failed after all retry attempts. Failed emails are stored in Redis under the key `dlq:emails` for later analysis and potential reprocessing.

## Architecture

1. **Email Sending Flow:**
   - `send_email_task` attempts delivery with exponential backoff
   - After `MAX_RETRIES` (6) failures, email goes to DLQ
   - DLQ stores full email payload as JSON

2. **DLQ Reprocessing:**
   - `requeue_dlq_emails` task runs every 2 hours via Celery Beat
   - Takes up to 50 emails from DLQ and requeues them
   - Tracks requeue operations in analytics

## Manual DLQ Management

Use the `dlq_manager.py` script for manual DLQ operations:

```bash
# Show DLQ statistics
python dlq_manager.py stats

# Inspect emails in DLQ
python dlq_manager.py inspect [limit]

# Clear DLQ (dangerous!)
python dlq_manager.py clear

# Manual requeue instructions
python dlq_manager.py requeue [limit]
```

## Celery Beat Schedule

The DLQ requeue task runs automatically every 15 minutes:

```python
"requeue-dlq-emails": {
    "task": "tasks.requeue_dlq_emails",
    "schedule": crontab(minute="*/15"),  # Every 15 minutes
    "args": (100,),  # Up to 100 messages per cycle
},
```

## Manual Requeue

To manually trigger DLQ reprocessing:

```bash
# Via Celery CLI
celery -A celery_app call tasks.requeue_dlq_emails --args='[50]'

# Via Python (requires Flask app context)
from tasks import requeue_dlq_emails
requeue_dlq_emails.delay(50)
```

## DLQ Email Format

Emails in DLQ are stored as JSON with this structure:

```json
{
  "subject": "Email subject",
  "recipients": ["email@example.com"],
  "body": "Plain text content",
  "html": "<p>HTML content</p>",
  "sender": "noreply@example.com",
  "message_id": "mail-1234567890",
  "failed_at": "2024-01-01T12:00:00.000000",
  "reason": "SMTP connection timeout"
}
```

## Monitoring

- DLQ size can be monitored via Redis: `LLEN dlq:emails`
- Requeue operations are tracked in analytics with `dlq_requeue` events
- Failed requeue attempts are logged with error details

## Rate Limiting

To prevent being blocked by email providers like Zoho, the email sending task is rate-limited to **30 emails per minute**:

```python
@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=600, retry_jitter=True, max_retries=MAX_RETRIES, rate_limit="30/m")
def send_email_task(self, subject: str, recipients: list, body: str, sender: str = None, html: str = None, message_id: str = None):
    # Email sending logic...
```

This ensures compliance with email provider limits and prevents account blocking due to excessive sending.

## Configuration

DLQ behavior is controlled by these environment variables:

- `EMAIL_MAX_RETRIES=6` - Maximum retry attempts before DLQ
- `EMAIL_RETRY_BASE_SECONDS=10` - Base delay for exponential backoff
- `CELERY_BROKER_URL` - Redis connection for DLQ storage</content>
<parameter name="filePath">c:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend\DLQ_README.md
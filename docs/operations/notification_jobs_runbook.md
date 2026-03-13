# Notification Jobs — Runbook (Phase 1)

## Overview
HelpChain uses a database-backed notification queue to ensure that emails are never lost when SMTP is down.  
When a lead/contact is submitted, the system creates a `NotificationJob` in the database and attempts delivery.  
If SMTP fails, the job is retained and retried later.

This is the operational foundation for future multi-channel notifications (in‑app, push, webhook).

---

## Delivery flow
1. User submits the contact form.
2. Lead is saved to the database.
3. A `NotificationJob` is created (`channel=email`, `status=pending`).
4. The system attempts immediate delivery:
   - If SMTP succeeds → job marked `sent`.
   - If SMTP fails → job marked `retry` and scheduled.

---

## Status lifecycle
- `pending` → created, waiting for first delivery
- `processing` → picked up by the worker
- `sent` → delivery succeeded
- `retry` → delivery failed, will retry later
- `failed` → retries exhausted (manual intervention needed)

### Status reference table
| Status | Meaning | Operator action |
| --- | --- | --- |
| pending | Job created, not yet attempted | Ensure worker runs |
| processing | Worker is handling the job | None (transient) |
| sent | Delivery succeeded | None |
| retry | Delivery failed, scheduled for retry | Check SMTP / run worker |
| failed | Retries exhausted | Manual intervention needed |

---

## Retry behavior
Retry schedule is a simple exponential backoff:
- 1st retry: +5 minutes
- 2nd retry: +15 minutes
- 3rd retry: +45 minutes
- 4th retry: +2 hours
- 5th retry: +6 hours
- 6th retry: +12 hours (cap)

After max attempts, the job becomes `failed`.

---

## What the user sees
- **Success**: lead saved + email sent → confirmation page.
- **Warning**: lead saved but email delivery failed → confirmation page + warning flash.
- **Error**: lead save failed → form shows error, no confirmation.

---

## What is not lost
- The lead is stored in the database regardless of SMTP failures.
- The notification job is stored separately in `notification_jobs`.
- SMTP failure does not destroy the submission.
- Retryable jobs remain in the database until sent or marked failed.

---

## Render setup (production)
Recommended approach: add a **Render Cron Job** that runs every 5–10 minutes.

**Command:**
```
flask notifications.process
```

Optional batch size:
```
NOTIFY_BATCH=100 flask notifications.process
```

This processes all due jobs and exits cleanly.

---

## Manual commands
Run the worker manually (local or prod shell):
```
flask notifications.process
```

Check recent jobs (SQL):
```
SELECT status, COUNT(*) FROM notification_jobs GROUP BY status;
```

---

## First deployment checklist
- Migration applied (notification_jobs exists)
- Contact form creates a lead
- Contact form creates a notification job
- Worker runs without error
- SMTP configuration present
- Recipient configuration present

---

## Incident procedure
### SMTP down / emails not arriving
1. Check Render logs for:
   - `SMTP not configured`
   - `notify skipped`
   - `send failed`
2. Verify environment variables:
   - `MAIL_SERVER`
   - `MAIL_PORT`
   - `MAIL_USERNAME`
   - `MAIL_PASSWORD`
   - `MAIL_DEFAULT_SENDER`
   - `PRO_LEADS_NOTIFY_TO` or `ADMIN_NOTIFY_EMAIL`
3. Once SMTP is fixed, run:
   ```
   flask notifications.process
   ```
4. Confirm jobs move from `retry` to `sent`.

---

## Known limitations (Phase 1)
- Only email delivery is implemented
- No admin UI for notification jobs yet
- No manual retry button yet
- No digest/escalation policy yet
- Worker is CLI/scheduled, not a distributed queue

---

## Monitoring checklist
- Any jobs stuck in `retry` for > 24h?
- Growing count of `failed` jobs?
- Errors in logs: SMTP auth errors or missing config
- Recent `sent` jobs consistent with daily volume

---

## Operator cheat‑sheet
**If contact emails stop arriving:**
1. Check Render logs for SMTP errors.
2. Verify `PRO_LEADS_NOTIFY_TO` is set.
3. Run `flask notifications.process` once manually.

**If jobs are stuck in retry:**
1. Fix SMTP credentials or sender domain.
2. Run `flask notifications.process` again.

**If SMTP was restored:**
1. Run `flask notifications.process`.
2. Confirm retry jobs are cleared.

---

## Developer note (why DB-backed)
Direct SMTP sending can fail silently if the provider is unavailable, blocked, or misconfigured.  
A DB-backed job queue ensures:
- no lost notifications
- auditability
- retry behavior without new infrastructure
- readiness for multi-channel delivery

This is the right foundation for a Slack-like notification layer later:
jobs can be routed to email, in‑app, push, and webhook channels without changing core flows.

---

## Future roadmap
Planned extensions (not implemented yet):
- in‑app notifications for admins/operators
- push notifications for mobile responders
- webhook delivery to institutional systems
- AI‑assisted routing based on case severity and urgency

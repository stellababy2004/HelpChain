# Notification Jobs Runbook

## Status
- Reviewed: 2026-04
- Status: Needs validation
- Source of truth: Partial
- Review required: Yes
- Notes: Validate against the current production environment and current job runner before using this document for incident response or operational changes.

## Overview

HelpChain is expected to use a database-backed notification queue so email delivery failures do not silently discard operational events. When a lead or contact submission is created, the system should store a `NotificationJob` and attempt delivery. Failed delivery should remain retryable.

## Delivery Flow

1. A user submits a qualifying form.
2. The business record is stored.
3. A `NotificationJob` is created with `channel=email`.
4. Delivery is attempted immediately or by worker.
5. Failed delivery is retried according to queue policy.

## Job Statuses

- `pending` means the job has been created and not yet completed.
- `processing` means a worker has picked up the job.
- `sent` means delivery succeeded.
- `retry` means delivery failed but remains eligible for retry.
- `failed` means retry policy has been exhausted and operator action is needed.

## Operational Rule

The originating submission should not be lost because of SMTP failure. The queue is the safety boundary between business data capture and external email delivery.

## Runtime Command

Current expected processor command:

```bash
flask notifications.process
```

Optional batch execution:

```bash
NOTIFY_BATCH=100 flask notifications.process
```

## Checks

- Confirm the notification jobs table exists in the current environment.
- Confirm the relevant submission creates a notification job.
- Confirm worker execution updates job states as expected.
- Confirm SMTP and recipient configuration are present.

## Incident Handling

If emails are not arriving:

1. Check application or platform logs for delivery failures.
2. Verify SMTP configuration values.
3. Run the processor manually if appropriate.
4. Inspect job counts by status to determine whether the queue is blocked or exhausted.

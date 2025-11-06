# Runbook – Email Delivery & Incident Response

## Email Delivery Failures

If Formspree or SMTP fails:

1. Check SPF/DKIM/DMARC via Site24x7 or MXToolbox.
2. Verify Flask-Mail config (MAIL_SERVER, MAIL_PORT, TLS).
3. Check `app.log` for tracebacks.
4. Retry via backup webhook or admin form.

## Incident Response

1. **Identify:** Detect anomalies via Site24x7 or APM.
2. **Contain:** Disable impacted endpoints or isolate the service.
3. **Eradicate:** Fix bug, patch dependency, or roll back.
4. **Recover:** Validate and redeploy.
5. **Document:** Update this Runbook and log the incident.

## SLA

- Critical incidents: 30 min acknowledgment, 2h resolution.
- Minor issues: Next release cycle.

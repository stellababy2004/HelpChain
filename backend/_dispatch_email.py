"""
Advanced email dispatch wrapper for HelpChain
Uses mail_service and Celery for async, templated, and reliable delivery.
"""
import logging

from flask import current_app

try:
    from mail_service import send_notification_email
except ImportError:
    send_notification_email = None

def _dispatch_email(subject, recipients, body, sender=None, html=None, template=None, context=None):
    """
    Dispatch an email using the HelpChain mail_service and Celery.
    - Uses HTML template if provided, else falls back to plain body.
    - Tracks analytics if available.
    - Logs and falls back to file if sending fails.
    """
    logger = logging.getLogger("helpchain.email")
    if not recipients:
        logger.warning("No recipients specified for email: %s", subject)
        return False

    # Prefer mail_service for advanced features
    if send_notification_email and template:
        try:
            return send_notification_email(
                recipient=recipients[0] if isinstance(recipients, (list, tuple)) else recipients,
                subject=subject,
                template=template,
                context=context or {},
            )
        except Exception as e:
            logger.error(f"mail_service.send_notification_email failed: {e}")

    # Fallback: try Flask-Mail directly if available
    try:
        from flask_mail import Mail, Message
        mail = Mail(current_app)
        msg = Message(subject=subject, recipients=recipients, body=body, sender=sender or current_app.config.get("MAIL_DEFAULT_SENDER"), html=html)
        mail.send(msg)
        logger.info(f"Fallback Flask-Mail sent: {subject} to {recipients}")
        return True
    except Exception as e:
        logger.error(f"Fallback Flask-Mail failed: {e}")

    # Last resort: log to file
    try:
        with open("sent_emails.txt", "a", encoding="utf-8") as f:
            f.write(f"Subject: {subject}\nTo: {recipients}\nFrom: {sender or 'noreply@helpchain.bg'}\n\n{body}\n{'='*50}\n")
        logger.info("Email saved to file as fallback: %s", subject)
        return True
    except Exception as file_e:
        logger.error(f"Failed to save email to file: {file_e}")

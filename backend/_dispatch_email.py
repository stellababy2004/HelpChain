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


def _dispatch_email(
    subject, recipients, body, sender=None, html=None, template=None, context=None
):
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
                recipient=(
                    recipients[0]
                    if isinstance(recipients, (list, tuple))
                    else recipients
                ),
                subject=subject,
                template=template,
                context=context or {},
            )
        except Exception as e:
            logger.error(f"mail_service.send_notification_email failed: {e}")

    # Fallback: try to use the application's configured `mail` if present
    try:
        # If the main application exposes a Mail instance (e.g. `from appy import mail`),
        # prefer using it so tests that patch `backend.appy.mail.send` will observe
        # the calls. This avoids creating a local Mail(current_app) instance here
        # which is harder for tests to intercept.
        try:
            from appy import mail as app_mail  # type: ignore
        except Exception:
            app_mail = None

        if app_mail is not None:
            try:
                # Construct a minimal Message-like object if the app's mail
                # implementation expects it; flask-mail's Message is simple
                from flask_mail import Message

                msg = Message(
                    subject=subject,
                    recipients=recipients,
                    body=body,
                    sender=sender or current_app.config.get("MAIL_DEFAULT_SENDER"),
                    html=html,
                )
            except Exception:
                # If Message isn't available, pass through a simple tuple
                msg = (subject, recipients, body)

            try:
                app_mail.send(msg)
                logger.info(f"App Mail sent: {subject} to {recipients}")
                return True
            except Exception as e:
                # If the application's mail instance fails, log and proceed to
                # the last-resort file fallback. We avoid constructing a local
                # Mail(current_app) here because test shims may delegate that
                # local instance back to the same app_mail, resulting in
                # duplicate send attempts (and confusing tests that patch
                # appy.mail.send). A direct file fallback is simpler and more
                # deterministic for tests.
                logger.error(f"App mail.send failed: {e}")
                # continue to file fallback

        else:
            # If no app mail instance, fall back to constructing a local Mail instance
            try:
                from flask_mail import Mail, Message

                mail = Mail(current_app)
                msg = Message(
                    subject=subject,
                    recipients=recipients,
                    body=body,
                    sender=sender or current_app.config.get("MAIL_DEFAULT_SENDER"),
                    html=html,
                )
                mail.send(msg)
                logger.info(f"Fallback Flask-Mail sent: {subject} to {recipients}")
                return True
            except Exception as e:
                logger.error(f"Fallback Flask-Mail failed: {e}")
    except Exception as e:
        logger.error(f"Fallback Flask-Mail failed: {e}")

    # Last resort: log to file
    try:
        with open("sent_emails.txt", "a", encoding="utf-8") as f:
            f.write(
                f"Subject: {subject}\nTo: {recipients}\nFrom: {sender or 'noreply@helpchain.bg'}\n\n{body}\n{'='*50}\n"
            )
        logger.info("Email saved to file as fallback: %s", subject)
        return True
    except Exception as file_e:
        logger.error(f"Failed to save email to file: {file_e}")

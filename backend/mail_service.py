"""
HelpChain Mail Service
Handles sending notification emails using Flask-Mail
"""

import logging
import os
import smtplib
import time
from datetime import UTC, datetime
from email.message import EmailMessage

from flask import current_app, render_template
from flask_mail import Message

try:
    from ..analytics_service import analytics_service

    analytics_available = True
except ImportError:
    analytics_service = None
    analytics_available = False

logger = logging.getLogger(__name__)

def _fallback_email_html(subject: str, context: dict) -> str:
    # Minimal HTML fallback when template is missing or fails to render.
    content = ""
    if isinstance(context, dict):
        content = (
            context.get("content")
            or context.get("message")
            or context.get("body")
            or ""
        )
    return f"""<!doctype html>
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.45;">
    <h2 style="margin: 0 0 12px;">{subject}</h2>
    <div style="margin: 0 0 18px;">{content}</div>
    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 18px 0;">
    <div style="font-size: 12px; color: #6b7280;">
      HelpChain.live · contact@helpchain.live · security@helpchain.live
    </div>
  </body>
</html>"""


def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


def send_notification_email(recipient, subject, template, context=None):
    """
    Send notification email to recipient

    Args:
        recipient (str): Email address
        subject (str): Email subject
        template (str): Template filename
        context (dict): Template context variables

    Returns:
        bool: True if queued successfully, False otherwise
    """
    try:
        if not recipient:
            logger.warning("No recipient specified for email")
            return False
        # Some SMTP providers reject SMTPUTF8 recipients; fail fast with a clear log.
        try:
            recipient.encode("ascii")
        except UnicodeEncodeError:
            logger.error(
                "Recipient email must be ASCII for this SMTP server (no SMTPUTF8): %r",
                recipient,
            )
            return False

        # Dev/test safety: allow mocking email delivery without touching SMTP.
        if os.environ.get("MAIL_MOCK", "").lower() in ("true", "1", "yes"):
            logger.info(
                "[MAIL_MOCK] Email suppressed | to=%s | subject=%s | template=%s",
                recipient,
                subject,
                template,
            )
            return True

        # Prepare context
        if context is None:
            context = {}

        frontend_url = (current_app.config.get("FRONTEND_URL") or "").rstrip("/")

        # Add common context variables
        context.update(
            {
                "recipient_email": recipient,
                "sent_at": utc_now(),
                "unsubscribe_url": (
                    f"{frontend_url}/api/notification/unsubscribe/{{token}}"
                    if frontend_url
                    else ""
                ),
                "preferences_url": (
                    f"{frontend_url}/notification_preferences" if frontend_url else ""
                ),
                "privacy_url": (f"{frontend_url}/privacy" if frontend_url else ""),
                "terms_url": (f"{frontend_url}/terms" if frontend_url else ""),
            }
        )

        # Render HTML content
        try:
            html_content = render_template(template, **context)
        except Exception as e:
            logger.warning("Email template render failed (%s). Using fallback HTML.", e)
            html_content = _fallback_email_html(subject, context)

        # Generate unique message ID
        message_id = f"notification_{recipient}_{template}_{int(time.time())}"

        # Optional TXT template for better deliverability (same path, .txt).
        text_content = None
        if template and template.endswith(".html"):
            txt_template = template[:-5] + ".txt"
            try:
                text_content = render_template(txt_template, **context)
            except Exception:
                text_content = None

        # Prefer async sending via Celery only when broker is configured.
        broker = os.environ.get("CELERY_BROKER_URL") or os.environ.get("BROKER_URL")
        queued = False
        queue_err = None

        try:
            if broker:
                # Import here to avoid circular imports and to allow environments without Celery.
                from .tasks import send_email_task

                send_email_task.delay(
                    subject=subject,
                    recipients=[recipient],
                    html=html_content,
                    message_id=message_id,
                )
                queued = True
        except Exception as e:
            queue_err = e

        if queued:
            # Track analytics for queued email
            if analytics_available and analytics_service:
                analytics_service.track_event(
                    event_type="email_queued",
                    event_category="notification",
                    context={
                        "recipient": recipient,
                        "template": template,
                        "subject": subject,
                        "message_id": message_id,
                    },
                )
            logger.info("Email queued successfully | to=%s | subject=%s", recipient, subject)
            return True

        # If broker is configured but queue failed, warn once and fall back to SMTP.
        if broker and queue_err:
            logger.warning(
                "Email queue failed (%s). Falling back to direct SMTP.", queue_err
            )

        # --- Direct SMTP ---
        cfg = current_app.config
        mail_server = cfg.get("MAIL_SERVER")
        mail_port = int(cfg.get("MAIL_PORT") or 0)
        mail_user = cfg.get("MAIL_USERNAME")
        mail_pass = cfg.get("MAIL_PASSWORD")
        mail_sender = cfg.get("MAIL_DEFAULT_SENDER") or mail_user
        from_name = cfg.get("MAIL_FROM_NAME") or "HelpChain"
        reply_to = cfg.get("MAIL_REPLY_TO") or mail_sender
        use_tls = bool(cfg.get("MAIL_USE_TLS"))
        use_ssl = bool(cfg.get("MAIL_USE_SSL"))

        if not (mail_server and mail_port and mail_user and mail_pass and mail_sender):
            logger.error("SMTP not configured (missing MAIL_* settings).")
            return False

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{mail_sender}>"
        msg["To"] = recipient
        msg["Reply-To"] = reply_to
        msg["Message-ID"] = f"<{message_id}@helpchain.live>"

        if text_content:
            msg.set_content(text_content)
        else:
            msg.set_content("Ouvrez ce message dans un client compatible HTML pour voir le contenu.")
        msg.add_alternative(html_content, subtype="html")

        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(mail_server, mail_port, timeout=15)
            else:
                server = smtplib.SMTP(mail_server, mail_port, timeout=15)
            with server:
                if use_tls and not use_ssl:
                    server.starttls()
                server.login(mail_user, mail_pass)
                server.send_message(msg)
        except Exception as smtp_e:
            logger.error("Direct SMTP send failed: %s", smtp_e)
            # Dev-friendly fallback: write to a local file for manual inspection.
            try:
                with open("sent_emails.txt", "a", encoding="utf-8") as f:
                    f.write(f"\n--- {utc_now().isoformat()} ---\n")
                    f.write(f"To: {recipient}\nSubject: {subject}\n\n")
                    if text_content:
                        f.write(text_content + "\n\n")
                    f.write(html_content)
                    f.write("\n")
            except Exception:
                pass
            return False

        # Track analytics for sent email
        if analytics_available and analytics_service:
            analytics_service.track_event(
                event_type="email_sent",
                event_category="notification",
                context={
                    "recipient": recipient,
                    "template": template,
                    "subject": subject,
                    "message_id": message_id,
                },
            )

        logger.info("Email sent successfully | to=%s | subject=%s", recipient, subject)
        return True

    except Exception as e:
        logger.error(f"Failed to queue email to {recipient}: {e}")

        # Track failed email queuing
        if analytics_available and analytics_service:
            analytics_service.track_event(
                event_type="email_queue_failed",
                event_category="notification",
                context={"recipient": recipient, "template": template, "error": str(e)},
            )

        return False


def send_bulk_notification_email(recipients, subject, template, context=None):
    """
    Send notification email to multiple recipients

    Args:
        recipients (list): List of email addresses
        subject (str): Email subject
        template (str): Template filename
        context (dict): Template context variables

    Returns:
        dict: Results with queued count and failures
    """
    results = {"total": len(recipients), "queued": 0, "failed": 0, "failures": []}

    for recipient in recipients:
        success = send_notification_email(recipient, subject, template, context)
        if success:
            results["queued"] += 1
        else:
            results["failed"] += 1
            results["failures"].append(recipient)

    # Track bulk email analytics
    if analytics_available and analytics_service:
        analytics_service.track_event(
            event_type="bulk_email_queued",
            event_category="notification",
            context={
                "total_recipients": results["total"],
                "queued": results["queued"],
                "failed": results["failed"],
            },
        )

    logger.info(f"Bulk email queued: {results['queued']}/{results['total']} successful")
    return results


def send_welcome_email(user):
    """
    Send welcome email to new user

    Args:
        user: User object with email and name

    Returns:
        bool: True if sent successfully
    """
    return send_notification_email(
        recipient=user.email,
        subject="Добре дошли в HelpChain!",
        template="email_template.html",
        context={
            "notification_type": "welcome",
            "recipient_name": user.name,
            "subject": "Добре дошли в HelpChain!",
            "content": """
                Добре дошли в HelpChain! Благодарим ви, че се присъединихте към нашата общност.

                С HelpChain можете да:
                - Помагате на хора в нужда във вашия район
                - Получавате помощ когато имате нужда
                - Свързвате се с доброволци и нуждаещи се

                Започнете като създадете профил и се запознаете с наличните заявки.
            """,
            "action_url": f"{current_app.config['FRONTEND_URL']}/volunteer_dashboard",
        },
    )


def send_password_reset_email(user, reset_token):
    """
    Send password reset email

    Args:
        user: User object
        reset_token (str): Password reset token

    Returns:
        bool: True if sent successfully
    """
    reset_url = f"{current_app.config['FRONTEND_URL']}/reset-password/{reset_token}"

    return send_notification_email(
        recipient=user.email,
        subject="Възстановяване на парола - HelpChain",
        template="email_template.html",
        context={
            "notification_type": "password_reset",
            "recipient_name": user.name,
            "subject": "Възстановяване на парола - HelpChain",
            "content": """
                Получихме заявка за възстановяване на вашата парола.

                Ако не сте поискали възстановяване на парола, моля игнорирайте този имейл.

                За да възстановите паролата си, кликнете върху бутона по-долу:
            """,
            "action_url": reset_url,
        },
    )


def send_volunteer_assigned_email(task, volunteer):
    """
    Send email when volunteer is assigned to task

    Args:
        task: Task object
        volunteer: Volunteer user object

    Returns:
        bool: True if sent successfully
    """
    return send_notification_email(
        recipient=task.requester.email,
        subject="Доброволец е готов да помогне - HelpChain",
        template="email_template.html",
        context={
            "notification_type": "volunteer_assigned",
            "recipient_name": task.requester.name,
            "volunteer": {
                "name": volunteer.name,
                "phone": volunteer.phone,
                "eta": "30 минути",  # Would calculate actual ETA
            },
            "task": {"title": task.title, "description": task.description},
            "action_url": f"{current_app.config['FRONTEND_URL']}/task/{task.id}",
            "chat_url": f"{current_app.config['FRONTEND_URL']}/chat/{task.id}",
        },
    )


def send_task_completed_email(task):
    """
    Send email when task is completed

    Args:
        task: Task object

    Returns:
        bool: True if sent successfully
    """
    return send_notification_email(
        recipient=task.requester.email,
        subject="Задачата е завършена - HelpChain",
        template="email_template.html",
        context={
            "notification_type": "task_completed",
            "recipient_name": task.requester.name,
            "task": {
                "title": task.title,
                "completion_note": task.completion_note
                or "Задачата е успешно завършена.",
                "completed_at": (
                    task.completed_at.strftime("%d.%m.%Y %H:%M")
                    if task.completed_at
                    else utc_now().strftime("%d.%m.%Y %H:%M")
                ),
            },
            "feedback_url": f"{current_app.config['FRONTEND_URL']}/feedback/{task.id}",
            "new_request_url": f"{current_app.config['FRONTEND_URL']}/new-request",
        },
    )


def send_feedback_request_email(task):
    """
    Send feedback request email

    Args:
        task: Task object

    Returns:
        bool: True if sent successfully
    """
    return send_notification_email(
        recipient=task.requester.email,
        subject="Обратна връзка - HelpChain",
        template="email_template.html",
        context={
            "notification_type": "feedback_request",
            "recipient_name": task.requester.name,
            "task": {
                "title": task.title,
                "completed_at": (
                    task.completed_at.strftime("%d.%m.%Y %H:%M")
                    if task.completed_at
                    else utc_now().strftime("%d.%m.%Y %H:%M")
                ),
            },
            "feedback_url": f"{current_app.config['FRONTEND_URL']}/feedback/{task.id}",
        },
    )

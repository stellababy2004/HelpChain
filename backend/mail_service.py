"""
HelpChain Mail Service
Handles sending notification emails using Flask-Mail
"""

import hashlib
import logging
import os
import smtplib
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import requests
from flask import current_app, has_request_context, render_template, request
from flask_mail import Message
from sqlalchemy.exc import SQLAlchemyError

from backend.core.tenant import current_structure_id
from backend.helpchain_backend.src.models import EmailSendEvent, db

try:
    from ..analytics_service import analytics_service

    analytics_available = True
except ImportError:
    analytics_service = None
    analytics_available = False

logger = logging.getLogger(__name__)

_SAFE_FALLBACK_PURPOSES = frozenset(
    {
        "generic",
        "admin_status_update",
        "admin_access_reset",
        "admin_team_invitation",
        "request",
        "volunteer",
        "volunteer_magic_link",
        "request_magic_link",
        "demo_request_internal",
        "contact_exchange",
        "daily_health_report",
        "weekly_operations_report",
        "organization_signup_verification",
    }
)

_SENSITIVE_LOG_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "client_secret",
    "access_key",
)

# Email templates must not receive tenant/object identifiers or internal case
# fields by accident.  Legitimate workflow-specific fields remain allowed;
# callers that need a new sensitive field must define a reviewed template
# contract instead of passing it through the generic service.
_EMAIL_CONTEXT_BLOCKED_KEYS = frozenset(
    {
        "case_id",
        "request_id",
        "referral_id",
        "structure_id",
        "tenant_id",
        "organization_id",
        "risk_level",
        "risk_score",
        "description",
        "internal_note",
        "coordination_note",
        "case_events",
        "participants",
        "collaborators",
    }
)

_EMAIL_CONTEXT_ALLOWLISTS = {
    "emails/admin_access_reset.html": frozenset({"magic_link_url", "ttl_minutes"}),
    "emails/admin_team_invitation.html": frozenset(
        {"invitation_url", "role", "structure_name", "ttl_hours"}
    ),
    "emails/magic_link.html": frozenset(
        {
            "magic_link_url",
            "ttl_minutes",
            "intro_text",
            "button_text",
            "fallback_text",
            "ignore_line",
            "privacy_line",
        }
    ),
    "emails/organization_signup_verification.html": frozenset(
        {"verification_url", "ttl_minutes"}
    ),
    "emails/professional_lead_notify.html": frozenset(
        {
            "admin_url",
            "availability",
            "city",
            "created_at",
            "email",
            "full_name",
            "ip",
            "lead_id",
            "locale",
            "message",
            "organization",
            "phone",
            "profession",
            "source",
            "user_agent",
        }
    ),
    "emails/demo_request_notify.html": frozenset(
        {
            "admin_url",
            "created_at",
            "email",
            "full_name",
            "message",
            "organization",
            "organization_size",
            "phone",
            "role_name",
            "source",
            "type_structure",
        }
    ),
    "emails/weekly_operations_report.html": frozenset(
        {"days", "item", "pdf_url", "report", "report_url", "structure_name"}
    ),
    # Legacy generic workflow. Its free-text keys are explicit and remain
    # isolated to this reviewed legacy template until callers migrate.
    "email_template.html": frozenset(
        {
            "notification_type",
            "recipient_name",
            "subject",
            "content",
            "message",
            "action_url",
            "chat_url",
            "feedback_url",
            "new_request_url",
            "volunteer",
            "task",
        }
    ),
}


def _validate_email_context(template: str, context: dict | None) -> dict:
    """Reject accidental cross-tenant and internal object fields."""
    if context is None:
        return {}
    if not isinstance(context, dict):
        raise ValueError("Email context must be a mapping")
    allowed = _EMAIL_CONTEXT_ALLOWLISTS.get((template or "").strip())
    if allowed is None:
        raise ValueError("Unknown email template")
    unknown = set(context) - allowed
    if unknown:
        raise ValueError("Email context contains unknown fields")

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).strip().lower() in _EMAIL_CONTEXT_BLOCKED_KEYS:
                    return True
                if walk(child):
                    return True
        elif isinstance(value, (list, tuple, set)):
            return any(walk(child) for child in value)
        return False

    if walk(context):
        raise ValueError("Email context contains disallowed fields")
    return context


def _sanitize_for_log(value):
    """Return a single-line, control-character-safe log value."""
    if value is None:
        return None
    if isinstance(value, str):
        return "".join(
            ch if ch >= " " and ch not in "\x7f\r\n\t" else " " for ch in value
        ).strip()
    return value


def _fallback_log_purpose(purpose):
    """Return only an allowlisted category for local fallback diagnostics."""
    if isinstance(purpose, str) and purpose in _SAFE_FALLBACK_PURPOSES:
        return purpose
    return "generic"


def _is_sensitive_log_key(key: str) -> bool:
    normalized = (key or "").strip().lower()
    return any(part in normalized for part in _SENSITIVE_LOG_KEY_PARTS)


def mask_sensitive(data):
    """Return a log-safe copy of nested diagnostic data."""
    if isinstance(data, Mapping):
        masked = {}
        for key, value in data.items():
            key_text = str(key)
            if _is_sensitive_log_key(key_text):
                masked[key_text] = "***"
            else:
                masked[key_text] = mask_sensitive(value)
        return masked
    if isinstance(data, str):
        return _sanitize_for_log(data)
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        return [mask_sensitive(item) for item in data]
    return data


def _norm_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _log_mail_config_presence(*, purpose: str | None = None):
    cfg = current_app.config
    diagnostics = {
        "MAIL_SERVER": cfg.get("MAIL_SERVER"),
        "MAIL_PORT": cfg.get("MAIL_PORT"),
        "MAIL_USE_SSL": cfg.get("MAIL_USE_SSL"),
        "MAIL_USE_TLS": cfg.get("MAIL_USE_TLS"),
        "MAIL_USERNAME": cfg.get("MAIL_USERNAME"),
        "MAIL_PASSWORD_STATE": "SET" if cfg.get("MAIL_PASSWORD") else "NOT_SET",
        "MAIL_DEFAULT_SENDER": cfg.get("MAIL_DEFAULT_SENDER"),
    }
    masked = mask_sensitive(diagnostics)
    presence = {
        "MAIL_SERVER": bool(masked.get("MAIL_SERVER")),
        "MAIL_PORT": bool(masked.get("MAIL_PORT")),
        "MAIL_USE_SSL": masked.get("MAIL_USE_SSL") is not None,
        "MAIL_USE_TLS": masked.get("MAIL_USE_TLS") is not None,
        "MAIL_USERNAME": bool(masked.get("MAIL_USERNAME")),
        "MAIL_PASSWORD_STATE": masked.get("MAIL_PASSWORD_STATE"),
        "MAIL_DEFAULT_SENDER": bool(masked.get("MAIL_DEFAULT_SENDER")),
    }
    log_presence = {
        key: value for key, value in presence.items() if key != "MAIL_PASSWORD"
    }
    logger.info(
        "SMTP config loaded%s | config=%s",
        f" | purpose={purpose}" if purpose else "",
        log_presence,
    )
    return presence


def _email_hash(email: str) -> str:
    salt = current_app.config.get("MAIL_HASH_SALT") or current_app.config["SECRET_KEY"]
    return hashlib.sha256((f"{salt}|{email}").encode()).hexdigest()


def _client_ip() -> str | None:
    if not has_request_context():
        return None
    xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return request.headers.get("CF-Connecting-IP") or xff or request.remote_addr


def _client_ua() -> str | None:
    if not has_request_context():
        return None
    return request.headers.get("User-Agent")


def _log_email_event(
    email_h: str,
    purpose: str,
    outcome: str,
    reason: str | None,
    *,
    structure_id: int | None = None,
):
    try:
        sid = structure_id or current_structure_id()
        event_kwargs = dict(
            email_hash=email_h,
            purpose=(purpose or "generic")[:64],
            outcome=(outcome or "failed")[:16],
            reason=(reason or None),
            ip=(_client_ip() or None),
            ua=(_client_ua() or "")[:256],
        )
        if hasattr(EmailSendEvent, "structure_id"):
            event_kwargs["structure_id"] = sid
        db.session.add(EmailSendEvent(**event_kwargs))
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.warning(
            "EmailSendEvent logging failed | error_type=%s", type(e).__name__
        )
    except Exception as e:
        db.session.rollback()
        logger.warning(
            "EmailSendEvent logging unexpected error | error_type=%s",
            type(e).__name__,
        )


def _recent_sent(email_h: str, purpose: str, minutes: int) -> bool:
    since = datetime.now(UTC) - timedelta(minutes=int(minutes))
    try:
        row = (
            EmailSendEvent.query.filter(
                EmailSendEvent.email_hash == email_h,
                EmailSendEvent.purpose == purpose,
                EmailSendEvent.outcome == "sent",
                EmailSendEvent.created_at >= since,
            )
            .order_by(EmailSendEvent.created_at.desc())
            .first()
        )
        return row is not None
    except Exception as e:
        logger.warning(
            "Email dedupe check failed; continuing send path | error_type=%s",
            type(e).__name__,
        )
        return False


def _count_sent(email_h: str, purpose: str, window_minutes: int) -> int:
    since = datetime.now(UTC) - timedelta(minutes=int(window_minutes))
    try:
        return int(
            EmailSendEvent.query.filter(
                EmailSendEvent.email_hash == email_h,
                EmailSendEvent.purpose == purpose,
                EmailSendEvent.outcome == "sent",
                EmailSendEvent.created_at >= since,
            ).count()
        )
    except Exception as e:
        logger.warning(
            "Email rate-limit check failed; continuing send path | error_type=%s",
            type(e).__name__,
        )
        return 0


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


def _send_via_resend(
    *,
    recipient: str,
    subject: str,
    html_content: str,
    text_content: str | None,
    from_name: str,
    mail_sender: str,
    reply_to: str | None,
) -> bool:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        return False
    if not mail_sender:
        logger.error("Resend send failed: MAIL_DEFAULT_SENDER is missing")
        return False

    api_base = os.getenv("RESEND_API_BASE_URL", "https://api.resend.com").rstrip("/")
    endpoint = f"{api_base}/emails"
    payload = {
        "from": f"{from_name} <{mail_sender}>",
        "to": [recipient],
        "subject": subject,
        "html": html_content,
    }
    if text_content:
        payload["text"] = text_content
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        resp = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if resp.status_code in (200, 201, 202):
            return True
        logger.error(
            "Resend send failed | status=%s | response_body_redacted=true",
            resp.status_code,
        )
    except Exception as e:
        logger.error("Resend request failed | error_type=%s", type(e).__name__)
    return False


def send_notification_email(
    recipient,
    subject,
    template,
    context=None,
    *,
    purpose="generic",
    structure_id=None,
    force_sync=False,
):
    """
    Send notification email to recipient

    Args:
        recipient (str): Email address
        subject (str): Email subject
        template (str): Template filename
        context (dict): Template context variables

    Returns:
        bool: True if delivered or intentionally suppressed, False otherwise
    """
    try:
        sid = structure_id or current_structure_id()
        recipient = _norm_email(recipient)
        if not recipient:
            logger.warning("No recipient specified for email")
            _log_email_event(
                email_h=hashlib.sha256(b"empty").hexdigest(),
                purpose=purpose,
                outcome="suppressed",
                reason="empty_email",
                structure_id=sid,
            )
            return False
        # Some SMTP providers reject SMTPUTF8 recipients; fail fast with a clear log.
        try:
            recipient.encode("ascii")
        except UnicodeEncodeError:
            logger.error("Recipient email rejected: non_ascii_address")
            _log_email_event(
                email_h=_email_hash(recipient),
                purpose=purpose,
                outcome="suppressed",
                reason="non_ascii_email",
                structure_id=sid,
            )
            return False

        email_h = _email_hash(recipient)
        dedupe_min = int(current_app.config.get("MAIL_DEDUPE_MINUTES", 10))
        if _recent_sent(email_h, purpose, minutes=dedupe_min):
            _log_email_event(
                email_h=email_h,
                purpose=purpose,
                outcome="suppressed",
                reason=f"dedupe_{dedupe_min}m",
                structure_id=sid,
            )
            return True

        rl_window = int(current_app.config.get("MAIL_RL_WINDOW_MINUTES", 30))
        rl_max = int(current_app.config.get("MAIL_RL_MAX_SENT", 3))
        if _count_sent(email_h, purpose, window_minutes=rl_window) >= rl_max:
            _log_email_event(
                email_h=email_h,
                purpose=purpose,
                outcome="suppressed",
                reason=f"per_email_rl_{rl_max}_per_{rl_window}m",
                structure_id=sid,
            )
            return True

        # Dev/test safety: allow mocking email delivery without touching SMTP.
        if os.environ.get("MAIL_MOCK", "").lower() in ("true", "1", "yes"):
            logger.info(
                "[MAIL_MOCK] Email suppressed | recipient_present=%s | "
                "subject_length=%d | template=%s",
                bool(recipient),
                len(subject or ""),
                _sanitize_for_log(template),
            )
            _log_email_event(
                email_h=email_h,
                purpose=purpose,
                outcome="sent",
                reason="mail_mock",
                structure_id=sid,
            )
            return True

        # Prepare context
        context = _validate_email_context(template, context)

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
            logger.warning(
                "Email template render failed | error_type=%s | using fallback HTML",
                type(e).__name__,
            )
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

        broker = os.environ.get("CELERY_BROKER_URL") or os.environ.get("BROKER_URL")
        if broker:
            logger.info(
                "Email broker configured but bypassed; using direct send | "
                "purpose=%s | subject_length=%d",
                _sanitize_for_log(purpose),
                len(subject or ""),
            )

        # --- Direct SMTP ---
        cfg = current_app.config
        presence = _log_mail_config_presence(purpose=purpose)
        mail_server = cfg.get("MAIL_SERVER")
        mail_port = int(cfg.get("MAIL_PORT") or 0)
        mail_user = cfg.get("MAIL_USERNAME")
        mail_pass = cfg.get("MAIL_PASSWORD")
        mail_sender = cfg.get("MAIL_DEFAULT_SENDER") or mail_user
        from_name = cfg.get("MAIL_FROM_NAME") or "HelpChain"
        reply_to = cfg.get("MAIL_REPLY_TO") or mail_sender
        use_tls = bool(cfg.get("MAIL_USE_TLS"))
        use_ssl = bool(cfg.get("MAIL_USE_SSL"))
        resend_enabled = bool(os.getenv("RESEND_API_KEY", "").strip())
        demo_target = "contact@helpchain.live"

        if purpose == "demo_request_internal":
            recipient = demo_target
            if _norm_email(mail_user) != demo_target:
                logger.error("Demo notification SMTP config invalid: username_mismatch")
                _log_email_event(
                    email_h=email_h,
                    purpose=purpose,
                    outcome="failed",
                    reason="demo_mail_username_invalid",
                    structure_id=sid,
                )
                return False
            if _norm_email(mail_sender) != demo_target:
                logger.error("Demo notification SMTP config invalid: sender_mismatch")
                _log_email_event(
                    email_h=email_h,
                    purpose=purpose,
                    outcome="failed",
                    reason="demo_mail_default_sender_invalid",
                    structure_id=sid,
                )
                return False
            logger.info("Demo notification SMTP routing validated")

        if (
            not (mail_server and mail_port and mail_user and mail_pass and mail_sender)
            and not resend_enabled
        ):
            missing = []
            if not mail_server:
                missing.append("MAIL_SERVER")
            if not mail_port:
                missing.append("MAIL_PORT")
            if not mail_user:
                missing.append("MAIL_USERNAME")
            if not mail_pass:
                missing.append("MAIL_PASSWORD")
            if not mail_sender:
                missing.append("MAIL_DEFAULT_SENDER")
            logger.error(
                "SMTP not configured (missing %s) | purpose=%s | MAIL_SERVER=%s | MAIL_PORT=%s | MAIL_USE_SSL=%s | MAIL_USE_TLS=%s | MAIL_USERNAME=%s | MAIL_PASSWORD_STATE=%s | MAIL_DEFAULT_SENDER=%s",
                ", ".join(missing) or "MAIL_*",
                _sanitize_for_log(purpose),
                presence["MAIL_SERVER"],
                presence["MAIL_PORT"],
                presence["MAIL_USE_SSL"],
                presence["MAIL_USE_TLS"],
                presence["MAIL_USERNAME"],
                presence["MAIL_PASSWORD_STATE"],
                presence["MAIL_DEFAULT_SENDER"],
            )
            _log_email_event(
                email_h=email_h,
                purpose=purpose,
                outcome="failed",
                reason="smtp_not_configured",
                structure_id=sid,
            )
            return False

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{mail_sender}>"
        msg["To"] = recipient
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="helpchain.live")
        msg["Reply-To"] = reply_to or mail_user
        msg["X-Mailer"] = "HelpChain Mailer"
        msg["List-Unsubscribe"] = "<mailto:contact@helpchain.live>"

        magic_url = (context or {}).get("magic_link_url")
        text_fallback = (
            f"Votre lien de connexion HelpChain : {magic_url}"
            if magic_url
            else "Votre lien de connexion HelpChain est dans ce message."
        )
        msg.set_content(text_content or text_fallback)
        msg.add_alternative(html_content, subtype="html")

        # HTTP transport for providers like Resend (works on Render free egress rules).
        if _send_via_resend(
            recipient=recipient,
            subject=subject,
            html_content=html_content,
            text_content=(text_content or text_fallback),
            from_name=from_name,
            mail_sender=mail_sender,
            reply_to=(reply_to or mail_user),
        ):
            logger.info(
                "Email sent via Resend | subject_length=%d",
                len(subject or ""),
            )
            _log_email_event(
                email_h=email_h,
                purpose=purpose,
                outcome="sent",
                reason="resend_http",
                structure_id=sid,
            )
            return True

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
        except smtplib.SMTPAuthenticationError as smtp_auth_e:
            logger.error(
                "Direct SMTP auth failed | error_type=%s", type(smtp_auth_e).__name__
            )
            _log_email_event(
                email_h=email_h,
                purpose=purpose,
                outcome="failed",
                reason="smtp_auth_error",
                structure_id=sid,
            )
            return False
        except Exception as smtp_e:
            logger.error(
                "Direct SMTP send failed | error_type=%s", type(smtp_e).__name__
            )
            # Dev-friendly fallback: write to a local file for manual inspection.
            try:
                with open("sent_emails.txt", "a", encoding="utf-8") as f:
                    f.write(f"\n--- {utc_now().isoformat()} ---\n")
                    f.write(
                        f"recipient_present={bool(recipient)}\n"
                        f"subject_length={len(subject or '')}\n"
                        f"purpose={_fallback_log_purpose(purpose)}\n"
                        "[Email body redacted]\n"
                    )
            except Exception as e:
                print("EMAIL ERROR: fallback_write_failed")
                raise
            _log_email_event(
                email_h=email_h,
                purpose=purpose,
                outcome="failed",
                reason="smtp_error",
            )
            return False

        # Track analytics for sent email
        if analytics_available and analytics_service:
            analytics_service.track_event(
                event_type="email_sent",
                event_category="notification",
                context={
                    "template": template,
                    "recipient_present": bool(recipient),
                    "subject_length": len(subject or ""),
                },
            )

        logger.info(
            "Email sent successfully | subject_length=%d",
            len(subject or ""),
        )
        _log_email_event(email_h=email_h, purpose=purpose, outcome="sent", reason=None)
        return True

    except Exception as e:
        logger.error(
            "Failed to queue email | recipient_present=%s | error_type=%s",
            bool(recipient),
            type(e).__name__,
        )
        try:
            if recipient:
                _log_email_event(
                    email_h=_email_hash(_norm_email(recipient)),
                    purpose=purpose,
                    outcome="failed",
                    reason="unexpected_error",
                )
        except Exception as e:
            print("EMAIL ERROR: failure_audit_failed")
            raise

        # Track failed email queuing
        if analytics_available and analytics_service:
            analytics_service.track_event(
                event_type="email_queue_failed",
                event_category="notification",
                context={
                    "recipient_present": bool(recipient),
                    "template": template,
                    "error_type": type(e).__name__,
                },
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

"""
HelpChain Mail Service
Handles sending notification emails using Flask-Mail
"""

import logging
import time
from datetime import UTC, datetime

from flask import current_app, render_template
from flask_mail import Message

try:
    from ..analytics_service import analytics_service

    analytics_available = True
except ImportError:
    analytics_service = None
    analytics_available = False

logger = logging.getLogger(__name__)


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

        # Prepare context
        if context is None:
            context = {}

        # Add common context variables
        context.update(
            {
                "recipient_email": recipient,
                "sent_at": utc_now(),
                "unsubscribe_url": f"{current_app.config['FRONTEND_URL']}/api/notification/unsubscribe/{{token}}",
                "preferences_url": f"{current_app.config['FRONTEND_URL']}/notification_preferences",
                "privacy_url": f"{current_app.config['FRONTEND_URL']}/privacy",
                "terms_url": f"{current_app.config['FRONTEND_URL']}/terms",
            }
        )

        # Render HTML content
        html_content = render_template(template, **context)

        # Generate unique message ID
        message_id = f"notification_{recipient}_{template}_{int(time.time())}"

        # Import here to avoid circular imports
        from .tasks import send_email_task

        # Queue email task with retry
        send_email_task.delay(
            subject=subject,
            recipients=[recipient],
            html=html_content,
            message_id=message_id,
        )

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

        logger.info(f"Email queued successfully to {recipient}: {subject}")
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

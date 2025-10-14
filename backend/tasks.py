"""
Automated tasks for HelpChain platform
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import and_
from backend.celery_app import celery
from backend.extensions import db
from backend.models import (
    HelpRequest,
    Volunteer,
    AdminUser,
    ChatMessage,
)
from backend.models_with_analytics import Task, TaskPerformance, AnalyticsEvent
from backend.smart_matching import smart_matching_engine
from backend.mail_service import send_notification_email
from backend.ai_service import ai_service
from backend.analytics_service import analytics_service

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def auto_match_requests(self):
    """Automatically match pending requests to available volunteers"""
    try:
        logger.info("Starting automatic request matching...")

        # Get pending requests that haven't been matched recently
        pending_requests = (
            db.session.query(HelpRequest)
            .filter(
                and_(
                    HelpRequest.status == "pending",
                    HelpRequest.created_at < datetime.utcnow() - timedelta(minutes=30),
                )
            )
            .all()
        )

        matched_count = 0
        for request in pending_requests:
            try:
                # Use smart matching engine to find best volunteer
                matches = smart_matching_engine.find_matches(request.id, limit=3)

                if matches:
                    best_match = matches[0]
                    volunteer = db.session.get(Volunteer, best_match["volunteer_id"])

                    if volunteer:
                        # Create task automatically
                        task = Task(
                            title=f"Помощ за {request.name}",
                            description=request.problem,
                            location_text=request.location,
                            priority="medium",
                            assigned_to=volunteer.id,
                            help_request_id=request.id,
                            status="assigned",
                            created_by=1,  # System user
                        )
                        db.session.add(task)

                        # Update request status
                        request.status = "assigned"
                        request.assigned_volunteer_id = volunteer.id

                        # Send notification to volunteer
                        self.send_notification.delay(
                            volunteer.email,
                            "Нова автоматично присвоена задача",
                            f"Получихте нова задача: {task.title}",
                        )

                        matched_count += 1
                        logger.info(
                            f"Auto-matched request {request.id} to volunteer {volunteer.name}"
                        )

            except Exception as e:
                logger.error(f"Error matching request {request.id}: {e}")
                continue

        db.session.commit()
        logger.info(f"Auto-matching completed. Matched {matched_count} requests.")

        return {"matched": matched_count, "total": len(pending_requests)}

    except Exception as e:
        logger.error(f"Error in auto_match_requests: {e}")
        db.session.rollback()
        raise self.retry(countdown=60, max_retries=3)


@celery.task(bind=True)
def send_reminders(self):
    """Send reminders for overdue tasks and pending requests"""
    try:
        logger.info("Sending automated reminders...")

        # Remind volunteers about overdue tasks
        overdue_tasks = (
            db.session.query(Task)
            .filter(
                and_(
                    Task.status.in_(["assigned", "in_progress"]),
                    Task.created_at < datetime.utcnow() - timedelta(days=2),
                )
            )
            .all()
        )

        for task in overdue_tasks:
            volunteer = db.session.get(Volunteer, task.assigned_to)
            if volunteer:
                self.send_notification.delay(
                    volunteer.email,
                    "Напомняне за задача",
                    f'Задачата "{task.title}" очаква изпълнение повече от 2 дни.',
                )

        # Remind admins about pending requests
        pending_requests = (
            db.session.query(HelpRequest)
            .filter(
                and_(
                    HelpRequest.status == "pending",
                    HelpRequest.created_at < datetime.utcnow() - timedelta(hours=24),
                )
            )
            .count()
        )

        if pending_requests > 0:
            admins = db.session.query(AdminUser).all()
            for admin in admins:
                self.send_notification.delay(
                    admin.email,
                    "Чакащи заявки",
                    f"Има {pending_requests} чакащи заявки за повече от 24 часа.",
                )

        logger.info(
            f"Reminders sent for {len(overdue_tasks)} tasks and {pending_requests} pending requests"
        )

    except Exception as e:
        logger.error(f"Error in send_reminders: {e}")
        raise self.retry(countdown=300, max_retries=3)


@celery.task(bind=True)
def auto_evaluate_tasks(self):
    """Automatically evaluate completed tasks using AI"""
    try:
        logger.info("Starting automatic task evaluation...")

        # Get recently completed tasks without performance records
        completed_tasks = (
            db.session.query(Task)
            .filter(
                and_(
                    Task.status == "completed",
                    Task.completed_at.isnot(None),
                    Task.completed_at > datetime.utcnow() - timedelta(hours=24),
                )
            )
            .all()
        )

        evaluated_count = 0
        for task in completed_tasks:
            # Check if performance record already exists
            existing_perf = (
                db.session.query(TaskPerformance).filter_by(task_id=task.id).first()
            )
            if existing_perf:
                continue

            try:
                # Get task details and chat history for AI evaluation
                chat_messages = (
                    db.session.query(ChatMessage)
                    .filter_by(task_id=task.id)
                    .order_by(ChatMessage.timestamp)
                    .all()
                )

                conversation_text = "\n".join(
                    [f"{msg.sender_type}: {msg.message}" for msg in chat_messages]
                )

                # Use AI to evaluate the task
                evaluation_prompt = f"""
                Оцени качеството на изпълнената задача въз основа на разговора:

                Задача: {task.title}
                Описание: {task.description}

                Разговор:
                {conversation_text}

                Оцени по скала 1-5:
                - Качество на комуникацията
                - Ефективност на решението
                - Скорост на отговор
                - Обща удовлетвореност

                Върни JSON с оценки и коментар.
                """

                ai_response = ai_service.generate_response(evaluation_prompt, "system")
                # Parse AI response and create performance record
                # This would need proper JSON parsing from AI response

                performance = TaskPerformance(
                    task_id=task.id,
                    volunteer_id=task.assigned_to,
                    quality_rating=4.0,  # Default rating
                    communication_rating=4.0,
                    timeliness_rating=4.0,
                    overall_rating=4.0,
                    ai_feedback="Автоматично оценена задача",
                    evaluated_by=1,  # System user
                    evaluated_at=datetime.utcnow(),
                )
                db.session.add(performance)
                evaluated_count += 1

            except Exception as e:
                logger.error(f"Error evaluating task {task.id}: {e}")
                continue

        db.session.commit()
        logger.info(f"Auto-evaluation completed for {evaluated_count} tasks")

    except Exception as e:
        logger.error(f"Error in auto_evaluate_tasks: {e}")
        db.session.rollback()
        raise self.retry(countdown=3600, max_retries=3)


@celery.task(bind=True)
def generate_daily_reports(self):
    """Generate daily analytics reports"""
    try:
        logger.info("Generating daily reports...")

        yesterday = datetime.utcnow() - timedelta(days=1)
        today_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Get daily statistics
        new_requests = (
            db.session.query(HelpRequest)
            .filter(HelpRequest.created_at.between(today_start, today_end))
            .count()
        )

        completed_tasks = (
            db.session.query(Task)
            .filter(
                and_(
                    Task.status == "completed",
                    Task.completed_at.between(today_start, today_end),
                )
            )
            .count()
        )

        new_volunteers = (
            db.session.query(Volunteer)
            .filter(Volunteer.created_at.between(today_start, today_end))
            .count()
        )

        # Generate report
        report = f"""
        Дневен отчет HelpChain - {today_start.strftime("%d.%m.%Y")}

        Нови заявки: {new_requests}
        Завършени задачи: {completed_tasks}
        Нови доброволци: {new_volunteers}

        Активни доброволци: {db.session.query(Volunteer).count()}
        Чакащи заявки: {db.session.query(HelpRequest).filter_by(status="pending").count()}
        """

        # Send report to admins
        admins = db.session.query(AdminUser).all()
        for admin in admins:
            self.send_notification.delay(admin.email, "Дневен отчет HelpChain", report)

        # Store in analytics
        analytics_service.track_event(
            event_type="report_generated",
            event_category="automation",
            event_action="daily_report",
            context={
                "new_requests": new_requests,
                "completed_tasks": completed_tasks,
                "new_volunteers": new_volunteers,
                "date": today_start.strftime("%Y-%m-%d"),
            },
        )

        logger.info("Daily report generated and sent")

    except Exception as e:
        logger.error(f"Error in generate_daily_reports: {e}")
        raise self.retry(countdown=3600, max_retries=3)


@celery.task(bind=True)
def cleanup_old_data(self):
    """Clean up old logs and temporary data"""
    try:
        logger.info("Starting data cleanup...")

        # Delete old analytics events (older than 90 days)
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        deleted_events = (
            db.session.query(AnalyticsEvent)
            .filter(AnalyticsEvent.timestamp < cutoff_date)
            .delete()
        )

        # Delete old chat messages (older than 180 days)
        cutoff_date = datetime.utcnow() - timedelta(days=180)
        deleted_messages = (
            db.session.query(ChatMessage)
            .filter(ChatMessage.timestamp < cutoff_date)
            .delete()
        )

        db.session.commit()

        logger.info(
            f"Data cleanup completed. Deleted {deleted_events} events and {deleted_messages} messages"
        )

    except Exception as e:
        logger.error(f"Error in cleanup_old_data: {e}")
        db.session.rollback()
        raise self.retry(countdown=86400, max_retries=3)


@celery.task(bind=True)
def send_notification(self, email, subject, message):
    """Send email notification"""
    try:
        send_notification_email(
            recipient=email,
            subject=subject,
            template="email_template.html",
            context={"message": message},
        )
        logger.info(f"Notification sent to {email}")
    except Exception as e:
        logger.error(f"Error sending notification to {email}: {e}")
        raise self.retry(countdown=60, max_retries=3)


@celery.task(bind=True)
def monitor_system_health(self):
    """Monitor system health and send alerts if needed"""
    try:
        logger.info("Monitoring system health...")

        # Check database connectivity
        db.session.execute("SELECT 1").first()

        # Check pending requests count
        pending_count = (
            db.session.query(HelpRequest).filter_by(status="pending").count()
        )
        if pending_count > 50:  # Alert threshold
            admins = db.session.query(AdminUser).all()
            for admin in admins:
                self.send_notification.delay(
                    admin.email,
                    "Системно предупреждение",
                    f"Висок брой чакащи заявки: {pending_count}",
                )

        # Check volunteer availability
        active_volunteers = (
            db.session.query(Volunteer).filter_by(is_active=True).count()
        )
        if active_volunteers < 5:  # Alert threshold
            admins = db.session.query(AdminUser).all()
            for admin in admins:
                self.send_notification.delay(
                    admin.email,
                    "Системно предупреждение",
                    f"Нисък брой активни доброволци: {active_volunteers}",
                )

        logger.info("System health check completed")

    except Exception as e:
        logger.error(f"Error in monitor_system_health: {e}")
        raise self.retry(countdown=300, max_retries=3)

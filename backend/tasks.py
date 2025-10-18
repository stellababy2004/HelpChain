"""
Automated tasks for HelpChain platform
"""

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import and_

try:
    from celery_app import celery
except ImportError:
    from backend.celery_app import celery

try:
    from extensions import db
except ImportError:
    from backend.extensions import db

try:
    from models import (
        AdminUser,
        ChatMessage,
        HelpRequest,
        Volunteer,
    )
except ImportError:
    from backend.models import (
        AdminUser,
        ChatMessage,
        HelpRequest,
        Volunteer,
    )

try:
    from models_with_analytics import AnalyticsEvent, Task, TaskPerformance
except ImportError:
    from backend.models_with_analytics import AnalyticsEvent, Task, TaskPerformance

try:
    from sentiment_analysis import sentiment_analysis_service
except ImportError:
    from backend.sentiment_analysis import sentiment_analysis_service

try:
    from mail_service import send_notification_email
except ImportError:
    from backend.mail_service import send_notification_email

try:
    from ai_service import ai_service
except ImportError:
    from backend.ai_service import ai_service

try:
    from analytics_service import analytics_service
except ImportError:
    from backend.analytics_service import analytics_service

try:
    from smart_matching import smart_matching_service
except ImportError:
    from backend.smart_matching import smart_matching_service

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
                matches = smart_matching_service.find_best_matches(request.id, limit=3)

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
        raise self.retry(countdown=60, max_retries=3) from e


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
        raise self.retry(countdown=300, max_retries=3) from e


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
            existing_perf = db.session.query(TaskPerformance).filter_by(task_id=task.id).first()
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

                # TODO: Parse AI response and create performance record
                ai_service.generate_response(evaluation_prompt, "system")

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
        raise self.retry(countdown=3600, max_retries=3) from e


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
        raise self.retry(countdown=3600, max_retries=3) from e


@celery.task(bind=True)
def cleanup_old_data(self):
    """Clean up old logs and temporary data"""
    try:
        logger.info("Starting data cleanup...")

        # Delete old analytics events (older than 90 days)
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        deleted_events = (
            db.session.query(AnalyticsEvent).filter(AnalyticsEvent.timestamp < cutoff_date).delete()
        )

        # Delete old chat messages (older than 180 days)
        cutoff_date = datetime.utcnow() - timedelta(days=180)
        deleted_messages = (
            db.session.query(ChatMessage).filter(ChatMessage.timestamp < cutoff_date).delete()
        )

        db.session.commit()

        logger.info(
            f"Data cleanup completed. Deleted {deleted_events} events and "
            f"{deleted_messages} messages"
        )

    except Exception as e:
        logger.error(f"Error in cleanup_old_data: {e}")
        db.session.rollback()
        raise self.retry(countdown=86400, max_retries=3) from e


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
        raise self.retry(countdown=60, max_retries=3) from e


@celery.task(bind=True)
def process_ml_analysis(self, request_id):
    """Process ML analysis for help request categorization and volunteer matching"""
    try:
        logger.info(f"Processing ML analysis for request {request_id}")

        # Get request details
        request = db.session.get(HelpRequest, request_id)
        if not request:
            logger.error(f"Request {request_id} not found")
            return

        # AI-powered categorization
        # TODO: Parse AI response and update request
        # ai_service.generate_response(categorization_prompt, "system")

        # Update request with AI categorization
        request.category = "AI_analyzed"  # Placeholder
        request.priority = "medium"  # Placeholder
        request.ai_processed = True

        # Store analysis results in analytics
        analytics_service.track_event(
            event_type="ml_analysis",
            event_category="ai",
            event_action="request_categorized",
            context={
                "request_id": request_id,
                "category": request.category,
                "priority": request.priority,
            },
        )

        db.session.commit()
        logger.info(f"ML analysis completed for request {request_id}")

    except Exception as e:
        logger.error(f"Error in ML analysis for request {request_id}: {e}")
        db.session.rollback()
        raise self.retry(countdown=300, max_retries=3) from e


@celery.task(bind=True)
def update_realtime_stats(self):
    """Update real-time statistics and cache them in Redis"""
    try:
        logger.info("Updating real-time statistics...")

        # Calculate current statistics
        stats = {
            "total_requests": db.session.query(HelpRequest).count(),
            "pending_requests": db.session.query(HelpRequest).filter_by(status="pending").count(),
            "completed_requests": db.session.query(HelpRequest)
            .filter_by(status="completed")
            .count(),
            "total_volunteers": db.session.query(Volunteer).count(),
            "active_volunteers": db.session.query(Volunteer).filter_by(is_active=True).count(),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Cache in Redis (if available)
        try:
            from redis import Redis

            redis_client = Redis.from_url(celery.conf.broker_url)
            redis_client.setex("helpchain:stats", 300, json.dumps(stats))  # Cache for 5 minutes
        except Exception as redis_error:
            logger.warning(f"Redis caching failed: {redis_error}")

        # Store in analytics for historical tracking
        analytics_service.track_event(
            event_type="stats_update",
            event_category="system",
            event_action="realtime_stats",
            context=stats,
        )

        logger.info("Real-time statistics updated")
        return stats

    except Exception as e:
        logger.error(f"Error updating real-time stats: {e}")
        raise self.retry(countdown=60, max_retries=3) from e


@celery.task(bind=True)
def send_bulk_notifications(self, notifications):
    """Send bulk email notifications efficiently"""
    try:
        logger.info(f"Sending bulk notifications to {len(notifications)} recipients")

        success_count = 0
        for notification in notifications:
            try:
                send_notification_email(
                    recipient=notification["email"],
                    subject=notification["subject"],
                    template="email_template.html",
                    context={"message": notification["message"]},
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send notification to {notification['email']}: {e}")
                continue

        logger.info(f"Bulk notifications completed: {success_count}/{len(notifications)} sent")

        # Track analytics
        analytics_service.track_event(
            event_type="bulk_notification",
            event_category="communication",
            event_action="bulk_sent",
            context={
                "total": len(notifications),
                "successful": success_count,
                "failed": len(notifications) - success_count,
            },
        )

    except Exception as e:
        logger.error(f"Error in bulk notifications: {e}")
        raise self.retry(countdown=300, max_retries=3) from e


@celery.task(bind=True)
def process_request_immediately(self, request_data):
    """Process new help request immediately with AI analysis"""
    try:
        logger.info("Processing new request immediately")

        # Create request in database
        request = HelpRequest(
            name=request_data["name"],
            email=request_data["email"],
            message=request_data["message"],
            status="pending",
        )

        if "category" in request_data:
            request.title = request_data["category"]
        if "location" in request_data:
            request.location_text = request_data["location"]

        db.session.add(request)
        db.session.flush()  # Get request ID

        # Trigger immediate ML analysis
        self.process_ml_analysis.delay(request.id)

        # Try immediate matching
        self.auto_match_requests.delay()

        # Send confirmation email
        confirmation_message = f"""
        Здравейте {request.name},

        Вашата заявка за помощ е получена успешно.

        Ще се свържем с вас скоро след като намерим подходящ доброволец.

        Детайли на заявката:
        - Категория: {request.title or "Не е посочена"}
        - Локация: {request.location_text or "Не е посочена"}
        - Съобщение: {request.message}

        Благодаря, че използвате HelpChain!
        """

        self.send_notification.delay(
            request.email,
            "Заявката ви е получена - HelpChain",
            confirmation_message,
        )

        db.session.commit()
        logger.info(f"Request {request.id} processed immediately")

        return {"request_id": request.id, "status": "processed"}

    except Exception as e:
        logger.error(f"Error processing request immediately: {e}")
        db.session.rollback()
        raise self.retry(countdown=60, max_retries=3) from e


@celery.task(bind=True)
def generate_performance_report(self, volunteer_id=None, period="weekly"):
    """Generate detailed performance report for volunteer or all volunteers"""
    try:
        logger.info(f"Generating performance report for period: {period}")

        # Calculate date range
        if period == "weekly":
            start_date = datetime.utcnow() - timedelta(days=7)
        elif period == "monthly":
            start_date = datetime.utcnow() - timedelta(days=30)
        else:  # daily
            start_date = datetime.utcnow() - timedelta(days=1)

        # Get performance data
        if volunteer_id:
            # Single volunteer report
            volunteer = db.session.get(Volunteer, volunteer_id)
            if not volunteer:
                return {"error": "Volunteer not found"}

            performances = (
                db.session.query(TaskPerformance)
                .filter(
                    and_(
                        TaskPerformance.volunteer_id == volunteer_id,
                        TaskPerformance.evaluated_at >= start_date,
                    )
                )
                .all()
            )

            report = {
                "volunteer_name": volunteer.name,
                "volunteer_email": volunteer.email,
                "period": period,
                "total_tasks": len(performances),
                "avg_rating": (
                    sum(p.overall_rating for p in performances) / len(performances)
                    if performances
                    else 0
                ),
                "tasks_completed": len([p for p in performances if p.task.status == "completed"]),
            }
        else:
            # All volunteers report
            performances = (
                db.session.query(TaskPerformance)
                .filter(TaskPerformance.evaluated_at >= start_date)
                .all()
            )

            volunteer_stats = {}
            for perf in performances:
                vid = perf.volunteer_id
                if vid not in volunteer_stats:
                    volunteer_stats[vid] = {
                        "tasks": 0,
                        "total_rating": 0,
                        "completed": 0,
                    }
                volunteer_stats[vid]["tasks"] += 1
                volunteer_stats[vid]["total_rating"] += perf.overall_rating
                if perf.task.status == "completed":
                    volunteer_stats[vid]["completed"] += 1

            report = {
                "period": period,
                "total_performances": len(performances),
                "volunteers": [
                    {
                        "volunteer_id": vid,
                        "avg_rating": stats["total_rating"] / stats["tasks"],
                        "tasks_completed": stats["completed"],
                        "total_tasks": stats["tasks"],
                    }
                    for vid, stats in volunteer_stats.items()
                ],
            }

        # Send report via email
        if volunteer_id:
            volunteer = db.session.get(Volunteer, volunteer_id)
            self.send_notification.delay(
                volunteer.email,
                f"Отчет за представянето - {period}",
                f"Вашият отчет за периода е готов. Средна оценка: {report['avg_rating']:.1f}",
            )
        else:
            # Send to admins
            admins = db.session.query(AdminUser).all()
            for admin in admins:
                self.send_notification.delay(
                    admin.email,
                    f"Общ отчет за представянето - {period}",
                    f"Отчетът за всички доброволци е готов. "
                    f"Общо оценки: {report['total_performances']}",
                )

        logger.info(f"Performance report generated for period: {period}")
        return report

    except Exception as e:
        logger.error(f"Error generating performance report: {e}")
        raise self.retry(countdown=3600, max_retries=3) from e


@celery.task(bind=True)
def monitor_system_health(self):
    """Monitor system health and send alerts if needed"""
    try:
        logger.info("Monitoring system health...")

        # Check database connectivity
        db.session.execute("SELECT 1").first()

        # Check pending requests count
        pending_count = db.session.query(HelpRequest).filter_by(status="pending").count()
        if pending_count > 50:  # Alert threshold
            admins = db.session.query(AdminUser).all()
            for admin in admins:
                self.send_notification.delay(
                    admin.email,
                    "Системно предупреждение",
                    f"Висок брой чакащи заявки: {pending_count}",
                )

        # Check volunteer availability
        active_volunteers = db.session.query(Volunteer).filter_by(is_active=True).count()
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
        raise self.retry(countdown=300, max_retries=3) from e


@celery.task(bind=True)
def process_feedback_sentiment(self, feedback_id):
    """Process sentiment analysis for user feedback"""
    try:
        logger.info(f"Processing sentiment analysis for feedback {feedback_id}")

        result = sentiment_analysis_service.analyze_feedback(feedback_id)

        if "error" in result:
            logger.error(f"Error analyzing feedback {feedback_id}: {result['error']}")
            raise self.retry(countdown=60, max_retries=3)
        else:
            sentiment_label = result.get("sentiment_label", "unknown")
            logger.info(
                f"Successfully analyzed sentiment for feedback {feedback_id}: {sentiment_label}"
            )

        return result

    except Exception as e:
        logger.error(f"Error in process_feedback_sentiment for feedback {feedback_id}: {e}")
        raise self.retry(countdown=300, max_retries=3) from e

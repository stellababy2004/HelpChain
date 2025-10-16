"""
Advanced Analytics Service for HelpChain
Provides comprehensive analytics and user behavior tracking
"""

import json
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func

# Remove direct db import - we'll get it from current_app
# try:
#     from extensions import db
# except ImportError:
#     # Fallback for when imported as a module
#     from .extensions import db

try:
    from models_with_analytics import (
        AnalyticsEvent,
        ChatbotConversation,
        PerformanceMetrics,
        UserBehavior,
    )
except ImportError:
    # Fallback for when imported as a module
    from backend.models_with_analytics import (
        AnalyticsEvent,
        ChatbotConversation,
        PerformanceMetrics,
        UserBehavior,
    )
import logging

logger = logging.getLogger(__name__)


def get_db():
    """Get the database instance from current Flask app context"""
    from flask import current_app

    if current_app and "sqlalchemy" in current_app.extensions:
        return current_app.extensions["sqlalchemy"]
    else:
        # Fallback - try to import from extensions
        try:
            from extensions import db

            return db
        except ImportError:
            try:
                from backend.extensions import db

                return db
            except ImportError:
                raise RuntimeError("Could not get database instance") from None


class AdvancedAnalytics:
    """Advanced Analytics Service"""

    def __init__(self):
        self.cache_duration = 300  # 5 минути кеш
        self._cache = {}

    def track_event(
        self,
        event_type: str,
        event_category: str = None,
        event_action: str = None,
        event_label: str = None,
        event_value: int = None,
        context: dict[str, Any] = None,
    ):
        """Проследява събитие за аналитика с thread safety"""
        return self._safe_database_operation(
            self._track_event_impl,
            event_type,
            event_category,
            event_action,
            event_label,
            event_value,
            context,
        )

    def _track_event_impl(
        self,
        event_type: str,
        event_category: str = None,
        event_action: str = None,
        event_label: str = None,
        event_value: int = None,
        context: dict[str, Any] = None,
    ):
        """Internal implementation of track_event"""
        try:
            context = context or {}

            event = AnalyticsEvent(
                event_type=event_type,
                event_category=event_category,
                event_action=event_action,
                event_label=event_label,
                event_value=event_value,
                user_session=context.get("session_id"),
                user_type=context.get("user_type", "guest"),
                user_ip=context.get("ip_address"),
                user_agent=context.get("user_agent"),
                page_url=context.get("page_url"),
                page_title=context.get("page_title"),
                referrer=context.get("referrer"),
                load_time=context.get("load_time"),
                screen_resolution=context.get("screen_resolution"),
                device_type=context.get("device_type", "unknown"),
            )

            get_db().session.add(event)
            get_db().session.commit()

            # Обновяваме user behavior
            self._update_user_behavior_impl(context)

            return True

        except Exception as e:
            logger.error(f"Error tracking event: {e}")
            get_db().session.rollback()
            return False

    def track_performance(
        self,
        metric_type: str,
        metric_name: str,
        metric_value: float,
        unit: str = None,
        context: dict[str, Any] = None,
    ):
        """Проследява метрики за производителност с thread safety"""
        return self._safe_database_operation(
            self._track_performance_impl,
            metric_type,
            metric_name,
            metric_value,
            unit,
            context,
        )

    def _safe_database_operation(self, operation, *args, **kwargs):
        """Безопасно извършва database операция с proper Flask app context"""
        try:
            from flask import has_app_context

            # Проверяваме дали имаме Flask app context
            if has_app_context():
                # Ако сме в request context, изпълняваме директно
                return operation(*args, **kwargs)
            else:
                # Ако сме в background thread, трябва да създадем app context
                logger.warning(
                    "No Flask app context - skipping database operation for thread safety"
                )
                return False
        except Exception as e:
            logger.error(f"Error in safe database operation: {e}")
            return False

    def _track_performance_impl(
        self,
        metric_type: str,
        metric_name: str,
        metric_value: float,
        unit: str = None,
        context: dict[str, Any] = None,
    ):
        """Internal implementation of track_performance"""
        try:
            context = context or {}

            metric = PerformanceMetrics(
                metric_type=metric_type,
                metric_name=metric_name,
                metric_value=metric_value,
                unit=unit,
                endpoint=context.get("endpoint"),
                user_agent=context.get("user_agent"),
                request_size=context.get("request_size"),
                response_size=context.get("response_size"),
                context_data=json.dumps(context.get("metadata", {})),
            )

            get_db().session.add(metric)
            get_db().session.commit()

            return True

        except Exception as e:
            logger.error(f"Error tracking performance: {e}")
            get_db().session.rollback()
            return False

    def _update_user_behavior_impl(self, context: dict[str, Any]):
        """Обновява потребителското поведение"""
        try:
            session_id = context.get("session_id")
            if not session_id:
                return

            behavior = UserBehavior.query.filter_by(session_id=session_id).first()

            if not behavior:
                behavior = UserBehavior(
                    session_id=session_id,
                    user_type=context.get("user_type", "guest"),
                    entry_page=context.get("page_url"),
                    ip_address=context.get("ip_address"),
                    user_agent=context.get("user_agent"),
                    device_info=context.get("device_type"),
                    location=context.get("location"),
                )
                get_db().session.add(behavior)

            # Обновяваме метриките
            behavior.pages_visited += 1
            behavior.last_activity = datetime.utcnow()
            behavior.exit_page = context.get("page_url")

            if behavior.pages_visited > 1:
                behavior.bounce_rate = False

            # Обновяваме sequence от посетени страници
            pages_sequence = json.loads(behavior.pages_sequence or "[]")
            pages_sequence.append(
                {
                    "url": context.get("page_url"),
                    "timestamp": datetime.utcnow().isoformat(),
                    "title": context.get("page_title"),
                }
            )
            behavior.pages_sequence = json.dumps(
                pages_sequence[-20:]
            )  # Последните 20 страници

            get_db().session.commit()

        except Exception as e:
            logger.error(f"Error updating user behavior: {e}")
            get_db().session.rollback()

    def get_dashboard_analytics(self, days: int = 30) -> dict[str, Any]:
        """Получава подробна аналитика за dashboard"""
        try:
            from flask import current_app

            if not current_app:
                return self._get_fallback_analytics()

            cache_key = f"dashboard_analytics_{days}"
            if self._is_cached(cache_key):
                return self._cache[cache_key]

            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            analytics = {
                "overview": self._get_overview_metrics(start_date, end_date),
                "user_engagement": self._get_user_engagement(start_date, end_date),
                "chatbot_analytics": self._get_chatbot_analytics(start_date, end_date),
                "performance_metrics": self._get_performance_metrics(
                    start_date, end_date
                ),
                "conversion_funnel": self._get_conversion_funnel(start_date, end_date),
                "user_journey": self._get_user_journey_analytics(start_date, end_date),
                "real_time": self._get_real_time_metrics(),
            }

            self._cache[cache_key] = analytics
            return analytics

        except Exception as e:
            logger.error(f"Error getting dashboard analytics: {e}")
            return self._get_fallback_analytics()

    def _get_overview_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Общи метрики за периода"""
        try:
            from flask import current_app

            if not current_app:
                return {
                    "unique_visitors": 0,
                    "total_page_views": 0,
                    "avg_session_time": 0,
                    "bounce_rate": 0,
                    "conversion_rate": 0,
                }

            # Уникални посетители (по session_id)
            unique_visitors = (
                get_db()
                .session.query(func.count(func.distinct(UserBehavior.session_id)))
                .filter(UserBehavior.session_start.between(start_date, end_date))
                .scalar()
                or 0
            )

            # Общо page views
            total_page_views = (
                get_db()
                .session.query(func.count(AnalyticsEvent.id))
                .filter(
                    and_(
                        AnalyticsEvent.event_type == "page_view",
                        AnalyticsEvent.created_at.between(start_date, end_date),
                    )
                )
                .scalar()
                or 0
            )

            # Средно време на сесия
            avg_session_time = (
                get_db()
                .session.query(func.avg(UserBehavior.total_time_spent))
                .filter(UserBehavior.session_start.between(start_date, end_date))
                .scalar()
                or 0
            )

            # Bounce rate
            total_sessions = (
                get_db()
                .session.query(func.count(UserBehavior.id))
                .filter(UserBehavior.session_start.between(start_date, end_date))
                .scalar()
                or 0
            )

            bounced_sessions = (
                get_db()
                .session.query(func.count(UserBehavior.id))
                .filter(
                    and_(
                        UserBehavior.bounce_rate,
                        UserBehavior.session_start.between(start_date, end_date),
                    )
                )
                .scalar()
                or 0
            )

            bounce_rate = (
                (bounced_sessions / total_sessions * 100) if total_sessions > 0 else 0
            )

            # Конверсии
            conversions = (
                get_db()
                .session.query(func.count(UserBehavior.id))
                .filter(
                    and_(
                        UserBehavior.conversion_action.isnot(None),
                        UserBehavior.session_start.between(start_date, end_date),
                    )
                )
                .scalar()
                or 0
            )

            conversion_rate = (
                (conversions / total_sessions * 100) if total_sessions > 0 else 0
            )

            return {
                "unique_visitors": unique_visitors,
                "total_page_views": total_page_views,
                "avg_session_time": (
                    round(avg_session_time / 60, 2) if avg_session_time else 0
                ),  # в минути
                "bounce_rate": round(bounce_rate, 2),
                "total_sessions": total_sessions,
                "conversions": conversions,
                "conversion_rate": round(conversion_rate, 2),
            }
        except Exception as e:
            logger.error(f"Error in _get_overview_metrics: {e}")
            return {
                "unique_visitors": 0,
                "total_page_views": 0,
                "avg_session_time": 0,
                "bounce_rate": 0,
                "conversion_rate": 0,
            }

    def _get_user_engagement(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Метрики за потребителската ангажираност"""

        # Най-посещавани страници
        top_pages = (
            get_db()
            .session.query(
                AnalyticsEvent.page_url, func.count(AnalyticsEvent.id).label("views")
            )
            .filter(
                and_(
                    AnalyticsEvent.event_type == "page_view",
                    AnalyticsEvent.created_at.between(start_date, end_date),
                    AnalyticsEvent.page_url.isnot(None),
                )
            )
            .group_by(AnalyticsEvent.page_url)
            .order_by(func.count(AnalyticsEvent.id).desc())
            .limit(10)
            .all()
        )

        # Device breakdown
        device_stats = (
            get_db()
            .session.query(
                UserBehavior.device_info, func.count(UserBehavior.id).label("sessions")
            )
            .filter(UserBehavior.session_start.between(start_date, end_date))
            .group_by(UserBehavior.device_info)
            .all()
        )

        # Hourly activity pattern
        hourly_activity = []
        for hour in range(24):
            count = (
                get_db()
                .session.query(func.count(AnalyticsEvent.id))
                .filter(
                    and_(
                        AnalyticsEvent.event_type == "page_view",
                        AnalyticsEvent.created_at.between(start_date, end_date),
                        func.extract("hour", AnalyticsEvent.created_at) == hour,
                    )
                )
                .scalar()
                or 0
            )
            hourly_activity.append({"hour": hour, "activity": count})

        return {
            "top_pages": [{"url": url, "views": views} for url, views in top_pages],
            "device_breakdown": [
                {"device": device or "Unknown", "sessions": sessions}
                for device, sessions in device_stats
            ],
            "hourly_activity": hourly_activity,
        }

    def _get_chatbot_analytics(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Аналитика на чатбота"""

        # Общо разговори
        total_conversations = ChatbotConversation.query.filter(
            ChatbotConversation.created_at.between(start_date, end_date)
        ).count()

        # По тип отговор
        response_types = (
            get_db()
            .session.query(
                ChatbotConversation.response_type,
                func.count(ChatbotConversation.id).label("count"),
            )
            .filter(ChatbotConversation.created_at.between(start_date, end_date))
            .group_by(ChatbotConversation.response_type)
            .all()
        )

        # AI статистики
        ai_conversations = ChatbotConversation.query.filter(
            and_(
                ChatbotConversation.response_type == "ai",
                ChatbotConversation.created_at.between(start_date, end_date),
            )
        ).all()

        ai_stats = {
            "total_ai_responses": len(ai_conversations),
            "avg_confidence": (
                sum(c.ai_confidence or 0 for c in ai_conversations)
                / len(ai_conversations)
                if ai_conversations
                else 0
            ),
            "avg_processing_time": (
                sum(c.processing_time or 0 for c in ai_conversations)
                / len(ai_conversations)
                if ai_conversations
                else 0
            ),
            "total_tokens": sum(c.ai_tokens_used or 0 for c in ai_conversations),
        }

        # User ratings
        rated_conversations = ChatbotConversation.query.filter(
            and_(
                ChatbotConversation.user_rating.isnot(None),
                ChatbotConversation.created_at.between(start_date, end_date),
            )
        ).all()

        avg_rating = (
            sum(c.user_rating for c in rated_conversations) / len(rated_conversations)
            if rated_conversations
            else 0
        )

        return {
            "total_conversations": total_conversations,
            "response_types": dict(response_types),
            "ai_statistics": ai_stats,
            "average_rating": round(avg_rating, 2),
            "rated_conversations": len(rated_conversations),
        }

    def _get_performance_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Метрики за производителност"""

        # Average response times by endpoint
        response_times = (
            get_db()
            .session.query(
                PerformanceMetrics.endpoint,
                func.avg(PerformanceMetrics.metric_value).label("avg_time"),
            )
            .filter(
                and_(
                    PerformanceMetrics.metric_type == "response_time",
                    PerformanceMetrics.created_at.between(start_date, end_date),
                    PerformanceMetrics.endpoint.isnot(None),
                )
            )
            .group_by(PerformanceMetrics.endpoint)
            .order_by(func.avg(PerformanceMetrics.metric_value).desc())
            .limit(10)
            .all()
        )

        # System load over time
        daily_performance = []
        current_date = start_date
        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)

            avg_response = (
                get_db()
                .session.query(func.avg(PerformanceMetrics.metric_value))
                .filter(
                    and_(
                        PerformanceMetrics.metric_type == "response_time",
                        PerformanceMetrics.created_at.between(current_date, next_date),
                    )
                )
                .scalar()
                or 0
            )

            daily_performance.append(
                {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "avg_response_time": round(avg_response, 3),
                }
            )

            current_date = next_date

        return {
            "endpoint_performance": [
                {"endpoint": ep, "avg_time": round(time, 3)}
                for ep, time in response_times
            ],
            "daily_performance": daily_performance,
        }

    def _get_conversion_funnel(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Анализ на conversion funnel"""

        # Основни стъпки във funnel-а
        total_visitors = (
            get_db()
            .session.query(func.count(func.distinct(UserBehavior.session_id)))
            .filter(UserBehavior.session_start.between(start_date, end_date))
            .scalar()
            or 0
        )

        # Посетили форма за регистрация
        visited_register = (
            get_db()
            .session.query(func.count(func.distinct(AnalyticsEvent.user_session)))
            .filter(
                and_(
                    AnalyticsEvent.page_url.like("%register%"),
                    AnalyticsEvent.created_at.between(start_date, end_date),
                )
            )
            .scalar()
            or 0
        )

        # Започнали регистрация
        started_registration = (
            get_db()
            .session.query(func.count(func.distinct(AnalyticsEvent.user_session)))
            .filter(
                and_(
                    AnalyticsEvent.event_action == "form_start",
                    AnalyticsEvent.event_category == "registration",
                    AnalyticsEvent.created_at.between(start_date, end_date),
                )
            )
            .scalar()
            or 0
        )

        # Завършили регистрация - използваме conversion_action в UserBehavior
        completed_registration = (
            get_db()
            .session.query(func.count(UserBehavior.id))
            .filter(
                and_(
                    UserBehavior.conversion_action == "registration",
                    UserBehavior.session_start.between(start_date, end_date),
                )
            )
            .scalar()
            or 0
        )

        # Използвали чатбота
        chatbot_users = (
            get_db()
            .session.query(func.count(func.distinct(ChatbotConversation.session_id)))
            .filter(ChatbotConversation.created_at.between(start_date, end_date))
            .scalar()
            or 0
        )

        return {
            "total_visitors": total_visitors,
            "visited_register": visited_register,
            "started_registration": started_registration,
            "completed_registration": completed_registration,
            "chatbot_users": chatbot_users,
            "conversion_rates": {
                "visit_to_register_page": (
                    round(visited_register / total_visitors * 100, 2)
                    if total_visitors
                    else 0
                ),
                "register_page_to_start": (
                    round(started_registration / visited_register * 100, 2)
                    if visited_register
                    else 0
                ),
                "start_to_complete": (
                    round(completed_registration / started_registration * 100, 2)
                    if started_registration
                    else 0
                ),
                "overall_conversion": (
                    round(completed_registration / total_visitors * 100, 2)
                    if total_visitors
                    else 0
                ),
            },
        }

    def _get_user_journey_analytics(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Анализ на потребителските пътища"""

        # Най-чести entry points
        entry_pages = (
            get_db()
            .session.query(
                UserBehavior.entry_page, func.count(UserBehavior.id).label("entries")
            )
            .filter(
                and_(
                    UserBehavior.session_start.between(start_date, end_date),
                    UserBehavior.entry_page.isnot(None),
                )
            )
            .group_by(UserBehavior.entry_page)
            .order_by(func.count(UserBehavior.id).desc())
            .limit(10)
            .all()
        )

        # Най-чести exit points
        exit_pages = (
            get_db()
            .session.query(
                UserBehavior.exit_page, func.count(UserBehavior.id).label("exits")
            )
            .filter(
                and_(
                    UserBehavior.session_start.between(start_date, end_date),
                    UserBehavior.exit_page.isnot(None),
                )
            )
            .group_by(UserBehavior.exit_page)
            .order_by(func.count(UserBehavior.id).desc())
            .limit(10)
            .all()
        )

        # Най-чести page sequences
        common_paths = []
        sessions_with_sequences = UserBehavior.query.filter(
            and_(
                UserBehavior.session_start.between(start_date, end_date),
                UserBehavior.pages_sequence.isnot(None),
            )
        ).all()

        path_counter = Counter()
        for session in sessions_with_sequences:
            try:
                sequence = json.loads(session.pages_sequence or "[]")
                if len(sequence) >= 2:
                    path = " → ".join(
                        [page["url"].split("/")[-1] or "home" for page in sequence[:3]]
                    )
                    path_counter[path] += 1
            except Exception:
                continue

        common_paths = [
            {"path": path, "count": count}
            for path, count in path_counter.most_common(10)
        ]

        return {
            "top_entry_pages": [
                {"page": page, "entries": entries} for page, entries in entry_pages
            ],
            "top_exit_pages": [
                {"page": page, "exits": exits} for page, exits in exit_pages
            ],
            "common_user_paths": common_paths,
        }

    def _get_real_time_metrics(self) -> dict[str, Any]:
        """Real-time метрики (последният час)"""

        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        # Активни потребители (последните 30 минути)
        thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)
        active_users = (
            get_db()
            .session.query(func.count(func.distinct(UserBehavior.session_id)))
            .filter(UserBehavior.last_activity >= thirty_min_ago)
            .scalar()
            or 0
        )

        # Page views последният час
        recent_page_views = AnalyticsEvent.query.filter(
            and_(
                AnalyticsEvent.event_type == "page_view",
                AnalyticsEvent.created_at >= one_hour_ago,
            )
        ).count()

        # Чатбот съобщения последният час
        recent_chatbot = ChatbotConversation.query.filter(
            ChatbotConversation.created_at >= one_hour_ago
        ).count()

        return {
            "active_users_now": active_users,
            "page_views_last_hour": recent_page_views,
            "chatbot_messages_last_hour": recent_chatbot,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _is_cached(self, key: str) -> bool:
        """Проверява дали данните са в кеша"""
        if key not in self._cache:
            return False

        cache_time = self._cache.get(f"{key}_timestamp", 0)
        return (time.time() - cache_time) < self.cache_duration

    def _get_fallback_analytics(self) -> dict[str, Any]:
        """Fallback аналитика при грешка"""
        return {
            "overview": {
                "unique_visitors": 0,
                "total_page_views": 0,
                "avg_session_time": 0,
                "bounce_rate": 0,
                "conversion_rate": 0,
            },
            "error": "Failed to load analytics data",
        }


# Global instance
analytics_service = AdvancedAnalytics()

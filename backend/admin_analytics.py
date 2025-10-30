#!/usr/bin/env python
"""
Модул за административен анализ и статистики
Съдържа функции за изчисляване на статистики в реално време,
филтриране, търсене и геолокационна аналитика
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, or_

from models import AuditLog, HelpRequest, User, Volunteer

# Import db/cache from extensions with fallback
try:
    from . import extensions as _extensions
except ImportError:  # pragma: no cover - fallback for standalone execution
    import extensions as _extensions  # type: ignore

db = _extensions.db
cache = getattr(_extensions, "cache", None)


class AnalyticsEngine:
    """Клас за анализ на данни и статистики"""

    @staticmethod
    def _normalize_period(days=30, start_date=None, end_date=None):
        """Нормализира периода и връща (start_datetime, end_datetime, дни)."""
        end = end_date or datetime.now()
        start = start_date or end - timedelta(days=max(days - 1, 0))

        if start > end:
            start, end = end, start

        if isinstance(start, datetime):
            start_dt = start.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start_dt = datetime.combine(start, datetime.min.time())

        if isinstance(end, datetime):
            end_dt = end.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            end_dt = datetime.combine(end, datetime.max.time())

        period_days = max(1, (end_dt.date() - start_dt.date()).days + 1)
        return start_dt, end_dt, period_days

    @staticmethod
    def get_dashboard_stats(days=30, start_date=None, end_date=None):
        """
        Получава основни статистики за dashboard

        Args:
            days (int): Период за анализ в дни

        Returns:
            dict: Речник със статистики
        """
        start_date, end_date, period_days = AnalyticsEngine._normalize_period(
            days=days, start_date=start_date, end_date=end_date
        )

        cache_key = "admin_dashboard_stats"
        if cache:
            cache_key = "_".join(
                [
                    cache_key,
                    start_date.strftime("%Y%m%d"),
                    end_date.strftime("%Y%m%d"),
                ]
            )
            cached_stats = cache.get(cache_key)
            if cached_stats is not None:
                return cached_stats
        total_volunteers = db.session.query(Volunteer).count()
        total_users = db.session.query(User).count()

        total_requests = (
            db.session.query(func.count(HelpRequest.id))
            .filter(
                HelpRequest.created_at >= start_date,
                HelpRequest.created_at <= end_date,
            )
            .scalar()
            or 0
        )

        period_requests = total_requests

        status_counts = (
            db.session.query(
                HelpRequest.status, func.count(HelpRequest.id).label("count")
            )
            .filter(
                HelpRequest.created_at >= start_date,
                HelpRequest.created_at <= end_date,
            )
            .group_by(HelpRequest.status)
            .all()
        )

        status_stats = {status: count for status, count in status_counts}

        # Дневни статистики за графики
        daily_stats = AnalyticsEngine.get_daily_stats(
            days=period_days, start_date=start_date, end_date=end_date
        )

        # Геолокационни данни
        location_stats = AnalyticsEngine.get_location_stats()

        # Категории заявка (ако имаме поле category)
        category_stats = AnalyticsEngine.get_category_stats(
            start_date=start_date, end_date=end_date
        )

        stats = {
            "totals": {
                "requests": total_requests,
                "volunteers": total_volunteers,
                "users": total_users,
                "period_requests": period_requests,
            },
            "status_stats": status_stats,
            "daily_stats": daily_stats,
            "location_stats": location_stats,
            "category_stats": category_stats,
            "period_days": period_days,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": period_days,
            },
        }

        stats["performance_metrics"] = AnalyticsEngine.get_performance_metrics()
        stats["real_time"] = AnalyticsEngine.get_live_stats()

        if cache:
            cache.set(cache_key, stats, timeout=60)

        return stats

    @staticmethod
    def get_daily_stats(days=30, start_date=None, end_date=None):
        """Получава дневни статистики за избрания период."""
        start_dt, end_dt, _ = AnalyticsEngine._normalize_period(
            days=days, start_date=start_date, end_date=end_date
        )
        start_date_only = start_dt.date()
        end_date_only = end_dt.date()

        daily_requests = (
            db.session.query(
                func.date(HelpRequest.created_at).label("date"),
                func.count(HelpRequest.id).label("count"),
            )
            .filter(
                func.date(HelpRequest.created_at) >= start_date_only,
                func.date(HelpRequest.created_at) <= end_date_only,
            )
            .group_by(func.date(HelpRequest.created_at))
            .all()
        )

        daily_data = {}
        current_date = start_date_only
        while current_date <= end_date_only:
            daily_data[current_date.strftime("%Y-%m-%d")] = {
                "date": current_date.strftime("%d.%m"),
                "requests": 0,
                "volunteers": 0,
            }
            current_date += timedelta(days=1)

        # Попълваме данните
        for date_obj, count in daily_requests:
            # Конвертираме обекта date към string, ако не е
            if hasattr(date_obj, "strftime"):
                date_str = date_obj.strftime("%Y-%m-%d")
            else:
                # Ако е string, използваме директно
                date_str = str(date_obj)

            if date_str in daily_data:
                daily_data[date_str]["requests"] = count

        return list(daily_data.values())

    @staticmethod
    def _add_months(dt: datetime, months: int):
        """Връща нов datetime обект, изместен с указан брой месеци."""
        year = dt.year + (dt.month - 1 + months) // 12
        month = (dt.month - 1 + months) % 12 + 1
        return datetime(year, month, 1)

    @staticmethod
    def _generate_month_series(end_date: datetime, months: int):
        """Генерира списък с първия ден на всеки месец (най-стар -> най-нов)."""
        if months <= 0:
            return []

        end_month = datetime(end_date.year, end_date.month, 1)
        start_month = AnalyticsEngine._add_months(end_month, -(months - 1))

        series = []
        current = start_month
        for _ in range(months):
            series.append(current)
            current = AnalyticsEngine._add_months(current, 1)
        return series

    @staticmethod
    def _month_group_expression(column):
        """Връща SQLAlchemy израз за групиране по месец в зависимост от СУБД."""
        bind = db.session.get_bind() if db.session else None
        dialect_name = getattr(getattr(bind, "dialect", None), "name", "sqlite")

        if dialect_name == "postgresql":
            return func.to_char(column, "YYYY-MM")
        if dialect_name in {"mysql", "mariadb"}:
            return func.date_format(column, "%Y-%m")
        # SQLite и останалите използват strftime
        return func.strftime("%Y-%m", column)

    @staticmethod
    def get_location_stats():
        """Получава статистики по локации"""
        # Заявки по локации (ако имаме location поле)
        # За сега ще използваме доброволците
        volunteer_locations = (
            db.session.query(
                Volunteer.location, func.count(Volunteer.id).label("count")
            )
            .filter(Volunteer.location.isnot(None), Volunteer.location != "")
            .group_by(Volunteer.location)
            .all()
        )

        location_data = {}
        for location, count in volunteer_locations:
            if location:
                location_data[location] = count

        return location_data

    @staticmethod
    def get_category_stats(start_date=None, end_date=None):
        """Получава статистики по категории"""
        # Симулираме категории базирано на ключови думи в описанието
        categories = {
            "здраве": ["здраве", "болница", "лекар", "медицин", "лечение"],
            "документи": ["документи", "паспорт", "удостоверение", "справка"],
            "социална помощ": ["храна", "облекло", "парично", "социална"],
            "транспорт": ["транспорт", "превоз", "автобус", "такси"],
            "образование": ["образование", "училище", "университет", "обучение"],
            "друго": [],
        }

        query = db.session.query(
            HelpRequest.description,
            HelpRequest.message,
            HelpRequest.title,
            HelpRequest.created_at,
        )

        if start_date:
            query = query.filter(HelpRequest.created_at >= start_date)
        if end_date:
            query = query.filter(HelpRequest.created_at <= end_date)

        requests = query.all()
        category_counts = defaultdict(int)

        for description, message, title, _ in requests:
            description = (description or "").lower()
            message = (message or "").lower()
            title = (title or "").lower()

            text = f"{description} {message} {title}"

            categorized = False
            for category, keywords in categories.items():
                if any(keyword in text for keyword in keywords):
                    category_counts[category] += 1
                    categorized = True
                    break

            if not categorized:
                category_counts["друго"] += 1

        return dict(category_counts)

    @staticmethod
    def get_active_volunteers():
        """Получава активни доброволци (с активност през последните 30 дни)"""
        # За сега връщаме всички доброволци
        # В бъдеще можем да добавим tracking на активността
        return db.session.query(Volunteer).count()

    @staticmethod
    def get_trends_data(months=12):
        """Получава трендове за определен период"""
        if months <= 0:
            return {"labels": [], "requests": [], "volunteers": [], "completed": []}

        try:
            end_date = datetime.now()
            month_series = AnalyticsEngine._generate_month_series(end_date, months)
            if not month_series:
                return {"labels": [], "requests": [], "volunteers": [], "completed": []}

            start_period = month_series[0]
            end_period = AnalyticsEngine._add_months(month_series[-1], 1)

            month_expr = AnalyticsEngine._month_group_expression(HelpRequest.created_at)

            request_rows = (
                db.session.query(
                    month_expr.label("month"), func.count(HelpRequest.id).label("count")
                )
                .filter(
                    HelpRequest.created_at >= start_period,
                    HelpRequest.created_at < end_period,
                )
                .group_by("month")
                .all()
            )

            completed_rows = (
                db.session.query(
                    month_expr.label("month"), func.count(HelpRequest.id).label("count")
                )
                .filter(
                    HelpRequest.created_at >= start_period,
                    HelpRequest.created_at < end_period,
                    HelpRequest.status == "completed",
                )
                .group_by("month")
                .all()
            )

            volunteer_expr = AnalyticsEngine._month_group_expression(
                Volunteer.created_at
            )
            volunteer_rows = (
                db.session.query(
                    volunteer_expr.label("month"),
                    func.count(Volunteer.id).label("count"),
                )
                .filter(
                    Volunteer.created_at >= start_period,
                    Volunteer.created_at < end_period,
                )
                .group_by("month")
                .all()
            )

            request_counts = {row.month: row.count for row in request_rows if row.month}
            completed_counts = {
                row.month: row.count for row in completed_rows if row.month
            }
            volunteer_counts = {
                row.month: row.count for row in volunteer_rows if row.month
            }

            labels = [month.strftime("%Y-%m") for month in month_series]

            return {
                "labels": labels,
                "requests": [request_counts.get(label, 0) for label in labels],
                "completed": [completed_counts.get(label, 0) for label in labels],
                "volunteers": [volunteer_counts.get(label, 0) for label in labels],
            }

        except Exception as exc:  # pragma: no cover - safety fallback
            print(f"Trend aggregation failed, falling back to legacy approach: {exc}")

            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)

            trends = {
                "labels": [],
                "requests": [],
                "volunteers": [],
                "completed": [],
            }

            for i in range(months):
                month_start = start_date + timedelta(days=i * 30)
                month_end = month_start + timedelta(days=30)

                month_requests = (
                    db.session.query(HelpRequest)
                    .filter(
                        HelpRequest.created_at >= month_start,
                        HelpRequest.created_at < month_end,
                    )
                    .count()
                )

                month_completed = (
                    db.session.query(HelpRequest)
                    .filter(
                        HelpRequest.created_at >= month_start,
                        HelpRequest.created_at < month_end,
                        HelpRequest.status == "completed",
                    )
                    .count()
                )

                month_volunteers = (
                    db.session.query(Volunteer)
                    .filter(
                        Volunteer.created_at >= month_start,
                        Volunteer.created_at < month_end,
                    )
                    .count()
                )

                trends["labels"].append(month_start.strftime("%Y-%m"))
                trends["requests"].append(month_requests)
                trends["completed"].append(month_completed)
                trends["volunteers"].append(month_volunteers)

            return trends

    @staticmethod
    def get_predictions(months=3):
        """Прогнозира бъдещи тенденции с ML insights"""
        try:
            from advanced_analytics import AdvancedAnalytics

            advanced_analytics = AdvancedAnalytics()

            # Получаваме ML insights от AdvancedAnalytics
            ml_insights = advanced_analytics.generate_insights_report()

            # Взимаме исторически данни за последните 3 месеца
            trends = AnalyticsEngine.get_trends_data(months=3)

            predictions = {
                "labels": [],
                "requests_predicted": [],
                "volunteers_predicted": [],
                "ml_insights": ml_insights,
            }

            if trends["requests"]:
                # Използваме по-сложна прогноза базирана на ML insights
                avg_requests = sum(trends["requests"][-3:]) / len(
                    trends["requests"][-3:]
                )
                avg_volunteers = (
                    sum(trends["volunteers"][-3:]) / len(trends["volunteers"][-3:])
                    if trends["volunteers"]
                    else 0
                )

                # Фактор на растеж базиран на ML insights
                growth_factor = 1.05  # базов фактор

                # Ако има аномалии в трафика, коригираме прогнозата
                anomalies = ml_insights.get("anomalies", [])
                if any(
                    a.get("type") == "traffic_spike"
                    for a in anomalies
                    if isinstance(a, dict)
                ):
                    growth_factor = 1.15  # по-агресивен растеж при spike
                elif any(
                    a.get("type") == "traffic_drop"
                    for a in anomalies
                    if isinstance(a, dict)
                ):
                    growth_factor = 0.95  # по-консервативен при drop

                # Прогнозираме за следващите months
                for i in range(months):
                    future_requests = int(avg_requests * (growth_factor ** (i + 1)))
                    future_volunteers = int(avg_volunteers * (growth_factor ** (i + 1)))

                    future_date = datetime.now() + timedelta(days=(i + 1) * 30)
                    predictions["labels"].append(future_date.strftime("%Y-%m"))
                    predictions["requests_predicted"].append(max(0, future_requests))
                    predictions["volunteers_predicted"].append(
                        max(0, future_volunteers)
                    )

            return predictions

        except Exception as e:
            # Fallback към опростена версия при грешка
            print(f"ML predictions failed, using simple forecast: {e}")
            return AnalyticsEngine._get_simple_predictions(months)

    @staticmethod
    def _get_simple_predictions(months=3):
        """Опростена прогноза като fallback"""
        trends = AnalyticsEngine.get_trends_data(months=3)

        predictions = {
            "labels": [],
            "requests_predicted": [],
            "volunteers_predicted": [],
        }

        if trends["requests"]:
            avg_requests = sum(trends["requests"][-3:]) / len(trends["requests"][-3:])
            avg_volunteers = (
                sum(trends["volunteers"][-3:]) / len(trends["volunteers"][-3:])
                if trends["volunteers"]
                else 0
            )

            growth_factor = 1.1  # 10% ръст

            for i in range(months):
                future_requests = int(avg_requests * (growth_factor ** (i + 1)))
                future_volunteers = int(avg_volunteers * (growth_factor ** (i + 1)))

                future_date = datetime.now() + timedelta(days=(i + 1) * 30)
                predictions["labels"].append(future_date.strftime("%Y-%m"))
                predictions["requests_predicted"].append(max(0, future_requests))
                predictions["volunteers_predicted"].append(max(0, future_volunteers))

        return predictions

    @staticmethod
    def get_performance_metrics():
        """Performance метрики"""
        # Средно време за отговор
        avg_response_time = db.session.query(
            func.avg(
                func.julianday(HelpRequest.updated_at)
                - func.julianday(HelpRequest.created_at)
            )
        ).scalar()

        # Success rate
        total_requests = db.session.query(HelpRequest).count()
        completed_requests = (
            db.session.query(HelpRequest).filter_by(status="completed").count()
        )
        success_rate = (
            (completed_requests / total_requests * 100) if total_requests > 0 else 0
        )

        # Volunteer utilization
        active_volunteers = db.session.query(Volunteer).count()
        active_requests = (
            db.session.query(HelpRequest)
            .filter(HelpRequest.status.in_(["pending", "active", "in_progress"]))
            .count()
        )

        utilization_rate = min(100, (active_requests / max(active_volunteers, 1)) * 100)

        return {
            "avg_response_time_days": round(avg_response_time or 0, 2),
            "success_rate": round(success_rate, 2),
            "utilization_rate": round(utilization_rate, 2),
            "total_requests": total_requests,
            "completed_requests": completed_requests,
            "active_requests": active_requests,
            "active_volunteers": active_volunteers,
        }

    @staticmethod
    def get_success_rate():
        """Изчислява success rate"""
        total = db.session.query(HelpRequest).count()
        completed = db.session.query(HelpRequest).filter_by(status="completed").count()
        return round((completed / total * 100) if total > 0 else 0, 2)

    @staticmethod
    def get_geo_data():
        """Получава геолокационни данни за карта"""
        # Заявки с координати
        requests_with_location = (
            db.session.query(HelpRequest)
            .filter(HelpRequest.latitude.isnot(None), HelpRequest.longitude.isnot(None))
            .all()
        )

        # Доброволци с координати
        volunteers_with_location = (
            db.session.query(Volunteer)
            .filter(Volunteer.latitude.isnot(None), Volunteer.longitude.isnot(None))
            .all()
        )

        return {
            "requests": [
                {
                    "id": req.id,
                    "title": req.title,
                    "lat": req.latitude,
                    "lng": req.longitude,
                    "status": req.status,
                    "created_at": (
                        req.created_at.isoformat() if req.created_at else None
                    ),
                }
                for req in requests_with_location
            ],
            "volunteers": [
                {
                    "id": vol.id,
                    "name": vol.name,
                    "lat": vol.latitude,
                    "lng": vol.longitude,
                    "location": vol.location,
                    "skills": getattr(vol, "skills", ""),
                }
                for vol in volunteers_with_location
            ],
        }

    @staticmethod
    def get_live_stats():
        """Получава live статистики за dashboard"""
        today = datetime.now().date()
        week_ago = datetime.now() - timedelta(days=7)

        return {
            "requests_today": db.session.query(HelpRequest)
            .filter(func.date(HelpRequest.created_at) == today)
            .count(),
            "requests_this_week": db.session.query(HelpRequest)
            .filter(HelpRequest.created_at >= week_ago)
            .count(),
            "active_requests": db.session.query(HelpRequest)
            .filter(HelpRequest.status.in_(["pending", "active", "in_progress"]))
            .count(),
            "total_volunteers": db.session.query(Volunteer).count(),
            "success_rate": AnalyticsEngine.get_success_rate(),
        }


class RequestFilter:
    """Клас за филтриране на заявки"""

    @staticmethod
    def filter_requests(
        status=None,
        date_from=None,
        date_to=None,
        location=None,
        keyword=None,
        category=None,
        priority=None,
        page=1,
        per_page=20,
    ):
        """
        Филтрира заявки според зададени критерии

        Args:
            status (str): Статус на заявката
            date_from (datetime): Начална дата
            date_to (datetime): Крайна дата
            location (str): Локация
            keyword (str): Ключова дума за търсене
            category (str): Категория
            priority (str): Приоритет
            page (int): Номер на страница
            per_page (int): Записи на страница

        Returns:
            dict: Филтрирани резултати с пагинация
        """
        query = db.session.query(HelpRequest)

        # Филтър по статус
        if status and status != "all":
            query = query.filter(HelpRequest.status == status)

        # Филтър по дата
        if date_from:
            query = query.filter(HelpRequest.created_at >= date_from)
        if date_to:
            query = query.filter(HelpRequest.created_at <= date_to)

        # Филтър по ключова дума
        if keyword:
            search_term = f"%{keyword}%"
            query = query.filter(
                or_(
                    HelpRequest.title.ilike(search_term),
                    HelpRequest.description.ilike(search_term),
                    HelpRequest.message.ilike(search_term),
                    HelpRequest.name.ilike(search_term),
                    HelpRequest.email.ilike(search_term),
                )
            )

        # Сортиране по дата (най-нови първо)
        query = query.order_by(HelpRequest.created_at.desc())

        # Пагинация
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "items": paginated.items,
            "total": paginated.total,
            "pages": paginated.pages,
            "current_page": page,
            "has_prev": paginated.has_prev,
            "has_next": paginated.has_next,
            "prev_num": paginated.prev_num,
            "next_num": paginated.next_num,
        }

    @staticmethod
    def get_filter_options():
        """Получава опции за филтри"""
        # Статуси
        statuses = db.session.query(HelpRequest.status).distinct().all()

        status_options = [status[0] for status in statuses if status[0]]

        # Локации (от доброволци)
        locations = db.session.query(Volunteer.location).distinct().all()

        location_options = [loc[0] for loc in locations if loc[0]]

        return {
            "statuses": status_options,
            "locations": location_options,
            "categories": [
                "здраве",
                "документи",
                "социална помощ",
                "транспорт",
                "образование",
                "друго",
            ],
        }


class RealtimeUpdates:
    """Клас за updates в реално време"""

    @staticmethod
    def get_recent_activity(limit=10):
        """Получава последна активност"""
        # Последни заявки
        recent_requests = (
            db.session.query(HelpRequest)
            .order_by(HelpRequest.created_at.desc())
            .limit(limit)
            .all()
        )

        # Последни логове (ако има)
        try:
            recent_logs = (
                db.session.query(AuditLog)
                .order_by(AuditLog.created_at.desc())
                .limit(limit)
                .all()
            )
        except Exception:
            recent_logs = []

        activity = []

        # Добавяме заявки
        for req in recent_requests:
            activity.append(
                {
                    "type": "request",
                    "id": req.id,
                    "title": f"Нова заявка от {req.name}",
                    "description": (
                        req.description[:100] + "..."
                        if len(req.description) > 100
                        else req.description
                    ),
                    "timestamp": req.created_at,
                    "status": req.status,
                }
            )

        # Добавяме логове
        for log in recent_logs:
            activity.append(
                {
                    "type": "admin_action",
                    "id": log.id,
                    "title": f"Административно действие: {log.action}",
                    "description": log.details or "Няма подробности",
                    "timestamp": log.timestamp,
                    "admin_user": (
                        log.admin_user.username if log.admin_user else "Неизвестен"
                    ),
                }
            )

        # Сортираме по време
        activity.sort(key=lambda x: x["timestamp"], reverse=True)

        return activity[:limit]

    @staticmethod
    def get_live_stats():
        """Получава статистики за live обновяване"""
        return {
            "timestamp": datetime.now().isoformat(),
            "requests_today": db.session.query(HelpRequest)
            .filter(func.date(HelpRequest.created_at) == datetime.now().date())
            .count(),
            "requests_this_week": db.session.query(HelpRequest)
            .filter(HelpRequest.created_at >= datetime.now() - timedelta(days=7))
            .count(),
            "active_requests": db.session.query(HelpRequest)
            .filter(HelpRequest.status.in_(["Pending", "Активен", "In Progress"]))
            .count(),
            "total_volunteers": db.session.query(Volunteer).count(),
            "success_rate": AnalyticsEngine.get_success_rate(),
        }


if __name__ == "__main__":
    """Тестване на аналитичните функции"""
    from appy import app

    with app.app_context():
        print("=== Тестване на Analytics Engine ===")

        # Основни статистики
        stats = AnalyticsEngine.get_dashboard_stats()
        print(f"Общо заявки: {stats['totals']['requests']}")
        print(f"Общо доброволци: {stats['totals']['volunteers']}")
        print(f"Статистики по статуси: {stats['status_stats']}")

        # Геолокационни данни
        geo_data = AnalyticsEngine.get_geo_data()
        print(f"Заявки на картата: {len(geo_data['requests'])}")
        print(f"Доброволци на картата: {len(geo_data['volunteers'])}")

        # Филтриране
        filtered = RequestFilter.filter_requests(status="Pending", page=1)
        print(f"Филтрирани заявки: {filtered['total']}")

        # Последна активност
        activity = RealtimeUpdates.get_recent_activity()
        print(f"Последна активност: {len(activity)} записа")

        print("Тестването завърши успешно!")

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Модул за административен анализ и статистики
Съдържа функции за изчисляване на статистики в реално време,
филтриране, търсене и геолокационна аналитика
"""

from datetime import datetime, timedelta
from sqlalchemy import func, or_
from models import db, HelpRequest, Volunteer, AdminLog, User
from collections import defaultdict


class AnalyticsEngine:
    """Клас за анализ на данни и статистики"""

    @staticmethod
    def get_dashboard_stats(days=30):
        """
        Получава основни статистики за dashboard

        Args:
            days (int): Период за анализ в дни

        Returns:
            dict: Речник със статистики
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Основни числа
        total_requests = HelpRequest.query.count()
        total_volunteers = Volunteer.query.count()
        total_users = User.query.count()

        # Заявки за периода
        period_requests = HelpRequest.query.filter(
            HelpRequest.created_at >= start_date
        ).count()

        # Статуси на заявки
        status_counts = (
            db.session.query(
                HelpRequest.status, func.count(HelpRequest.id).label("count")
            )
            .group_by(HelpRequest.status)
            .all()
        )

        status_stats = {status: count for status, count in status_counts}

        # Дневни статистики за графики
        daily_stats = AnalyticsEngine.get_daily_stats(days)

        # Геолокационни данни
        location_stats = AnalyticsEngine.get_location_stats()

        # Категории заявки (ако имаме поле category)
        category_stats = AnalyticsEngine.get_category_stats()

        return {
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
            "period_days": days,
        }

    @staticmethod
    def get_daily_stats(days=30):
        """Получава дневни статистики за последните N дни"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        # Заявки по дни
        daily_requests = (
            db.session.query(
                func.date(HelpRequest.created_at).label("date"),
                func.count(HelpRequest.id).label("count"),
            )
            .filter(func.date(HelpRequest.created_at) >= start_date)
            .group_by(func.date(HelpRequest.created_at))
            .all()
        )

        # Създаваме списък за всички дни
        daily_data = {}
        current_date = start_date
        while current_date <= end_date:
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
    def get_category_stats():
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

        # Получаваме всички заявки
        requests = HelpRequest.query.all()
        category_counts = defaultdict(int)

        for req in requests:
            description = (req.description or "").lower()
            message = (req.message or "").lower()
            title = (req.title or "").lower()

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
        return Volunteer.query.count()

    @staticmethod
    def get_success_rate():
        """Изчислява процент успех (завършени заявки)"""
        total = HelpRequest.query.count()
        if total == 0:
            return 0

        completed = HelpRequest.query.filter(
            or_(
                HelpRequest.status == "Завършена",
                HelpRequest.status == "Resolved",
                HelpRequest.status == "Completed",
            )
        ).count()

        return round((completed / total) * 100, 2)

    @staticmethod
    def get_geo_data():
        """
        Получава геолокационни данни за карта

        Returns:
            dict: Данни за заявки и доброволци с координати
        """
        # Координати за основни градове в България
        city_coords = {
            "софия": [42.6977, 23.3219],
            "пловдив": [42.1354, 24.7453],
            "варна": [43.2141, 27.9147],
            "бургас": [42.5048, 27.4626],
            "русе": [43.8564, 25.9706],
            "стара загора": [42.4258, 25.6347],
            "плевен": [43.4170, 24.6167],
            "сливен": [42.6858, 26.3253],
            "добрич": [43.5723, 27.8274],
            "шумен": [43.2706, 26.9247],
        }

        geo_data = {"requests": [], "volunteers": [], "centers": []}

        # Доброволци по локации
        volunteers = Volunteer.query.filter(Volunteer.location.isnot(None)).all()

        location_counts = defaultdict(int)

        for volunteer in volunteers:
            if volunteer.location:
                location = volunteer.location.lower().strip()
                location_counts[location] += 1

                # Търсим координати
                coords = None
                for city, coord in city_coords.items():
                    if city in location:
                        coords = coord
                        break

                if coords:
                    geo_data["volunteers"].append(
                        {
                            "id": volunteer.id,
                            "name": volunteer.name,
                            "location": volunteer.location,
                            "lat": coords[0],
                            "lng": coords[1],
                            "type": "volunteer",
                        }
                    )

        # Заявки (използваме произволни координати около градовете)
        requests = HelpRequest.query.limit(50).all()  # Ограничаваме за производителност

        import random

        for i, req in enumerate(requests):
            # Избираме произволен град
            city_name, coords = random.choice(list(city_coords.items()))

            # Добавяме малка произволност към координатите
            lat_offset = random.uniform(-0.05, 0.05)
            lng_offset = random.uniform(-0.05, 0.05)

            geo_data["requests"].append(
                {
                    "id": req.id,
                    "name": req.name,
                    "title": req.title or "Заявка за помощ",
                    "status": req.status,
                    "lat": coords[0] + lat_offset,
                    "lng": coords[1] + lng_offset,
                    "type": "request",
                    "created_at": (
                        req.created_at.strftime("%d.%m.%Y") if req.created_at else ""
                    ),
                }
            )

        # Добавяме центрове на градове
        for city, coords in city_coords.items():
            volunteer_count = sum(1 for loc in location_counts.keys() if city in loc)
            if volunteer_count > 0:
                geo_data["centers"].append(
                    {
                        "city": city.title(),
                        "lat": coords[0],
                        "lng": coords[1],
                        "volunteer_count": volunteer_count,
                        "type": "center",
                    }
                )

        return geo_data


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
        query = HelpRequest.query

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
            HelpRequest.query.order_by(HelpRequest.created_at.desc()).limit(limit).all()
        )

        # Последни логове (ако има)
        try:
            recent_logs = (
                AdminLog.query.order_by(AdminLog.timestamp.desc()).limit(limit).all()
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
            "requests_today": HelpRequest.query.filter(
                func.date(HelpRequest.created_at) == datetime.now().date()
            ).count(),
            "requests_this_week": HelpRequest.query.filter(
                HelpRequest.created_at >= datetime.now() - timedelta(days=7)
            ).count(),
            "active_requests": HelpRequest.query.filter(
                HelpRequest.status.in_(["Pending", "Активен", "In Progress"])
            ).count(),
            "total_volunteers": Volunteer.query.count(),
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

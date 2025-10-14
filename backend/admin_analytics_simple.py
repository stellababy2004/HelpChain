#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Опростена версия на административен анализ и статистики
Работи с текущия Volunteer модел
"""

from datetime import datetime, timedelta
from sqlalchemy import func
from .models import db, Volunteer


class AnalyticsEngine:
    """Опростен клас за анализ на данни и статистики"""

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
        _start_date = end_date - timedelta(days=days)

        # Основни числа (само доброволци за момента)
        total_volunteers = Volunteer.query.count()

        # Симулирани данни за демонстрация
        total_requests = total_volunteers * 3  # Приблизително 3 заявки на доброволец
        total_users = total_volunteers * 2  # Приблизително 2 потребителя на доброволец
        period_requests = max(1, total_volunteers // 2)  # Нови заявки за периода

        # Симулирани статуси на заявки
        status_stats = {
            "pending": period_requests // 3,
            "active": period_requests // 3,
            "completed": period_requests // 3,
        }

        # Дневни статистики за графики
        daily_stats = AnalyticsEngine.get_daily_stats(days)

        # Геолокационни данни
        location_stats = AnalyticsEngine.get_location_stats()

        # Категории заявки (симулирани)
        category_stats = {
            "здраве": total_requests // 4,
            "документи": total_requests // 4,
            "транспорт": total_requests // 4,
            "други": total_requests // 4,
        }

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

        # Създаваме симулирани данни
        daily_data = []
        current_date = start_date

        while current_date <= end_date:
            # Симулирани стойности
            day_requests = max(0, 5 + (hash(str(current_date)) % 10) - 5)
            day_volunteers = max(0, 2 + (hash(str(current_date)) % 5) - 2)

            daily_data.append(
                {
                    "date": current_date.strftime("%d.%m"),
                    "requests": day_requests,
                    "volunteers": day_volunteers,
                }
            )
            current_date += timedelta(days=1)

        return daily_data

    @staticmethod
    def get_location_stats():
        """Анализира доброволци по географски локации"""
        # Взема реални локации от доброволци
        volunteers_by_location = (
            db.session.query(
                Volunteer.location, func.count(Volunteer.id).label("count")
            )
            .filter(Volunteer.location.isnot(None))
            .group_by(Volunteer.location)
            .all()
        )

        location_data = {}
        for location, count in volunteers_by_location:
            if location:
                location_data[location.strip()] = count

        # Добавяме симулирани данни ако няма реални
        if not location_data:
            location_data = {
                "София": 8,
                "Пловдив": 5,
                "Варна": 4,
                "Бургас": 3,
                "Стара Загора": 2,
            }

        return location_data

    @staticmethod
    def get_geo_data():
        """Получава геолокационни данни за картата"""
        # Опростени координати за демонстрация
        return [
            {"lat": 42.7339, "lng": 25.4858, "name": "Казанлък", "count": 3},
            {"lat": 42.6977, "lng": 23.3219, "name": "София", "count": 8},
            {"lat": 42.1354, "lng": 24.7453, "name": "Пловдив", "count": 5},
            {"lat": 43.2141, "lng": 27.9147, "name": "Варна", "count": 4},
            {"lat": 42.5048, "lng": 27.4626, "name": "Бургас", "count": 3},
        ]

    @staticmethod
    def get_success_rate():
        """Изчислява процент успешност"""
        # Симулирана стойност
        return 85.5

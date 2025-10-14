# -*- coding: utf-8 -*-
"""
Smart Matching System - AI-базиран мениджмънт на задачи
AI система за интелигентно съпоставяне на задачи с доброволци
"""

import json
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict

# Try relative imports first, fall back to absolute imports for standalone execution
try:
    from .extensions import db
    from .models import Volunteer
except ImportError:
    from extensions import db
    from models import Volunteer

from models_with_analytics import Task, TaskAssignment, TaskPerformance, AnalyticsEvent
from advanced_analytics import AdvancedAnalytics


class SmartMatchingEngine:
    """AI-базиран engine за съпоставяне на задачи с доброволци"""

    def __init__(self):
        self.analytics = AdvancedAnalytics()
        self.weights = {
            "skill_match": 0.4,
            "location_match": 0.2,
            "availability_match": 0.15,
            "performance_match": 0.15,
            "engagement_match": 0.1,
        }

    def find_best_matches(self, task_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Намира най-добрите съпоставяния за задача

        Args:
            task_id: ID на задачата
            limit: Максимален брой предложения

        Returns:
            List с предложения за доброволци
        """
        task = Task.query.get(task_id)
        if not task:
            return []

        # Вземи всички активни доброволци
        volunteers = Volunteer.query.filter_by(is_active=True).all()

        matches = []
        for volunteer in volunteers:
            match_score = self._calculate_match_score(task, volunteer)
            if match_score["overall"] > 0:  # Само ако има някакво съпоставяне
                matches.append(
                    {
                        "volunteer": volunteer,
                        "scores": match_score,
                        "recommendation_reason": self._generate_recommendation_reason(
                            task, volunteer, match_score
                        ),
                    }
                )

        # Сортирай по overall score и вземи топ резултатите
        matches.sort(key=lambda x: x["scores"]["overall"], reverse=True)
        return matches[:limit]

    def _calculate_match_score(
        self, task: Task, volunteer: Volunteer
    ) -> Dict[str, float]:
        """
        Изчислява match score между задача и доброволец

        Returns:
            Dict с различни score компоненти и overall score
        """
        scores = {
            "skill_match": self._calculate_skill_match(task, volunteer),
            "location_match": self._calculate_location_match(task, volunteer),
            "availability_match": self._calculate_availability_match(task, volunteer),
            "performance_match": self._calculate_performance_match(task, volunteer),
            "engagement_match": self._calculate_engagement_match(task, volunteer),
        }

        # Изчисли overall score с тегла
        overall = sum(
            scores[component] * self.weights[component] for component in scores.keys()
        )

        scores["overall"] = min(100.0, overall)  # Капни на 100
        return scores

    def _calculate_skill_match(self, task: Task, volunteer: Volunteer) -> float:
        """Изчислява skill match score (0-100)"""
        if not task.required_skills and not task.preferred_skills:
            return 50.0  # Неутрално ако няма изисквания

        volunteer_skills = set((volunteer.skills or "").lower().split(","))
        volunteer_skills = {
            skill.strip() for skill in volunteer_skills if skill.strip()
        }

        required_skills = set()
        if task.required_skills:
            try:
                required_skills = set(json.loads(task.required_skills))
            except:
                required_skills = set(task.required_skills.split(","))

        preferred_skills = set()
        if task.preferred_skills:
            try:
                preferred_skills = set(json.loads(task.preferred_skills))
            except:
                preferred_skills = set(task.preferred_skills.split(","))

        # Конвертирай в lowercase за сравнение
        required_skills = {skill.lower().strip() for skill in required_skills}
        preferred_skills = {skill.lower().strip() for skill in preferred_skills}

        # Изчисли match
        required_match = len(required_skills.intersection(volunteer_skills))
        preferred_match = len(preferred_skills.intersection(volunteer_skills))

        if not required_skills:
            # Само preferred skills
            score = (preferred_match / max(len(preferred_skills), 1)) * 100
        else:
            # Required + preferred
            required_score = (
                (required_match / len(required_skills)) * 70 if required_skills else 70
            )
            preferred_score = (
                (preferred_match / max(len(preferred_skills), 1)) * 30
                if preferred_skills
                else 30
            )
            score = required_score + preferred_score

        return min(100.0, score)

    def _calculate_location_match(self, task: Task, volunteer: Volunteer) -> float:
        """Изчислява location match score (0-100)"""
        if not task.location_required:
            return 100.0  # Не е важно местоположението

        if not task.latitude or not task.longitude:
            return 50.0  # Не можем да изчислим distance

        if not volunteer.latitude or not volunteer.longitude:
            return 30.0  # Доброволецът няма координати

        # Изчисли distance в км
        distance = self._calculate_distance(
            task.latitude, task.longitude, volunteer.latitude, volunteer.longitude
        )

        # Score базиран на distance
        if distance <= 5:  # Много близо
            return 100.0
        elif distance <= 10:  # Близо
            return 80.0
        elif distance <= 25:  # Приемливо
            return 60.0
        elif distance <= 50:  # Далече
            return 40.0
        else:  # Много далече
            return 20.0

    def _calculate_availability_match(self, task: Task, volunteer: Volunteer) -> float:
        """Изчислява availability match score (0-100)"""
        # За сега опростено - проверява дали доброволецът е активен
        # В бъдеще може да се добави календар система

        if volunteer.is_active:
            return 100.0
        else:
            return 0.0

    def _calculate_performance_match(self, task: Task, volunteer: Volunteer) -> float:
        """Изчислява performance match score базиран на минали резултати (0-100)"""
        # Вземи минали performance records за този доброволец
        performances = TaskPerformance.query.filter_by(volunteer_id=volunteer.id).all()

        if not performances:
            return 50.0  # Няма история, неутрално

        # Изчисли среден рейтинг
        ratings = []
        for perf in performances:
            if perf.quality_rating:
                ratings.append(perf.quality_rating)
            if perf.timeliness_rating:
                ratings.append(perf.timeliness_rating)
            if perf.communication_rating:
                ratings.append(perf.communication_rating)

        if not ratings:
            return 50.0

        avg_rating = sum(ratings) / len(ratings)
        completion_rate = len([p for p in performances if p.task_completed]) / len(
            performances
        )

        # Комбинирай rating и completion rate
        score = (avg_rating / 5.0) * 70 + completion_rate * 30
        return min(100.0, score)

    def _calculate_engagement_match(self, task: Task, volunteer: Volunteer) -> float:
        """Изчислява engagement match базиран на user behavior (0-100)"""
        try:
            # Използвай advanced analytics за user behavior
            user_events = self.analytics.get_user_events(str(volunteer.id))

            if not user_events:
                return 50.0

            # Анализирай engagement patterns
            recent_events = [
                e
                for e in user_events
                if e["timestamp"] > datetime.now() - timedelta(days=30)
            ]
            engagement_score = min(
                100.0, len(recent_events) * 2
            )  # 2 точки per event, max 100

            return engagement_score

        except Exception as e:
            print(f"Error calculating engagement match: {e}")
            return 50.0

    def _calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Изчислява distance между две точки в км (Haversine formula)"""
        R = 6371  # Earth radius in km

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
            math.radians(lat1)
        ) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _generate_recommendation_reason(
        self, task: Task, volunteer: Volunteer, scores: Dict[str, float]
    ) -> str:
        """Генерира текст защо този доброволец е препоръчан"""
        reasons = []

        if scores["skill_match"] > 80:
            reasons.append("Отлични умения за задачата")
        elif scores["skill_match"] > 60:
            reasons.append("Добри умения за задачата")

        if scores["location_match"] > 80:
            reasons.append("Много близо до местоположението")
        elif scores["location_match"] > 60:
            reasons.append("Приемливо разстояние")

        if scores["performance_match"] > 80:
            reasons.append("Отлична история на изпълнение")
        elif scores["performance_match"] > 60:
            reasons.append("Добра история на изпълнение")

        if not reasons:
            reasons.append("Подходящ кандидат")

        return ", ".join(reasons)

    def auto_assign_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Автоматично разпределя задача на най-добрия кандидат

        Returns:
            Dict с информация за assignment или None ако няма подходящ кандидат
        """
        matches = self.find_best_matches(task_id, limit=1)

        if not matches or matches[0]["scores"]["overall"] < 60:
            return None  # Няма достатъчно добър match

        task = Task.query.get(task_id)
        volunteer = matches[0]["volunteer"]

        # Създай assignment record
        assignment = TaskAssignment(
            task_id=task_id,
            volunteer_id=volunteer.id,
            skill_match_score=matches[0]["scores"]["skill_match"],
            location_match_score=matches[0]["scores"]["location_match"],
            availability_match_score=matches[0]["scores"]["availability_match"],
            performance_match_score=matches[0]["scores"]["performance_match"],
            overall_match_score=matches[0]["scores"]["overall"],
            assigned_at=datetime.utcnow(),
            status="assigned",
            assigned_by="auto",
        )

        # Update task
        task.assigned_to = volunteer.id
        task.assigned_at = datetime.utcnow()
        task.status = "assigned"

        db.session.add(assignment)
        db.session.commit()

        return {
            "task": task,
            "volunteer": volunteer,
            "assignment": assignment,
            "match_score": matches[0]["scores"]["overall"],
        }

    def get_matching_analytics(self) -> Dict[str, Any]:
        """Аналитика за ефективността на matching системата"""
        # Обща статистика
        total_tasks = Task.query.count()
        assigned_tasks = Task.query.filter(
            Task.status.in_(["assigned", "in_progress", "completed"])
        ).count()
        completed_tasks = Task.query.filter_by(status="completed").count()

        assignment_rate = (assigned_tasks / total_tasks * 100) if total_tasks > 0 else 0
        completion_rate = (
            (completed_tasks / assigned_tasks * 100) if assigned_tasks > 0 else 0
        )

        # Средни match scores
        assignments = TaskAssignment.query.all()
        if assignments:
            avg_skill_match = sum(a.skill_match_score for a in assignments) / len(
                assignments
            )
            avg_location_match = sum(a.location_match_score for a in assignments) / len(
                assignments
            )
            avg_performance_match = sum(
                a.performance_match_score for a in assignments
            ) / len(assignments)
            avg_overall_match = sum(a.overall_match_score for a in assignments) / len(
                assignments
            )
        else:
            avg_skill_match = avg_location_match = avg_performance_match = (
                avg_overall_match
            ) = 0

        return {
            "total_tasks": total_tasks,
            "assigned_tasks": assigned_tasks,
            "completed_tasks": completed_tasks,
            "assignment_rate": round(assignment_rate, 2),
            "completion_rate": round(completion_rate, 2),
            "avg_skill_match": round(avg_skill_match, 2),
            "avg_location_match": round(avg_location_match, 2),
            "avg_performance_match": round(avg_performance_match, 2),
            "avg_overall_match": round(avg_overall_match, 2),
        }


# Global instance
smart_matching_engine = SmartMatchingEngine()

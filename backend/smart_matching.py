"""
Smart Matching System - AI-базиран мениджмънт на задачи
AI система за интелигентно съпоставяне на HelpRequests с Volunteers
"""

import math
from datetime import UTC, datetime
from typing import Any

# Try relative imports first, fall back to absolute imports for standalone execution
try:
    from .ai_service import ai_service
    from .extensions import db
    from .models import HelpRequest, UserActivity, Volunteer
except ImportError:
    try:
        from ai_service import ai_service
        from backend.extensions import db
        from backend.models import HelpRequest, UserActivity, Volunteer
    except ImportError:
        # Fallback for Celery tasks - define minimal classes if analytics not available
        db = None
        HelpRequest = None
        Volunteer = None
        UserActivity = None
        ai_service = None


def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


class SmartMatchingService:
    """AI-базиран engine за съпоставяне на HelpRequests с Volunteers"""

    def __init__(self):
        # Matching weights - can be adjusted based on requirements
        self.weights = {
            "skill_match": 0.35,
            "location_match": 0.25,
            "availability_match": 0.15,
            "performance_match": 0.15,
            "urgency_match": 0.10,
        }

        # AI service for intelligent matching
        self.ai_service = ai_service

    def _load_help_request(self, request_id: int):
        """Return help request using SQLAlchemy 2.x session API when available."""
        help_request = None

        if db is not None:
            try:
                help_request = db.session.get(HelpRequest, request_id)
            except Exception:  # pragma: no cover - defensive for legacy setups
                help_request = None

        if help_request is None and hasattr(HelpRequest, "query"):
            help_request = HelpRequest.query.filter_by(id=request_id).first()

        return help_request

    def find_best_matches(self, request_id: int, limit: int = 5) -> list[dict[str, Any]]:
        """
        Намира най-добрите съпоставяния за HelpRequest

        Args:
            request_id: ID на HelpRequest
            limit: Максимален брой предложения

        Returns:
            List с предложения за доброволци
        """
        help_request = self._load_help_request(request_id)
        if not help_request:
            return []

        # Вземи всички активни доброволци
        volunteers = Volunteer.query.filter_by().all()  # All volunteers for now

        matches = []
        for volunteer in volunteers:
            match_score = self._calculate_match_score(help_request, volunteer)
            if match_score["overall"] > 0:  # Само ако има някакво съпоставяне
                matches.append(
                    {
                        "volunteer": volunteer,
                        "scores": match_score,
                        "recommendation_reason": self._generate_recommendation_reason(help_request, volunteer, match_score),
                    }
                )

        # Сортирай по overall score и вземи топ резултатите
        matches.sort(key=lambda x: x["scores"]["overall"], reverse=True)
        return matches[:limit]

    def _calculate_match_score(self, help_request: HelpRequest, volunteer: Volunteer) -> dict[str, float]:
        """
        Изчислява match score между HelpRequest и Volunteer

        Returns:
            Dict с различни score компоненти и overall score
        """
        scores = {
            "skill_match": self._calculate_skill_match(help_request, volunteer),
            "location_match": self._calculate_location_match(help_request, volunteer),
            "availability_match": self._calculate_availability_match(help_request, volunteer),
            "performance_match": self._calculate_performance_match(help_request, volunteer),
            "urgency_match": self._calculate_urgency_match(help_request, volunteer),
        }

        # Изчисли overall score с тегла
        overall = sum(scores[component] * self.weights[component] for component in scores.keys())

        scores["overall"] = min(100.0, overall)  # Капни на 100
        return scores

    def _calculate_skill_match(self, help_request: HelpRequest, volunteer: Volunteer) -> float:
        """Изчислява skill match score (0-100)"""
        if not volunteer.skills:
            return 25.0  # Неутрално ако доброволецът няма умения

        volunteer_skills = set((volunteer.skills or "").lower().split(","))
        volunteer_skills = {skill.strip() for skill in volunteer_skills if skill.strip()}

        # Extract keywords from help request title and description
        request_text = f"{help_request.title} {help_request.description}".lower()

        # Common help categories and their keywords
        skill_categories = {
            "medical": [
                "medical",
                "health",
                "doctor",
                "nurse",
                "hospital",
                "medicine",
                "care",
                "patient",
            ],
            "transport": ["transport", "drive", "car", "delivery", "moving", "vehicle"],
            "teaching": [
                "teaching",
                "education",
                "tutor",
                "school",
                "student",
                "learning",
                "math",
                "language",
            ],
            "technical": [
                "technical",
                "computer",
                "it",
                "repair",
                "fix",
                "maintenance",
                "technology",
            ],
            "household": [
                "household",
                "cleaning",
                "cooking",
                "gardening",
                "home",
                "repair",
            ],
            "elderly": ["elderly", "senior", "aged", "care", "assistance", "help"],
            "children": ["children", "kids", "childcare", "babysitting", "youth"],
            "emergency": ["emergency", "crisis", "urgent", "disaster", "rescue"],
            "legal": ["legal", "law", "advice", "counseling", "rights"],
            "psychological": [
                "psychological",
                "mental",
                "counseling",
                "therapy",
                "support",
            ],
        }

        # Find matching categories based on request text
        request_categories = set()
        for category, keywords in skill_categories.items():
            if any(keyword in request_text for keyword in keywords):
                request_categories.add(category)

        # If no categories found, use basic keyword matching
        if not request_categories:
            # Simple keyword matching with volunteer skills
            request_words = set(request_text.split())
            skill_matches = len(volunteer_skills.intersection(request_words))
            total_words = len(request_words)
            if total_words > 0:
                return min(100.0, (skill_matches / total_words) * 100)
            return 25.0

        # Category-based matching
        volunteer_categories = set()
        for skill in volunteer_skills:
            for category, keywords in skill_categories.items():
                if any(keyword in skill for keyword in keywords):
                    volunteer_categories.add(category)

        # Calculate match score
        category_matches = len(request_categories.intersection(volunteer_categories))
        if request_categories:
            category_score = (category_matches / len(request_categories)) * 80
        else:
            category_score = 40.0  # Default if no categories identified

        # Bonus for exact skill matches
        exact_matches = len(volunteer_skills.intersection(set(request_text.split())))
        exact_bonus = min(20.0, exact_matches * 5)

        return min(100.0, category_score + exact_bonus)

    def _calculate_location_match(self, help_request: HelpRequest, volunteer: Volunteer) -> float:
        """Изчислява location match score (0-100)"""
        # If request has no location, it's location-independent
        if not help_request.latitude or not help_request.longitude:
            return 100.0

        # If volunteer has no location, assume they can travel
        if not volunteer.latitude or not volunteer.longitude:
            return 60.0  # Moderate score for unknown location

        # Calculate distance in km
        distance = self._calculate_distance(
            help_request.latitude,
            help_request.longitude,
            volunteer.latitude,
            volunteer.longitude,
        )

        # Score based on distance
        if distance <= 2:  # Very close (walking distance)
            return 100.0
        elif distance <= 5:  # Close (short drive)
            return 90.0
        elif distance <= 10:  # Reasonable distance
            return 80.0
        elif distance <= 25:  # Acceptable distance
            return 60.0
        elif distance <= 50:  # Far but possible
            return 40.0
        else:  # Too far
            return 20.0

    def _calculate_availability_match(self, help_request: HelpRequest, volunteer: Volunteer) -> float:
        """Изчислява availability match score (0-100)"""
        # For now, assume all volunteers are available
        # In future, could check volunteer schedule/calendar
        return 100.0

    def _calculate_performance_match(self, help_request: HelpRequest, volunteer: Volunteer) -> float:
        """Изчислява performance match базиран на volunteer metrics (0-100)"""
        # Use volunteer rating, experience, and completion history
        rating_score = volunteer.rating * 20  # Rating out of 5, convert to 0-100 scale

        # Experience bonus
        experience_score = min(30.0, volunteer.experience * 0.1)  # 1 point per 10 experience

        # Completion rate bonus (assume based on total_tasks_completed)
        completion_score = min(30.0, volunteer.total_tasks_completed * 2)  # 2 points per task

        # Level bonus
        level_score = min(20.0, volunteer.level * 2)  # 2 points per level

        total_score = rating_score + experience_score + completion_score + level_score

        return min(100.0, total_score)

    def _calculate_urgency_match(self, help_request: HelpRequest, volunteer: Volunteer) -> float:
        """Изчислява urgency match - prefers experienced volunteers for urgent requests"""
        if help_request.priority == "urgent":
            # For urgent requests, prefer high-rated, experienced volunteers
            urgency_bonus = min(50.0, volunteer.rating * 10 + volunteer.experience * 0.5)
            return urgency_bonus
        elif help_request.priority == "high":
            urgency_bonus = min(30.0, volunteer.rating * 6 + volunteer.experience * 0.3)
            return urgency_bonus
        else:
            # Normal/low priority - no urgency bonus
            return 50.0

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Изчислява distance между две точки в км (Haversine formula)"""
        R = 6371  # Earth radius in km

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _generate_recommendation_reason(self, help_request: HelpRequest, volunteer: Volunteer, scores: dict[str, float]) -> str:
        """Генерира текст защо този доброволец е препоръчан"""
        reasons = []

        if scores["skill_match"] > 80:
            reasons.append("Отлични умения за тази задача")
        elif scores["skill_match"] > 60:
            reasons.append("Добри умения за тази задача")

        if scores["location_match"] > 80:
            reasons.append("Много близо до местоположението")
        elif scores["location_match"] > 60:
            reasons.append("Приемливо разстояние")

        if scores["performance_match"] > 80:
            reasons.append("Отлична история на изпълнение")
        elif scores["performance_match"] > 60:
            reasons.append("Добра история на изпълнение")

        if scores["urgency_match"] > 70 and help_request.priority in ["urgent", "high"]:
            reasons.append("Опитен доброволец за спешна задача")

        if not reasons:
            reasons.append("Подходящ кандидат")

        return ", ".join(reasons)

    def auto_assign_request(self, request_id: int) -> dict[str, Any] | None:
        """
        Автоматично разпределя HelpRequest на най-добрия кандидат

        Returns:
            Dict с информация за assignment или None ако няма подходящ кандидат
        """
        matches = self.find_best_matches(request_id, limit=1)

        if not matches or matches[0]["scores"]["overall"] < 60:
            return None  # Няма достатъчно добър match

        help_request = self._load_help_request(request_id)
        volunteer = matches[0]["volunteer"]

        # Update request status and assignment
        help_request.status = "assigned"
        help_request.updated_at = utc_now()

        # Create assignment record (if TaskAssignment model exists)
        try:
            from backend.models_with_analytics import TaskAssignment

            assignment = TaskAssignment(
                task_id=request_id,  # Using request_id as task_id for compatibility
                volunteer_id=volunteer.id,
                skill_match_score=matches[0]["scores"]["skill_match"],
                location_match_score=matches[0]["scores"]["location_match"],
                availability_match_score=matches[0]["scores"]["availability_match"],
                performance_match_score=matches[0]["scores"]["performance_match"],
                overall_match_score=matches[0]["scores"]["overall"],
                assigned_at=utc_now(),
                status="assigned",
                assigned_by="auto",
            )
            db.session.add(assignment)
        except ImportError:
            # TaskAssignment model not available, just update the request
            assignment = None

        db.session.commit()

        return {
            "help_request": help_request,
            "volunteer": volunteer,
            "assignment": assignment,
            "match_score": matches[0]["scores"]["overall"],
        }

    def get_ai_insights(self, request_id: int) -> dict[str, Any]:
        """Използва AI за допълнителни insights за matching"""
        if not self.ai_service:
            return {"insights": [], "confidence": 0.0}

        help_request = self._load_help_request(request_id)
        if not help_request:
            return {"insights": [], "confidence": 0.0}

        # Prepare context for AI
        context = f"""
        Help Request Details:
        Title: {help_request.title}
        Description: {help_request.description}
        Priority: {help_request.priority}
        Location: {help_request.location or "Not specified"}

        Please analyze this help request and provide insights about:
        1. What type of skills would be most helpful
        2. Any special considerations for volunteers
        3. Suggested volunteer characteristics
        """

        try:
            # Use AI service to get insights
            ai_response = self.ai_service.generate_response(
                user_msg="Analyze this help request for volunteer matching",
                context=context,
            )

            return {
                "insights": [ai_response.get("response", "")],
                "confidence": ai_response.get("confidence", 0.5),
                "ai_processed": True,
            }
        except Exception as e:
            print(f"AI insights failed: {e}")
            return {
                "insights": ["AI analysis not available"],
                "confidence": 0.0,
                "ai_processed": False,
            }

    def get_matching_analytics(self) -> dict[str, Any]:
        """Аналитика за ефективността на matching системата"""
        # Обща статистика
        total_requests = HelpRequest.query.count()
        assigned_requests = HelpRequest.query.filter(HelpRequest.status.in_(["assigned", "in_progress", "completed"])).count()
        completed_requests = HelpRequest.query.filter_by(status="completed").count()

        assignment_rate = (assigned_requests / total_requests * 100) if total_requests > 0 else 0
        completion_rate = (completed_requests / assigned_requests * 100) if assigned_requests > 0 else 0

        # Volunteer statistics
        total_volunteers = Volunteer.query.count()
        active_volunteers = Volunteer.query.filter(Volunteer.total_tasks_completed > 0).count()

        # Average ratings and experience
        volunteers = Volunteer.query.all()
        if volunteers:
            avg_rating = sum(v.rating for v in volunteers) / len(volunteers)
            avg_experience = sum(v.experience for v in volunteers) / len(volunteers)
            total_tasks = sum(v.total_tasks_completed for v in volunteers)
        else:
            avg_rating = avg_experience = total_tasks = 0

        return {
            "total_requests": total_requests,
            "assigned_requests": assigned_requests,
            "completed_requests": completed_requests,
            "assignment_rate": round(assignment_rate, 2),
            "completion_rate": round(completion_rate, 2),
            "total_volunteers": total_volunteers,
            "active_volunteers": active_volunteers,
            "avg_volunteer_rating": round(avg_rating, 2),
            "avg_volunteer_experience": round(avg_experience, 2),
            "total_tasks_completed": total_tasks,
        }


# Global instance
smart_matching_service = SmartMatchingService()

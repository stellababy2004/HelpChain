try:
    from .extensions import db
    from .models import Achievement, Volunteer
except ImportError:  # pragma: no cover - fallback for standalone scripts
    from backend.extensions import db
    from backend.models import Achievement, Volunteer


class GamificationService:
    """Service за управление на геймификация елементи"""

    @staticmethod
    def initialize_achievements():
        """Инициализира базовите постижения"""
        achievements = [
            # Task-based achievements
            Achievement(
                id="first_task",
                name="Първа помощ",
                description="Завърши първата си задача",
                icon="fas fa-star",
                category="tasks",
                requirement_type="count",
                requirement_value=1,
                rarity="common",
            ),
            Achievement(
                id="task_master",
                name="Майстор на задачите",
                description="Завърши 10 задачи",
                icon="fas fa-tasks",
                category="tasks",
                requirement_type="count",
                requirement_value=10,
                rarity="common",
            ),
            Achievement(
                id="hero",
                name="Герой",
                description="Завърши 50 задачи",
                icon="fas fa-trophy",
                category="tasks",
                requirement_type="count",
                requirement_value=50,
                rarity="rare",
            ),
            Achievement(
                id="legend",
                name="Легенда",
                description="Завърши 100 задачи",
                icon="fas fa-crown",
                category="tasks",
                requirement_type="count",
                requirement_value=100,
                rarity="epic",
            ),
            # Rating achievements
            Achievement(
                id="five_star",
                name="5 звезди",
                description="Получи среден рейтинг 5.0",
                icon="fas fa-star-half-alt",
                category="rating",
                requirement_type="value",
                requirement_value=50,  # 5.0 * 10
                rarity="rare",
            ),
            # Streak achievements
            Achievement(
                id="consistent",
                name="Последователен",
                description="Поддържай 7-дневна серия",
                icon="fas fa-calendar-check",
                category="streak",
                requirement_type="streak",
                requirement_value=7,
                rarity="common",
            ),
            Achievement(
                id="dedicated",
                name="Посветен",
                description="Поддържай 30-дневна серия",
                icon="fas fa-fire",
                category="streak",
                requirement_type="streak",
                requirement_value=30,
                rarity="rare",
            ),
            # Level achievements
            Achievement(
                id="level_up",
                name="Първо ниво",
                description="Достигни ниво 2",
                icon="fas fa-level-up-alt",
                category="level",
                requirement_type="value",
                requirement_value=2,
                rarity="common",
            ),
            Achievement(
                id="experienced",
                name="Опитен",
                description="Достигни ниво 10",
                icon="fas fa-graduation-cap",
                category="level",
                requirement_type="value",
                requirement_value=10,
                rarity="rare",
            ),
        ]

        for achievement in achievements:
            if not db.session.get(Achievement, achievement.id):
                db.session.add(achievement)

        db.session.commit()

    @staticmethod
    def check_achievements(volunteer):
        """Проверява и отключва постижения за доброволец"""
        achievements = Achievement.query.all()
        unlocked = []

        for achievement in achievements:
            if achievement.id in volunteer.achievements:
                continue

            unlocked_this = False

            # Coerce stored requirement_value (which may be a string) to int
            req_val = GamificationService._parse_requirement_value(achievement)

            if achievement.requirement_type == "count":
                if achievement.category == "tasks" and (
                    volunteer.total_tasks_completed >= req_val
                ):
                    unlocked_this = True
            elif achievement.requirement_type == "value":
                if (
                    achievement.category == "rating"
                    and int(volunteer.rating * 10) >= req_val
                ):
                    unlocked_this = True
                elif achievement.category == "level" and volunteer.level >= req_val:
                    unlocked_this = True
            elif achievement.requirement_type == "streak":
                if (
                    achievement.category == "streak"
                    and volunteer.streak_days >= req_val
                ):
                    unlocked_this = True

            if unlocked_this:
                volunteer.unlock_achievement(achievement.id)
                unlocked.append(achievement)

        if unlocked:
            db.session.commit()

        return unlocked

    @staticmethod
    def update_leaderboard():
        """Обновява класацията на доброволците"""
        volunteers = Volunteer.query.order_by(Volunteer.get_total_score().desc()).all()

        for rank, volunteer in enumerate(volunteers, 1):
            volunteer.rank = rank

        db.session.commit()

    @staticmethod
    def _parse_requirement_value(achievement):
        """Safely parse achievement.requirement_value to an integer.

        The DB column is a string historically; this helper makes numeric
        comparisons robust by returning an int (or 0 on failure).
        """
        val = getattr(achievement, "requirement_value", None)
        if val is None:
            return 0
        try:
            return int(val)
        except (TypeError, ValueError):
            try:
                return int(float(val))
            except (TypeError, ValueError):
                return 0

    @staticmethod
    def get_leaderboard(limit=10):
        """Връща топ доброволците"""
        volunteers = Volunteer.query.all()
        # Sort by total score
        volunteers.sort(key=lambda v: v.get_total_score(), reverse=True)
        return volunteers[:limit]

    @staticmethod
    def get_achievement_progress(volunteer, achievement):
        """Връща прогрес към постижение като процент"""
        if achievement.requirement_type == "count":
            if achievement.category == "tasks":
                current = volunteer.total_tasks_completed
            else:
                return 0
        elif achievement.requirement_type == "value":
            if achievement.category == "rating":
                current = int(volunteer.rating * 10)
            elif achievement.category == "level":
                current = volunteer.level
            else:
                return 0
        elif achievement.requirement_type == "streak":
            current = volunteer.streak_days
        else:
            return 0

        req_val = GamificationService._parse_requirement_value(achievement)
        if req_val <= 0:
            return 0

        return min(100, (current / req_val) * 100)

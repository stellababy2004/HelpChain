"""
Advanced Analytics Features
Real-time notifications, predictive analytics, και advanced visualizations
"""

import copy
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import load_only

from backend.extensions import db

try:
    from backend.models_with_analytics import AnalyticsEvent
except ImportError:
    from .models_with_analytics import AnalyticsEvent


MAX_ANALYTICS_EVENTS = int(os.getenv("ANALYTICS_MAX_EVENTS", 5000))
MAX_USER_EVENTS = int(os.getenv("ANALYTICS_MAX_USER_EVENTS", 500))
INSIGHTS_CACHE_TTL = int(os.getenv("ANALYTICS_INSIGHTS_CACHE_TTL", 120))
_INSIGHTS_CACHE = {"timestamp": 0.0, "data": None}


class AdvancedAnalytics:
    """Advanced analytics features за HelpChain"""

    def __init__(self, db_session=None):
        self.db = db_session or db

    def detect_anomalies(self, timeframe_days=7):
        """Detect unusual patterns в analytics data"""

        # Check if we have Flask application context
        try:
            from flask import current_app

            if not current_app:
                return []
        except RuntimeError:
            # Working outside of application context
            return []

        # Вземи данните за последните дни
        end_date = datetime.now()
        start_date = end_date - timedelta(days=timeframe_days * 2)  # Double timeframe за comparison

        events = self.get_events_by_hour(start_date, end_date)

        # Раздели на два периода - events е list от list-ове с dict-ове
        midpoint = start_date + timedelta(days=timeframe_days)
        baseline_events = []
        current_events = []

        for hour_events in events:
            for event in hour_events:
                if event["timestamp"] < midpoint:
                    baseline_events.append(event)
                else:
                    current_events.append(event)

        # Анализирай anomalies
        anomalies = []

        # Traffic anomalies
        baseline_avg = len(baseline_events) / timeframe_days if baseline_events else 0
        current_avg = len(current_events) / timeframe_days if current_events else 0

        if baseline_avg > 0:
            change_percent = ((current_avg - baseline_avg) / baseline_avg) * 100
            if abs(change_percent) > 30:  # 30% change threshold
                anomalies.append(
                    {
                        "type": ("traffic_spike" if change_percent > 0 else "traffic_drop"),
                        "severity": "high" if abs(change_percent) > 50 else "medium",
                        "value": change_percent,
                        "description": f"Traffic change of {change_percent:.1f}%",
                        "timestamp": datetime.now(),
                    }
                )

        # Error rate anomalies
        baseline_errors = len([e for e in baseline_events if "error" in str(e.get("details", "")).lower()])
        current_errors = len([e for e in current_events if "error" in str(e.get("details", "")).lower()])

        baseline_error_rate = (baseline_errors / len(baseline_events)) * 100 if baseline_events else 0
        current_error_rate = (current_errors / len(current_events)) * 100 if current_events else 0

        if current_error_rate > baseline_error_rate * 2 and current_error_rate > 5:
            anomalies.append(
                {
                    "type": "error_spike",
                    "severity": "critical",
                    "value": current_error_rate,
                    "description": f"Error rate increased to {current_error_rate:.1f}%",
                    "timestamp": datetime.now(),
                }
            )

        return anomalies

    def predict_user_behavior(self, user_id=None):
        """Predict user behavior patterns"""

        # Simple prediction model
        predictions = {
            "likely_to_convert": self._predict_conversion(user_id),
            "optimal_engagement_time": self._find_optimal_time(),
            "feature_recommendations": self._recommend_features(user_id),
            "churn_risk": self._calculate_churn_risk(user_id),
        }

        return predictions

    def _predict_conversion(self, user_id):
        """Predict conversion probability"""
        # Simplified conversion prediction
        if user_id:
            user_events = self.get_user_events(user_id)
            page_views = len([e for e in user_events if e["event_type"] == "page_view"])
            form_interactions = len([e for e in user_events if e["event_type"] == "form_interaction"])

            # Simple scoring
            score = (page_views * 0.1) + (form_interactions * 0.3)
            probability = min(score / 10, 0.95)  # Cap at 95%

            return {
                "probability": probability,
                "score": score,
                "factors": {
                    "page_engagement": page_views,
                    "form_interactions": form_interactions,
                },
            }

        return {"probability": 0.5, "score": 0, "factors": {}}

    def _find_optimal_time(self):
        """Find optimal time за user engagement"""
        from collections import defaultdict

        hour_engagement = defaultdict(int)

        # Анализирай engagement по часове
        events = self.get_recent_events(days=30)
        for event in events:
            hour = event["timestamp"].hour
            if event["event_type"] in ["form_interaction", "feature_usage"]:
                hour_engagement[hour] += 1

        # Намери peak hour
        if hour_engagement:
            optimal_hour = max(hour_engagement, key=hour_engagement.get)
            return {
                "hour": optimal_hour,
                "engagement_score": hour_engagement[optimal_hour],
                "recommendation": f"Best time for engagement: {optimal_hour}:00",
            }

        return {
            "hour": 14,
            "engagement_score": 0,
            "recommendation": "Insufficient data",
        }

    def _recommend_features(self, user_id):
        """Recommend features based на user behavior"""

        recommendations = []

        if user_id:
            events = self.get_user_events(user_id)
            used_features = set(e["category"] for e in events if e["event_type"] == "feature_usage")

            # All available features
            all_features = {
                "search",
                "volunteer_registration",
                "admin_panel",
                "messaging",
                "notifications",
            }
            unused_features = all_features - used_features

            # Prioritize recommendations
            feature_priorities = {
                "search": {"score": 0.9, "reason": "High conversion rate"},
                "volunteer_registration": {
                    "score": 0.8,
                    "reason": "Core functionality",
                },
                "messaging": {"score": 0.7, "reason": "Engagement booster"},
                "notifications": {"score": 0.6, "reason": "Retention tool"},
                "admin_panel": {"score": 0.3, "reason": "Advanced users only"},
            }

            for feature in unused_features:
                if feature in feature_priorities:
                    recommendations.append(
                        {
                            "feature": feature,
                            "score": feature_priorities[feature]["score"],
                            "reason": feature_priorities[feature]["reason"],
                        }
                    )

        return sorted(recommendations, key=lambda x: x["score"], reverse=True)[:3]

    def _calculate_churn_risk(self, user_id):
        """Calculate churn risk за user"""
        from datetime import datetime

        if not user_id:
            return {"risk": "unknown", "score": 0.5}

        # Последна активност
        events = self.get_user_events(user_id)
        if not events:
            return {"risk": "high", "score": 0.9, "reason": "No activity recorded"}

        last_activity = max(e["timestamp"] for e in events)
        days_since_activity = (datetime.now() - last_activity).days

        # Calculate risk
        if days_since_activity > 30:
            risk = "high"
            score = 0.8
        elif days_since_activity > 14:
            risk = "medium"
            score = 0.6
        elif days_since_activity > 7:
            risk = "low"
            score = 0.3
        else:
            risk = "very_low"
            score = 0.1

        return {
            "risk": risk,
            "score": score,
            "days_since_activity": days_since_activity,
            "last_seen": last_activity.strftime("%Y-%m-%d"),
        }

    def generate_insights_report(self):
        """Generate comprehensive insights report"""

        now_ts = time.time()
        cached_snapshot = _INSIGHTS_CACHE.get("data")
        if cached_snapshot is not None and now_ts - _INSIGHTS_CACHE.get("timestamp", 0.0) < INSIGHTS_CACHE_TTL:
            cached_copy = copy.deepcopy(cached_snapshot)
            metadata = cached_copy.setdefault("metadata", {})
            metadata["cached"] = True
            metadata.setdefault("cache_ttl", INSIGHTS_CACHE_TTL)
            metadata.setdefault("generated_at", cached_copy.get("generated_at"))
            return cached_copy

        # Check if we have Flask application context
        try:
            from flask import current_app

            if not current_app:
                return {
                    "generated_at": datetime.now().isoformat(),
                    "error": "No application context available",
                    "anomalies": [],
                    "predictions": {},
                    "kpi_trends": {},
                    "user_segments": {},
                    "recommendations": [],
                }
        except RuntimeError:
            # Working outside of application context
            return {
                "generated_at": datetime.now().isoformat(),
                "error": "Working outside of application context",
                "anomalies": [],
                "predictions": {},
                "kpi_trends": {},
                "user_segments": {},
                "recommendations": [],
            }

        report = {
            "generated_at": datetime.now().isoformat(),
            "anomalies": self.detect_anomalies(),
            "predictions": self.predict_user_behavior(),
            "kpi_trends": self._analyze_kpi_trends(),
            "user_segments": self._segment_users(),
            "recommendations": self._generate_recommendations(),
        }

        report["metadata"] = {
            "cached": False,
            "cache_ttl": INSIGHTS_CACHE_TTL,
            "generated_at": report["generated_at"],
        }

        _INSIGHTS_CACHE["data"] = copy.deepcopy(report)
        _INSIGHTS_CACHE["timestamp"] = now_ts

        return report

    def _analyze_kpi_trends(self):
        """Analyze KPI trends"""
        from datetime import datetime, timedelta

        # Get data за последните 4 седмици
        weeks_data = []

        for i in range(4):
            week_end = datetime.now() - timedelta(weeks=i)
            week_start = week_end - timedelta(weeks=1)

            week_events = self.get_events_in_range(week_start, week_end)

            weeks_data.append(
                {
                    "week": f"Week {4 - i}",
                    "total_events": len(week_events),
                    "unique_users": len(set(e["user_id"] for e in week_events if e["user_id"])),
                    "page_views": len([e for e in week_events if e["event_type"] == "page_view"]),
                    "conversions": len([e for e in week_events if e["event_type"] == "form_interaction"]),
                }
            )

        # Calculate trends
        trends = {}
        for metric in ["total_events", "unique_users", "page_views", "conversions"]:
            values = [week[metric] for week in weeks_data]
            if len(values) >= 2:
                trend = "increasing" if values[-1] > values[0] else "decreasing"
                change = ((values[-1] - values[0]) / values[0] * 100) if values[0] > 0 else 0
                trends[metric] = {"trend": trend, "change_percent": change}

        return {"weekly_data": weeks_data, "trends": trends}

    def _segment_users(self):
        """Segment users based на behavior"""

        segments = {
            "power_users": {
                "count": 0,
                "criteria": "High activity, multiple features used",
            },
            "regular_users": {
                "count": 0,
                "criteria": "Moderate activity, core features",
            },
            "new_users": {"count": 0, "criteria": "Recent registration, exploring"},
            "inactive_users": {"count": 0, "criteria": "Low activity or churned"},
        }

        # Simplified segmentation logic
        recent_events = self.get_recent_events(days=30)
        user_activity = {}

        for event in recent_events:
            if event["user_id"]:
                if event["user_id"] not in user_activity:
                    user_activity[event["user_id"]] = {"events": 0, "features": set()}

                user_activity[event["user_id"]]["events"] += 1
                if event["event_type"] == "feature_usage":
                    user_activity[event["user_id"]]["features"].add(event["category"])

        # Classify users
        for _user_id, activity in user_activity.items():
            events_count = activity["events"]
            features_count = len(activity["features"])

            if events_count > 50 and features_count > 3:
                segments["power_users"]["count"] += 1
            elif events_count > 10 and features_count > 1:
                segments["regular_users"]["count"] += 1
            elif events_count > 0:
                segments["new_users"]["count"] += 1
            else:
                segments["inactive_users"]["count"] += 1

        return segments

    def _generate_recommendations(self):
        """Generate actionable recommendations"""

        recommendations = [
            {
                "type": "performance",
                "priority": "high",
                "title": "Optimize page load times",
                "description": "Pages loading >2s show 30% higher bounce rate",
                "action": "Enable caching and optimize images",
            },
            {
                "type": "engagement",
                "priority": "medium",
                "title": "Add onboarding flow",
                "description": "New users drop off without guidance",
                "action": "Create interactive tutorial for new volunteers",
            },
            {
                "type": "conversion",
                "priority": "high",
                "title": "Simplify registration form",
                "description": "Form abandonment rate at 45%",
                "action": "Reduce form fields and add progress indicator",
            },
        ]

        return recommendations

    # Helper methods
    def get_events_by_hour(self, start_date, end_date):
        """Get events grouped by hour"""
        # Check if we have Flask application context
        try:
            from flask import current_app

            if not current_app:
                return []
        except RuntimeError:
            # Working outside of application context
            return []

        try:
            query = (
                AnalyticsEvent.query.options(
                    load_only(
                        AnalyticsEvent.created_at,
                        AnalyticsEvent.event_type,
                        AnalyticsEvent.event_label,
                        AnalyticsEvent.event_action,
                        AnalyticsEvent.user_type,
                        AnalyticsEvent.page_url,
                    )
                )
                .filter(
                    AnalyticsEvent.created_at >= start_date,
                    AnalyticsEvent.created_at <= end_date,
                )
                .order_by(AnalyticsEvent.created_at.desc())
            )

            if MAX_ANALYTICS_EVENTS:
                query = query.limit(MAX_ANALYTICS_EVENTS)

            events = query.all()

            # Group by hour
            events_by_hour = defaultdict(list)
            for event in events:
                hour_key = event.created_at.replace(minute=0, second=0, microsecond=0)
                events_by_hour[hour_key].append(
                    {
                        "timestamp": event.created_at,
                        "event_type": event.event_type,
                        "details": event.event_label or event.event_action,
                        "user_type": event.user_type,
                        "page_url": event.page_url,
                    }
                )

            return list(events_by_hour.values())
        except Exception as e:
            print(f"Error getting events by hour: {e}")
            return []

    def get_user_events(self, user_id):
        """Get all events για specific user"""
        # Check if we have Flask application context
        try:
            from flask import current_app

            if not current_app:
                return []
        except RuntimeError:
            # Working outside of application context
            return []

        try:
            query = (
                AnalyticsEvent.query.options(
                    load_only(
                        AnalyticsEvent.created_at,
                        AnalyticsEvent.event_type,
                        AnalyticsEvent.event_category,
                        AnalyticsEvent.event_action,
                        AnalyticsEvent.event_label,
                        AnalyticsEvent.page_url,
                    )
                )
                .filter(AnalyticsEvent.user_session == str(user_id))
                .order_by(AnalyticsEvent.created_at.desc())
            )

            if MAX_USER_EVENTS:
                query = query.limit(MAX_USER_EVENTS)

            events = query.all()

            return [
                {
                    "timestamp": event.created_at,
                    "event_type": event.event_type,
                    "category": event.event_category,
                    "action": event.event_action,
                    "details": event.event_label,
                    "page_url": event.page_url,
                }
                for event in events
            ]
        except Exception as e:
            print(f"Error getting user events: {e}")
            return []

    def get_recent_events(self, days=7):
        """Get recent events"""
        # Check if we have Flask application context
        try:
            from flask import current_app

            if not current_app:
                return []
        except RuntimeError:
            # Working outside of application context
            return []

        try:
            start_date = datetime.now() - timedelta(days=days)
            query = (
                AnalyticsEvent.query.options(
                    load_only(
                        AnalyticsEvent.created_at,
                        AnalyticsEvent.event_type,
                        AnalyticsEvent.event_category,
                        AnalyticsEvent.event_action,
                        AnalyticsEvent.user_session,
                        AnalyticsEvent.user_type,
                        AnalyticsEvent.page_url,
                    )
                )
                .filter(AnalyticsEvent.created_at >= start_date)
                .order_by(AnalyticsEvent.created_at.desc())
            )

            if MAX_ANALYTICS_EVENTS:
                query = query.limit(MAX_ANALYTICS_EVENTS)

            events = query.all()

            return [
                {
                    "timestamp": event.created_at,
                    "event_type": event.event_type,
                    "category": event.event_category,
                    "action": event.event_action,
                    "user_id": event.user_session,
                    "user_type": event.user_type,
                    "page_url": event.page_url,
                }
                for event in events
            ]
        except Exception as e:
            print(f"Error getting recent events: {e}")
            return []

    def get_events_in_range(self, start_date, end_date):
        """Get events in date range"""
        # Check if we have Flask application context
        try:
            from flask import current_app

            if not current_app:
                return []
        except RuntimeError:
            # Working outside of application context
            return []

        try:
            query = (
                AnalyticsEvent.query.options(
                    load_only(
                        AnalyticsEvent.created_at,
                        AnalyticsEvent.event_type,
                        AnalyticsEvent.event_category,
                        AnalyticsEvent.event_action,
                        AnalyticsEvent.user_session,
                        AnalyticsEvent.user_type,
                        AnalyticsEvent.page_url,
                    )
                )
                .filter(
                    AnalyticsEvent.created_at >= start_date,
                    AnalyticsEvent.created_at <= end_date,
                )
                .order_by(AnalyticsEvent.created_at.desc())
            )

            if MAX_ANALYTICS_EVENTS:
                query = query.limit(MAX_ANALYTICS_EVENTS)

            events = query.all()

            return [
                {
                    "timestamp": event.created_at,
                    "event_type": event.event_type,
                    "category": event.event_category,
                    "action": event.event_action,
                    "user_id": event.user_session,
                    "user_type": event.user_type,
                    "page_url": event.page_url,
                }
                for event in events
            ]
        except Exception as e:
            print(f"Error getting events in range: {e}")
            return []


# WebSocket για real-time notifications
class RealTimeNotifications:
    """Real-time notifications system"""

    def __init__(self, socketio, feature_checker=None):
        self.socketio = socketio
        self.subscribers = set()
        self._feature_enabled = feature_checker or (lambda feature: True)

    def subscribe(self, session_id):
        """Subscribe session για notifications"""
        self.subscribers.add(session_id)

    def unsubscribe(self, session_id):
        """Unsubscribe session"""
        self.subscribers.discard(session_id)

    def broadcast_anomaly(self, anomaly):
        """Broadcast anomaly detection"""
        if not self.socketio or not self._feature_enabled("notifications"):
            return

        notification = {
            "type": "anomaly",
            "severity": anomaly.get("severity", "medium"),
            "title": f"Anomaly Detected: {anomaly['type']}",
            "message": anomaly["description"],
            "timestamp": anomaly["timestamp"].isoformat(),
            "action_required": anomaly.get("severity") == "critical",
        }

        self.socketio.emit("analytics_notification", notification)

    def broadcast_milestone(self, milestone):
        """Broadcast milestone achievements"""
        if not self.socketio or not self._feature_enabled("notifications"):
            return

        notification = {
            "type": "milestone",
            "severity": "info",
            "title": "Milestone Reached!",
            "message": f"We've reached {milestone['value']} {milestone['metric']}!",
            "timestamp": datetime.now().isoformat(),
        }

        self.socketio.emit("analytics_notification", notification)


if __name__ == "__main__":
    print("🤖 Advanced Analytics Module Ready")
    print("Features: Anomaly detection, Predictive analytics, Real-time notifications")

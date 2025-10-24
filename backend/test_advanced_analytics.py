"""
Unit tests for Advanced Analytics functions
Tests anomaly detection, predictive analytics, and insights generation
"""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add the backend directory to Python path for imports
backend_dir = os.path.dirname(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from advanced_analytics import AdvancedAnalytics, RealTimeNotifications


class TestAdvancedAnalytics:
    """Test suite for AdvancedAnalytics class"""

    @pytest.fixture
    def analytics(self):
        """Create AdvancedAnalytics instance with mocked database"""
        analytics = AdvancedAnalytics()
        analytics.db = Mock()
        return analytics

    @pytest.fixture
    def sample_events(self):
        """Create sample analytics events for testing"""
        base_time = datetime.now()

        return [
            {
                "timestamp": base_time - timedelta(hours=i),
                "event_type": "page_view",
                "details": "home_page",
                "user_type": "guest",
                "page_url": "/",
            }
            for i in range(24)  # 24 hours of data
        ] + [
            {
                "timestamp": base_time - timedelta(hours=i),
                "event_type": "error",
                "details": "database_error",
                "user_type": "guest",
                "page_url": "/api/data",
            }
            for i in range(2)  # 2 error events
        ]

    def test_detect_anomalies_no_data(self, analytics):
        """Test anomaly detection with no data"""
        with patch.object(analytics, 'get_events_by_hour', return_value=[]):
            anomalies = analytics.detect_anomalies(timeframe_days=7)
            assert isinstance(anomalies, list)
            assert len(anomalies) == 0

    def test_detect_anomalies_traffic_spike(self, analytics, sample_events):
        """Test detection of traffic spike anomaly"""
        # Create data with significant traffic increase
        # The method expects events grouped by hour, so we need to simulate that
        base_time = datetime.now()
        timeframe_days = 7

        # Create baseline period events (first half of timeframe)
        baseline_start = base_time - timedelta(days=timeframe_days * 2)
        baseline_end = base_time - timedelta(days=timeframe_days)

        baseline_events = [
            {
                "timestamp": baseline_start + timedelta(hours=i),
                "event_type": "page_view",
                "details": "normal",
                "user_type": "guest",
                "page_url": "/",
            }
            for i in range(10)  # 10 events in baseline
        ]

        # Create current period with spike (second half of timeframe)
        current_events = [
            {
                "timestamp": baseline_end + timedelta(hours=i),
                "event_type": "page_view",
                "details": "normal",
                "user_type": "guest",
                "page_url": "/",
            }
            for i in range(50)  # 50 events in current (5x increase)
        ]

        # Mock get_events_by_hour to return events grouped by hour
        with patch.object(analytics, 'get_events_by_hour') as mock_get_events:
            # Group events by hour as the method expects
            all_events = baseline_events + current_events
            events_by_hour = {}
            for event in all_events:
                hour_key = event["timestamp"].replace(minute=0, second=0, microsecond=0)
                if hour_key not in events_by_hour:
                    events_by_hour[hour_key] = []
                events_by_hour[hour_key].append(event)

            mock_get_events.return_value = list(events_by_hour.values())

            # Mock Flask current_app to avoid context check
            with patch('flask.current_app', new_callable=lambda: Mock()):
                anomalies = analytics.detect_anomalies(timeframe_days=timeframe_days)

                # Should detect traffic spike
                traffic_anomalies = [a for a in anomalies if 'traffic' in a['type']]
                assert len(traffic_anomalies) > 0

                spike_anomaly = traffic_anomalies[0]
                assert spike_anomaly['type'] == 'traffic_spike'
                assert 'severity' in spike_anomaly
                assert 'value' in spike_anomaly
                assert spike_anomaly['value'] > 0  # Positive change

    def test_detect_anomalies_error_spike(self, analytics):
        """Test detection of error rate spike"""
        base_time = datetime.now()
        timeframe_days = 7

        # Create baseline period with low error rate
        baseline_start = base_time - timedelta(days=timeframe_days * 2)
        baseline_events = [
            {
                "timestamp": baseline_start + timedelta(hours=i),
                "event_type": "page_view",
                "details": "normal_page",
                "user_type": "guest",
                "page_url": "/normal",
            }
            for i in range(100)  # 100 normal events in baseline
        ] + [
            {
                "timestamp": baseline_start + timedelta(hours=i),
                "event_type": "page_view",
                "details": "error",
                "user_type": "guest",
                "page_url": "/error",
            }
            for i in range(2)  # 2 error events in baseline (2% error rate)
        ]

        # Create current period with high error rate
        current_start = base_time - timedelta(days=timeframe_days)
        current_events = [
            {
                "timestamp": current_start + timedelta(hours=i),
                "event_type": "page_view",
                "details": "normal_page",
                "user_type": "guest",
                "page_url": "/normal",
            }
            for i in range(50)  # 50 normal events in current
        ] + [
            {
                "timestamp": current_start + timedelta(hours=i),
                "event_type": "page_view",
                "details": "error_500",
                "user_type": "guest",
                "page_url": "/error",
            }
            for i in range(30)  # 30 error events in current (37.5% error rate)
        ]

        # Mock get_events_by_hour to return events grouped by hour
        with patch.object(analytics, 'get_events_by_hour') as mock_get_events:
            all_events = baseline_events + current_events
            events_by_hour = {}
            for event in all_events:
                hour_key = event["timestamp"].replace(minute=0, second=0, microsecond=0)
                if hour_key not in events_by_hour:
                    events_by_hour[hour_key] = []
                events_by_hour[hour_key].append(event)

            mock_get_events.return_value = list(events_by_hour.values())

            # Mock Flask current_app to avoid context check
            with patch('flask.current_app', new_callable=lambda: Mock()):
                anomalies = analytics.detect_anomalies(timeframe_days=timeframe_days)

                # Should detect error spike
                error_anomalies = [a for a in anomalies if a['type'] == 'error_spike']
                assert len(error_anomalies) > 0

                error_anomaly = error_anomalies[0]
                assert error_anomaly['severity'] == 'critical'
                assert error_anomaly['value'] > 5  # High error rate

    def test_predict_user_behavior_no_user(self, analytics):
        """Test user behavior prediction without specific user"""
        with patch.object(analytics, '_predict_conversion', return_value={'probability': 0.5}):
            with patch.object(analytics, '_find_optimal_time', return_value={'hour': 14}):
                with patch.object(analytics, '_recommend_features', return_value=[]):
                    with patch.object(analytics, '_calculate_churn_risk', return_value={'risk': 'unknown'}):
                        predictions = analytics.predict_user_behavior()

                        assert 'likely_to_convert' in predictions
                        assert 'optimal_engagement_time' in predictions
                        assert 'feature_recommendations' in predictions
                        assert 'churn_risk' in predictions

    def test_predict_user_behavior_with_user(self, analytics):
        """Test user behavior prediction for specific user"""
        user_id = "test_user_123"

        mock_events = [
            {"event_type": "page_view", "timestamp": datetime.now()},
            {"event_type": "page_view", "timestamp": datetime.now()},
            {"event_type": "form_interaction", "timestamp": datetime.now()},
        ]

        with patch.object(analytics, 'get_user_events', return_value=mock_events):
            with patch.object(analytics, '_find_optimal_time', return_value={'hour': 14}):
                with patch.object(analytics, '_recommend_features', return_value=[]):
                    with patch.object(analytics, '_calculate_churn_risk', return_value={'risk': 'low'}):
                        predictions = analytics.predict_user_behavior(user_id)

                        assert predictions['likely_to_convert']['probability'] > 0
                        assert predictions['likely_to_convert']['score'] > 0
                        assert 'factors' in predictions['likely_to_convert']

    def test_predict_conversion_calculation(self, analytics):
        """Test conversion probability calculation"""
        user_id = "test_user"

        # Mock user with high engagement
        mock_events = [
            {"event_type": "page_view"} for _ in range(20)  # 20 page views
        ] + [
            {"event_type": "form_interaction"} for _ in range(5)  # 5 form interactions
        ]

        with patch.object(analytics, 'get_user_events', return_value=mock_events):
            result = analytics._predict_conversion(user_id)

            assert result['probability'] > 0
            assert result['score'] > 0
            assert result['factors']['page_engagement'] == 20
            assert result['factors']['form_interactions'] == 5

    def test_find_optimal_time(self, analytics):
        """Test optimal engagement time finding"""
        # Mock events with peak activity at hour 14
        mock_events = []
        for hour in range(24):
            # Create more events at hour 14
            event_count = 10 if hour == 14 else 1
            for _ in range(event_count):
                mock_events.append({
                    "event_type": "form_interaction",
                    "timestamp": datetime.now().replace(hour=hour),
                })

        with patch.object(analytics, 'get_recent_events', return_value=mock_events):
            result = analytics._find_optimal_time()

            assert result['hour'] == 14
            assert result['engagement_score'] == 10
            assert 'recommendation' in result

    def test_recommend_features(self, analytics):
        """Test feature recommendation logic"""
        user_id = "test_user"

        # Mock user who has used some features
        mock_events = [
            {"event_type": "feature_usage", "category": "search"},
            {"event_type": "feature_usage", "category": "messaging"},
        ]

        with patch.object(analytics, 'get_user_events', return_value=mock_events):
            recommendations = analytics._recommend_features(user_id)

            # Should recommend unused features
            recommended_features = [r['feature'] for r in recommendations]
            assert 'volunteer_registration' in recommended_features
            assert 'notifications' in recommended_features
            assert 'search' not in recommended_features  # Already used
            assert 'messaging' not in recommended_features  # Already used

            # Should be sorted by score (highest first)
            scores = [r['score'] for r in recommendations]
            assert scores == sorted(scores, reverse=True)

    def test_calculate_churn_risk(self, analytics):
        """Test churn risk calculation"""
        user_id = "test_user"

        # Test with recent activity (low risk)
        recent_events = [{
            "timestamp": datetime.now() - timedelta(days=1),
            "event_type": "page_view"
        }]

        with patch.object(analytics, 'get_user_events', return_value=recent_events):
            result = analytics._calculate_churn_risk(user_id)

            assert result['risk'] == 'very_low'
            assert result['score'] < 0.2
            assert result['days_since_activity'] == 1

        # Test with old activity (high risk)
        old_events = [{
            "timestamp": datetime.now() - timedelta(days=45),
            "event_type": "page_view"
        }]

        with patch.object(analytics, 'get_user_events', return_value=old_events):
            result = analytics._calculate_churn_risk(user_id)

            assert result['risk'] == 'high'
            assert result['score'] > 0.7
            assert result['days_since_activity'] == 45

    def test_generate_insights_report(self, analytics):
        """Test comprehensive insights report generation"""
        with patch.object(analytics, 'detect_anomalies', return_value=[]):
            with patch.object(analytics, 'predict_user_behavior', return_value={}):
                with patch.object(analytics, '_analyze_kpi_trends', return_value={'trends': {}}):
                    with patch.object(analytics, '_segment_users', return_value={}):
                        with patch.object(analytics, '_generate_recommendations', return_value=[]):
                            report = analytics.generate_insights_report()

                            assert 'generated_at' in report
                            assert 'anomalies' in report
                            assert 'predictions' in report
                            assert 'kpi_trends' in report
                            assert 'user_segments' in report
                            assert 'recommendations' in report

                            # Check timestamp format
                            datetime.fromisoformat(report['generated_at'])

    def test_analyze_kpi_trends(self, analytics):
        """Test KPI trends analysis"""
        # Mock events for 4 weeks with increasing trend
        mock_events = []
        for week in range(4):
            for _ in range(10 + week * 5):  # Increasing events per week
                mock_events.append({
                    "timestamp": datetime.now() - timedelta(weeks=week),
                    "event_type": "page_view",
                    "user_id": f"user_{week}",
                    "category": "test",
                    "action": "test",
                    "user_type": "guest",
                    "page_url": "/test",
                })

        with patch.object(analytics, 'get_events_in_range', return_value=mock_events):
            result = analytics._analyze_kpi_trends()

            assert 'weekly_data' in result
            assert 'trends' in result
            assert len(result['weekly_data']) == 4

            # Check trend calculation
            total_events_trend = result['trends'].get('total_events', {})
            assert 'trend' in total_events_trend
            assert 'change_percent' in total_events_trend

    def test_segment_users(self, analytics):
        """Test user segmentation logic"""
        # Create mock events for different user types
        mock_events = []

        # Power user: many events, multiple features
        for _ in range(60):
            mock_events.append({
                "user_id": "power_user",
                "event_type": "feature_usage",
                "category": "search",
                "timestamp": datetime.now(),
            })

        # Regular user: moderate activity
        for _ in range(15):
            mock_events.append({
                "user_id": "regular_user",
                "event_type": "page_view",
                "category": "volunteer_registration",
                "timestamp": datetime.now(),
            })

        # New user: few events
        for _ in range(3):
            mock_events.append({
                "user_id": "new_user",
                "event_type": "page_view",
                "category": "home",
                "timestamp": datetime.now(),
            })

        with patch.object(analytics, 'get_recent_events', return_value=mock_events):
            segments = analytics._segment_users()

            assert 'power_users' in segments
            assert 'regular_users' in segments
            assert 'new_users' in segments
            assert 'inactive_users' in segments

            # Check counts
            assert segments['power_users']['count'] >= 0
            assert segments['regular_users']['count'] >= 0
            assert segments['new_users']['count'] >= 0

    def test_generate_recommendations(self, analytics):
        """Test recommendations generation"""
        recommendations = analytics._generate_recommendations()

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        # Check recommendation structure
        for rec in recommendations:
            assert 'type' in rec
            assert 'priority' in rec
            assert 'title' in rec
            assert 'description' in rec
            assert 'action' in rec

    def test_helper_methods_no_context(self, analytics):
        """Test helper methods when no Flask context is available"""
        # These methods should return empty lists when no context
        assert analytics.get_events_by_hour(datetime.now(), datetime.now()) == []
        assert analytics.get_user_events("test_user") == []
        assert analytics.get_recent_events() == []
        assert analytics.get_events_in_range(datetime.now(), datetime.now()) == []


class TestRealTimeNotifications:
    """Test suite for RealTimeNotifications class"""

    @pytest.fixture
    def notifications(self):
        """Create RealTimeNotifications instance with mocked socketio"""
        mock_socketio = Mock()
        notifications = RealTimeNotifications(mock_socketio)
        return notifications

    def test_subscribe_unsubscribe(self, notifications):
        """Test subscriber management"""
        session_id = "session_123"

        # Subscribe
        notifications.subscribe(session_id)
        assert session_id in notifications.subscribers

        # Unsubscribe
        notifications.unsubscribe(session_id)
        assert session_id not in notifications.subscribers

    def test_broadcast_anomaly(self, notifications):
        """Test anomaly broadcasting"""
        anomaly = {
            "type": "traffic_spike",
            "severity": "high",
            "description": "Traffic increased by 50%",
            "timestamp": datetime.now(),
        }

        notifications.broadcast_anomaly(anomaly)

        # Check that socketio.emit was called
        notifications.socketio.emit.assert_called_once()
        call_args = notifications.socketio.emit.call_args

        assert call_args[0][0] == "analytics_notification"
        notification = call_args[0][1]

        assert notification["type"] == "anomaly"
        assert notification["severity"] == "high"
        assert "Traffic increased" in notification["message"]

    def test_broadcast_milestone(self, notifications):
        """Test milestone broadcasting"""
        milestone = {
            "metric": "users",
            "value": 1000,
        }

        notifications.broadcast_milestone(milestone)

        # Check that socketio.emit was called
        notifications.socketio.emit.assert_called_once()
        call_args = notifications.socketio.emit.call_args

        assert call_args[0][0] == "analytics_notification"
        notification = call_args[0][1]

        assert notification["type"] == "milestone"
        assert "1000 users" in notification["message"]


if __name__ == "__main__":
    pytest.main([__file__])
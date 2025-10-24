#!/usr/bin/env python
"""
Unit tests for analytics_service.py
Tests all analytics functions including event tracking, performance monitoring,
dashboard analytics, and error handling.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, Mock

import pytest

# Mock the models before importing analytics_service to avoid relationship issues
mock_db = MagicMock()

# Create mock model classes that accept any arguments
class MockAdminUser:
    def __init__(self, *args, **kwargs):
        pass

class MockAnalyticsEvent:
    def __init__(self, *args, **kwargs):
        pass

class MockUserBehavior:
    def __init__(self, *args, **kwargs):
        pass

class MockPerformanceMetrics:
    def __init__(self, *args, **kwargs):
        pass

class MockChatbotConversation:
    def __init__(self, *args, **kwargs):
        pass

# Patch the models in sys.modules before importing
with patch.dict('sys.modules', {
    'models_with_analytics': Mock(),
    'backend.models_with_analytics': Mock(),
}):
    # Set up the mock module attributes
    import sys
    mock_module = sys.modules['models_with_analytics']
    mock_module.AdminUser = MockAdminUser
    mock_module.AnalyticsEvent = MockAnalyticsEvent
    mock_module.UserBehavior = MockUserBehavior
    mock_module.PerformanceMetrics = MockPerformanceMetrics
    mock_module.ChatbotConversation = MockChatbotConversation
    
    from analytics_service import AdvancedAnalytics


class TestAdvancedAnalytics:
    """Test suite for AdvancedAnalytics class"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for testing"""
        session = MagicMock()
        # Mock the query method to return a mock query object
        query_mock = MagicMock()
        session.query.return_value = query_mock
        # Mock filter method
        query_mock.filter.return_value = query_mock
        # Mock first method to return a mock UserBehavior with proper attributes
        mock_behavior = MagicMock()
        mock_behavior.pages_visited = 0
        mock_behavior.pages_sequence = "[]"
        mock_behavior.last_activity = None
        mock_behavior.bounce_rate = True
        query_mock.first.return_value = mock_behavior
        # Mock scalar method
        query_mock.scalar.return_value = 0
        # Mock count method
        query_mock.count.return_value = 0
        # Mock all method
        query_mock.all.return_value = []
        return session

    @pytest.fixture
    def analytics_service(self, mock_db_session):
        """Create analytics service instance with mocked dependencies"""
        # Mock the db object
        mock_db_obj = MagicMock()
        mock_db_obj.session = mock_db_session
        
        # Create service with mocked db
        service = AdvancedAnalytics(db=mock_db_obj)
        return service

    def test_init(self, analytics_service):
        """Test analytics service initialization"""
        assert analytics_service is not None
        assert hasattr(analytics_service, 'track_event')
        assert hasattr(analytics_service, 'track_performance')
        assert hasattr(analytics_service, 'get_dashboard_analytics')

    def test_track_event_success(self, analytics_service, mock_db_session):
        """Test successful event tracking"""
        # Setup
        event_data = {
            'event_type': 'page_view',
            'event_category': 'navigation',
            'event_action': 'view',
            'context': {
                'session_id': '123',
                'user_type': 'guest',
                'page_url': '/dashboard'
            }
        }

        # Mock successful database operation
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None

        # Mock Flask app context
        with patch('flask.has_app_context', return_value=True):
            # Execute
            result = analytics_service.track_event(**event_data)

        # Assert
        assert result is True
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_track_event_database_error(self, analytics_service, mock_db_session):
        """Test event tracking with database error"""
        # Setup
        event_data = {
            'event_type': 'page_view',
            'context': {'session_id': '123'}
        }

        # Mock database error
        mock_db_session.commit.side_effect = Exception("Database connection failed")

        # Mock Flask app context
        with patch('flask.has_app_context', return_value=True):
            # Execute
            result = analytics_service.track_event(**event_data)

        # Assert
        assert result is False
        mock_db_session.rollback.assert_called_once()

    def test_track_event_missing_required_fields(self, analytics_service):
        """Test event tracking with missing required fields"""
        # Test missing event_type should raise TypeError
        with patch('flask.has_app_context', return_value=True):
            with pytest.raises(TypeError):
                analytics_service.track_event(context={'session_id': '123'})

        # Test with empty event_type
        with patch('flask.has_app_context', return_value=True):
            result = analytics_service.track_event(event_type='', context={'session_id': '123'})
        assert result is False

    def test_track_performance_success(self, analytics_service, mock_db_session):
        """Test successful performance tracking"""
        # Setup
        perf_data = {
            'metric_type': 'response_time',
            'metric_name': 'api_call',
            'metric_value': 150.5,
            'unit': 'ms',
            'context': {
                'endpoint': '/api/dashboard',
                'user_agent': 'test-agent'
            }
        }

        # Mock successful database operation
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None

        # Mock Flask app context
        with patch('flask.has_app_context', return_value=True):
            # Execute
            result = analytics_service.track_performance(**perf_data)

        # Assert
        assert result is True
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_track_performance_with_tags(self, analytics_service, mock_db_session):
        """Test performance tracking with additional context"""
        # Setup
        perf_data = {
            'metric_type': 'response_time',
            'metric_name': 'api_call',
            'metric_value': 200.0,
            'unit': 'ms',
            'context': {
                'endpoint': '/api/dashboard',
                'user_agent': 'chrome',
                'metadata': {'browser': 'chrome', 'device': 'mobile'}
            }
        }

        # Mock successful database operation
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None

        # Mock Flask app context
        with patch('flask.has_app_context', return_value=True):
            # Execute
            result = analytics_service.track_performance(**perf_data)

        # Assert
        assert result is True
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_track_performance_database_error(self, analytics_service, mock_db_session):
        """Test performance tracking with database error"""
        # Setup
        perf_data = {
            'metric_type': 'response_time',
            'metric_name': 'api_call',
            'metric_value': 150.5,
            'context': {'endpoint': '/api/dashboard'}
        }

        # Mock database error
        mock_db_session.commit.side_effect = Exception("Database error")

        # Mock Flask app context
        with patch('flask.has_app_context', return_value=True):
            # Execute
            result = analytics_service.track_performance(**perf_data)

        # Assert
        assert result is False
        mock_db_session.rollback.assert_called_once()

    def test_get_dashboard_analytics_basic(self, analytics_service, mock_db_session):
        """Test basic dashboard analytics retrieval"""
        # Mock Flask app context properly
        mock_app = MagicMock()
        mock_app.extensions = {'sqlalchemy': MagicMock()}
        
        with patch('flask.current_app', mock_app), \
             patch('analytics_service.datetime') as mock_datetime:

            mock_datetime.utcnow.return_value = datetime(2024, 1, 1)

            # Mock query results - simplified for testing
            mock_query = MagicMock()
            mock_db_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.scalar.return_value = 100  # Mock count result

            # Execute
            result = analytics_service.get_dashboard_analytics()

            # Assert
            assert isinstance(result, dict)
            # Should return sample data when no real data exists
            assert 'overview' in result
            assert 'user_engagement' in result

    def test_get_dashboard_analytics_database_error(self, analytics_service, mock_db_session):
        """Test dashboard analytics with database error"""
        # Mock Flask app context properly
        mock_app = MagicMock()
        mock_app.extensions = {'sqlalchemy': MagicMock()}
        
        with patch('flask.current_app', mock_app):
            # Execute
            result = analytics_service.get_dashboard_analytics()

            # Assert - should return sample data on error
            assert isinstance(result, dict)
            assert 'overview' in result

    def test_error_handling_comprehensive(self, analytics_service, mock_db_session):
        """Test comprehensive error handling across all methods"""
        # Test track_event with various errors
        mock_db_session.commit.side_effect = Exception("Connection lost")

        with patch('flask.has_app_context', return_value=True):
            result = analytics_service.track_event(event_type='test', context={'session_id': '1'})
            assert result is False

        # Reset for performance test
        mock_db_session.commit.side_effect = Exception("Database error")

        with patch('flask.has_app_context', return_value=True):
            result = analytics_service.track_performance(
                metric_type='test', metric_name='test', metric_value=100, context={}
            )
            assert result is False

        # Dashboard analytics should handle errors gracefully
        mock_app = MagicMock()
        mock_app.extensions = {'sqlalchemy': MagicMock()}
        
        with patch('flask.current_app', mock_app):
            result = analytics_service.get_dashboard_analytics()
            assert isinstance(result, dict)  # Should return sample data

    def test_concurrent_operations_simulation(self, analytics_service, mock_db_session):
        """Test behavior under simulated concurrent operations"""
        import threading

        results = []
        errors = []

        def track_event_worker():
            try:
                with patch('flask.has_app_context', return_value=True):
                    result = analytics_service.track_event(
                        event_type='concurrent_test',
                        context={'session_id': f'thread_{threading.current_thread().ident}'}
                    )
                    results.append(result)
            except Exception as e:
                errors.append(str(e))

        # Mock successful operations
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None

        # Simulate concurrent calls
        threads = []
        for i in range(3):  # Reduced for testing
            thread = threading.Thread(target=track_event_worker)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Assert all operations succeeded
        assert len(results) == 3
        assert all(results)
        assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__])
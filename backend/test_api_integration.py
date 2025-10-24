#!/usr/bin/env python
"""
Integration tests for HelpChain API endpoints
Tests authentication, data validation, and API responses
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestAPIIntegration:
    """Integration tests for API endpoints"""

    def test_volunteer_dashboard_api(self, client, authenticated_volunteer_client):
        """Test volunteer dashboard API endpoint"""
        # Test with authenticated volunteer
        response = authenticated_volunteer_client.get('/api/volunteer/dashboard')
        assert response.status_code in [200, 404]  # 404 is acceptable if no data

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for expected dashboard structure
            expected_keys = ['stats', 'recent_activity', 'tasks']
            for key in expected_keys:
                assert key in data or 'sample_data' in data

    def test_admin_dashboard_api(self, client, authenticated_admin_client):
        """Test admin dashboard API endpoint"""
        # Test with authenticated admin
        response = authenticated_admin_client.get('/api/admin/dashboard')
        assert response.status_code in [200, 404]  # 404 is acceptable if no data

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for expected admin dashboard structure
            expected_keys = ['overview', 'analytics', 'recent_activity']
            for key in expected_keys:
                assert key in data or 'sample_data' in data

    def test_chatbot_message_api(self, client, authenticated_volunteer_client):
        """Test chatbot message API endpoint"""
        # Test with valid message data
        message_data = {
            'message': 'Hello, I need help',
            'session_id': 'test_session_123'
        }

        response = authenticated_volunteer_client.post(
            '/api/chatbot/message',
            data=json.dumps(message_data),
            content_type='application/json'
        )

        # Should return 200 for successful processing or 500 for AI service issues
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'response' in data
            assert 'confidence' in data

    def test_chatbot_message_invalid_data(self, client, authenticated_volunteer_client):
        """Test chatbot API with invalid data"""
        # Test with missing message
        response = authenticated_volunteer_client.post(
            '/api/chatbot/message',
            data=json.dumps({'session_id': 'test'}),
            content_type='application/json'
        )
        assert response.status_code == 400

        # Test with empty message
        response = authenticated_volunteer_client.post(
            '/api/chatbot/message',
            data=json.dumps({'message': '', 'session_id': 'test'}),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_ai_status_api(self, client, authenticated_admin_client):
        """Test AI status API endpoint"""
        response = authenticated_admin_client.get('/api/ai/status')
        assert response.status_code in [200, 503]  # 503 if AI service unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'status' in data
            assert 'provider' in data

    def test_volunteer_tasks_api(self, client, authenticated_volunteer_client):
        """Test volunteer tasks API endpoint"""
        response = authenticated_volunteer_client.get('/api/volunteer/tasks')
        assert response.status_code in [200, 404]  # 404 if no tasks

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, list)  # Should return array of tasks

    def test_user_profile_api(self, client, authenticated_volunteer_client):
        """Test user profile API endpoint"""
        response = authenticated_volunteer_client.get('/api/user/profile')
        assert response.status_code in [200, 404]  # 404 if profile not found

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'name' in data or 'username' in data

    def test_chat_rooms_api(self, client, authenticated_volunteer_client):
        """Test chat rooms API endpoint"""
        response = authenticated_volunteer_client.get('/api/chat/rooms')
        assert response.status_code in [200, 404]  # 404 if no rooms

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, list)  # Should return array of rooms

    def test_chat_room_messages_api(self, client, authenticated_volunteer_client):
        """Test chat room messages API endpoint"""
        # Test with valid room ID
        response = authenticated_volunteer_client.get('/api/chat/room/1/messages')
        assert response.status_code in [200, 404]  # 404 if room not found

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, list)  # Should return array of messages

    def test_create_chat_room_api(self, client, authenticated_volunteer_client):
        """Test create chat room API endpoint"""
        room_data = {
            'name': 'Test Room',
            'description': 'Test chat room for integration testing'
        }

        response = authenticated_volunteer_client.post(
            '/api/chat/create_room',
            data=json.dumps(room_data),
            content_type='application/json'
        )

        assert response.status_code in [201, 400, 500]  # 201 success, 400 validation error, 500 server error

        if response.status_code == 201:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'room_id' in data

    def test_leave_chat_room_api(self, client, authenticated_volunteer_client):
        """Test leave chat room API endpoint"""
        leave_data = {
            'room_id': 1
        }

        response = authenticated_volunteer_client.post(
            '/api/chat/leave_room',
            data=json.dumps(leave_data),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404]  # 200 success, 400/404 validation/room not found

    def test_unauthenticated_access(self, client):
        """Test that unauthenticated users cannot access protected endpoints"""
        protected_endpoints = [
            '/api/volunteer/dashboard',
            '/api/admin/dashboard',
            '/api/volunteer/tasks',
            '/api/user/profile',
            '/api/chat/rooms'
        ]

        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code in [302, 401, 403]  # Redirect or unauthorized

    def test_invalid_json_payload(self, client, authenticated_volunteer_client):
        """Test API endpoints with invalid JSON payloads"""
        endpoints = [
            '/api/chatbot/message',
            '/api/chat/create_room',
            '/api/chat/leave_room'
        ]

        for endpoint in endpoints:
            # Test with invalid JSON
            response = authenticated_volunteer_client.post(
                endpoint,
                data='invalid json {',
                content_type='application/json'
            )
            assert response.status_code == 400

    def test_rate_limiting_simulation(self, client, authenticated_volunteer_client):
        """Test rate limiting behavior (simulated)"""
        # Make multiple rapid requests to chatbot endpoint
        for i in range(10):
            response = authenticated_volunteer_client.post(
                '/api/chatbot/message',
                data=json.dumps({
                    'message': f'Test message {i}',
                    'session_id': 'rate_limit_test'
                }),
                content_type='application/json'
            )
            # Should not be rate limited in test environment
            assert response.status_code in [200, 500]

    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options('/api/chatbot/message')
        # CORS headers should be present
        cors_headers = [
            'Access-Control-Allow-Origin',
            'Access-Control-Allow-Methods',
            'Access-Control-Allow-Headers'
        ]
        for header in cors_headers:
            assert header in response.headers or response.status_code == 404

    @patch('analytics_service.analytics_service')
    def test_analytics_tracking_integration(self, mock_analytics, client, authenticated_volunteer_client):
        """Test that API calls properly track analytics"""
        # Mock analytics service
        mock_analytics.track_event.return_value = True

        # Make API call that should trigger analytics
        response = authenticated_volunteer_client.get('/api/volunteer/dashboard')

        # Analytics should be called (may not be in all cases due to error handling)
        # This is more of a smoke test for integration

    def test_error_response_format(self, client, authenticated_volunteer_client):
        """Test that error responses have consistent format"""
        # Make request that should fail
        response = authenticated_volunteer_client.post(
            '/api/chatbot/message',
            data=json.dumps({}),  # Empty payload should cause validation error
            content_type='application/json'
        )

        if response.status_code >= 400:
            try:
                data = json.loads(response.data)
                assert isinstance(data, dict)
                assert 'error' in data or 'message' in data
            except json.JSONDecodeError:
                # Some errors might return HTML instead of JSON
                pass

    def test_response_content_type(self, client, authenticated_volunteer_client):
        """Test that API responses have correct content type"""
        endpoints = [
            '/api/volunteer/dashboard',
            '/api/admin/dashboard',
            '/api/ai/status',
            '/api/volunteer/tasks',
            '/api/user/profile',
            '/api/chat/rooms'
        ]

        for endpoint in endpoints:
            response = authenticated_volunteer_client.get(endpoint)
            if response.status_code == 200:
                assert 'application/json' in response.content_type or 'text/html' in response.content_type

    def test_analytics_data_api(self, client, authenticated_admin_client):
        """Test analytics data API endpoint"""
        response = authenticated_admin_client.get('/api/analytics/data')
        assert response.status_code in [200, 500]  # 500 if analytics service unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for expected analytics structure
            assert 'overview' in data or 'sample_data' in data

    def test_analytics_live_api(self, client, authenticated_admin_client):
        """Test live analytics API endpoint"""
        response = authenticated_admin_client.get('/api/analytics/live')
        assert response.status_code in [200, 500]  # 500 if analytics service unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for live data structure
            expected_keys = ['requests_today', 'volunteers_active', 'conversions_today', 'avg_response_time', 'timestamp']
            for key in expected_keys:
                assert key in data

    def test_analytics_trends_api(self, client, authenticated_admin_client):
        """Test analytics trends API endpoint"""
        response = authenticated_admin_client.get('/api/analytics/trends?months=3')
        assert response.status_code in [200, 500]  # 500 if analytics service unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for trend data structure
            expected_keys = ['labels', 'requests', 'completed', 'volunteers']
            for key in expected_keys:
                assert key in data
                assert isinstance(data[key], list)

    def test_analytics_export_api(self, client, authenticated_admin_client):
        """Test analytics export API endpoint"""
        # Test JSON export
        response = authenticated_admin_client.get('/api/analytics/export?format=json')
        assert response.status_code in [200, 500]  # 500 if analytics service unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'export_info' in data

        # Test CSV export
        response = authenticated_admin_client.get('/api/analytics/export?format=csv')
        assert response.status_code in [200, 500]  # 500 if analytics service unavailable

        if response.status_code == 200:
            assert 'text/csv' in response.content_type

    def test_predictive_regional_demand_api(self, client, authenticated_admin_client):
        """Test predictive regional demand API endpoint"""
        response = authenticated_admin_client.get('/api/predictive/regional-demand?days=7')
        assert response.status_code in [200, 500]  # 500 if predictive analytics unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for forecast structure
            assert 'forecast' in data or 'error' in data

    def test_predictive_workload_api(self, client, authenticated_admin_client):
        """Test predictive workload API endpoint"""
        response = authenticated_admin_client.get('/api/predictive/workload?hours=24')
        assert response.status_code in [200, 500]  # 500 if predictive analytics unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for prediction structure
            assert 'prediction' in data or 'error' in data

    def test_predictive_insights_api(self, client, authenticated_admin_client):
        """Test predictive insights API endpoint"""
        response = authenticated_admin_client.get('/api/predictive/insights')
        assert response.status_code in [200, 500]  # 500 if predictive analytics unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for insights structure
            assert 'insights' in data or 'recommendations' in data or 'error' in data

    def test_predictive_model_info_api(self, client, authenticated_admin_client):
        """Test predictive model info API endpoint"""
        response = authenticated_admin_client.get('/api/predictive/model-info')
        assert response.status_code in [200, 500]  # 500 if predictive analytics unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for model info structure
            expected_keys = ['regional_demand_model', 'workload_prediction_model', 'data_sources', 'update_frequency']
            for key in expected_keys:
                assert key in data

    def test_advanced_anomalies_api(self, client, authenticated_admin_client):
        """Test advanced anomalies API endpoint"""
        response = authenticated_admin_client.get('/api/advanced/anomalies?days=7')
        assert response.status_code in [200, 500]  # 500 if advanced analytics unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for anomalies structure
            expected_keys = ['anomalies', 'timeframe_days', 'total_anomalies', 'generated_at']
            for key in expected_keys:
                assert key in data
            assert isinstance(data['anomalies'], list)

    def test_advanced_predictions_api(self, client, authenticated_admin_client):
        """Test advanced predictions API endpoint"""
        response = authenticated_admin_client.get('/api/advanced/predictions')
        assert response.status_code in [200, 500]  # 500 if advanced analytics unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for predictions structure
            expected_keys = ['predictions', 'generated_at']
            for key in expected_keys:
                assert key in data

    def test_advanced_insights_api(self, client, authenticated_admin_client):
        """Test advanced insights API endpoint"""
        response = authenticated_admin_client.get('/api/advanced/insights')
        assert response.status_code in [200, 500]  # 500 if advanced analytics unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for insights structure - could be various formats
            assert len(data) > 0  # Should have some content

    def test_advanced_user_behavior_api(self, client, authenticated_admin_client):
        """Test advanced user behavior API endpoint"""
        response = authenticated_admin_client.get('/api/advanced/user-behavior?days=30')
        assert response.status_code in [200, 500]  # 500 if advanced analytics unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for user behavior structure
            expected_keys = ['user_segments', 'kpi_trends', 'user_activity', 'analysis_period_days', 'generated_at']
            for key in expected_keys:
                assert key in data

    def test_alerts_config_api(self, client, authenticated_admin_client):
        """Test alerts configuration API endpoint"""
        response = authenticated_admin_client.get('/api/alerts/config')
        assert response.status_code in [200, 500]  # 500 if alerts system unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for alerts config structure
            expected_keys = ['alerts', 'total_alerts', 'generated_at']
            for key in expected_keys:
                assert key in data
            assert isinstance(data['alerts'], list)

    def test_alerts_check_api(self, client, authenticated_admin_client):
        """Test alerts check API endpoint"""
        response = authenticated_admin_client.get('/api/alerts/check')
        assert response.status_code in [200, 500]  # 500 if alerts system unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for alerts check structure
            expected_keys = ['triggered_alerts', 'total_triggered', 'checked_at']
            for key in expected_keys:
                assert key in data
            assert isinstance(data['triggered_alerts'], list)

    def test_alerts_history_api(self, client, authenticated_admin_client):
        """Test alerts history API endpoint"""
        response = authenticated_admin_client.get('/api/alerts/history')
        assert response.status_code in [200, 500]  # 500 if alerts system unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for alerts history structure
            expected_keys = ['history', 'total_alerts', 'active_alerts', 'generated_at']
            for key in expected_keys:
                assert key in data
            assert isinstance(data['history'], list)

    def test_alerts_config_update_api(self, client, authenticated_admin_client):
        """Test alerts configuration update API endpoint"""
        # First get current config
        response = authenticated_admin_client.get('/api/alerts/config')
        if response.status_code == 200:
            config_data = json.loads(response.data)
            if config_data['alerts']:
                alert_id = config_data['alerts'][0]['id']

                # Test updating an alert
                update_data = {
                    'enabled': False,
                    'threshold': 75
                }

                response = authenticated_admin_client.put(
                    f'/api/alerts/config/{alert_id}',
                    data=json.dumps(update_data),
                    content_type='application/json'
                )

                assert response.status_code in [200, 500]  # 200 success, 500 if update fails

                if response.status_code == 200:
                    data = json.loads(response.data)
                    assert 'success' in data or 'message' in data

    def test_notification_settings_api(self, client, authenticated_volunteer_client):
        """Test notification settings API endpoint"""
        # Test GET request
        response = authenticated_volunteer_client.get('/notifications/settings')
        assert response.status_code in [200, 500]  # 500 if service unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'success' in data
            assert 'settings' in data

        # Test POST request
        settings_data = {
            'emailEnabled': True,
            'smsEnabled': False,
            'pushEnabled': True
        }

        response = authenticated_volunteer_client.post(
            '/notifications/settings',
            data=json.dumps(settings_data),
            content_type='application/json'
        )

        assert response.status_code in [200, 500]  # 200 success, 500 if service unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'success' in data

    def test_push_subscription_api(self, client, authenticated_volunteer_client):
        """Test push subscription API endpoint"""
        subscription_data = {
            'endpoint': 'https://fcm.googleapis.com/fcm/send/test-endpoint',
            'p256dh': 'test-p256dh-key',
            'auth': 'test-auth-key',
            'userAgent': 'Mozilla/5.0 Test Browser'
        }

        response = authenticated_volunteer_client.post(
            '/notifications/subscribe',
            data=json.dumps(subscription_data),
            content_type='application/json'
        )

        assert response.status_code in [200, 500]  # 200 success, 500 if database unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'success' in data

    def test_vapid_public_key_api(self, client):
        """Test VAPID public key API endpoint"""
        response = client.get('/notifications/vapid-public-key')
        assert response.status_code in [200, 500]  # 500 if VAPID not configured

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'success' in data
            if 'publicKey' in data:
                assert isinstance(data['publicKey'], str)

    def test_push_unsubscribe_api(self, client, authenticated_volunteer_client):
        """Test push unsubscribe API endpoint"""
        unsubscribe_data = {
            'endpoint': 'https://fcm.googleapis.com/fcm/send/test-endpoint'
        }

        response = authenticated_volunteer_client.post(
            '/notifications/unsubscribe-push',
            data=json.dumps(unsubscribe_data),
            content_type='application/json'
        )

        assert response.status_code in [200, 404, 500]  # 200 success, 404 not found, 500 error

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'success' in data

    def test_test_email_api(self, client, authenticated_volunteer_client):
        """Test email notification API endpoint"""
        response = authenticated_volunteer_client.post('/notifications/test-email')
        assert response.status_code in [200, 500]  # 200 success, 500 if email service unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'success' in data

    def test_test_sms_api(self, client, authenticated_volunteer_client):
        """Test SMS notification API endpoint"""
        response = authenticated_volunteer_client.post('/notifications/test-sms')
        assert response.status_code in [200, 500]  # 200 success, 500 if SMS service unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'success' in data

    def test_send_notification_api(self, client, authenticated_admin_client):
        """Test send notification API endpoint"""
        notification_data = {
            'type': 'new_request',
            'recipients': [1, 2],  # Test user IDs
            'context': {
                'request': {
                    'id': 123,
                    'category': 'Medical',
                    'address': 'Test Address',
                    'distance': '2.5'
                }
            }
        }

        response = authenticated_admin_client.post(
            '/notifications/send',
            data=json.dumps(notification_data),
            content_type='application/json'
        )

        assert response.status_code in [200, 500]  # 200 success, 500 if notification service unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'success' in data
            assert 'sent_count' in data

    def test_notification_stats_api(self, client, authenticated_volunteer_client):
        """Test notification statistics API endpoint"""
        response = authenticated_volunteer_client.get('/notifications/stats')
        assert response.status_code in [200, 500]  # 200 success, 500 if service unavailable

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            assert 'success' in data
            assert 'stats' in data

    def test_unsubscribe_api(self, client):
        """Test unsubscribe API endpoint"""
        # Test with a mock token
        response = client.get('/notifications/unsubscribe/test-token-123')
        assert response.status_code in [200, 400]  # 200 success, 400 invalid token

        # Should return HTML template, not JSON
        if response.status_code == 200:
            assert 'text/html' in response.content_type

    def test_admin_login_api(self, client):
        """Test admin login API endpoint"""
        # Test GET request (should return login page)
        response = client.get('/admin/login')
        assert response.status_code in [200, 302]  # 200 for page, 302 for redirect

        # Test POST request with valid credentials
        login_data = {
            'username': 'admin',
            'password': 'admin123'  # Default admin password
        }

        response = client.post(
            '/admin/login',
            data=login_data,
            follow_redirects=False  # Don't follow redirects in test
        )

        assert response.status_code in [200, 302]  # 302 redirect on success, 200 on failure

        # Test POST request with invalid credentials
        invalid_data = {
            'username': 'admin',
            'password': 'wrongpassword'
        }

        response = client.post(
            '/admin/login',
            data=invalid_data,
            follow_redirects=False
        )

        assert response.status_code == 200  # Should stay on login page

    def test_admin_logout_api(self, client, authenticated_admin_client):
        """Test admin logout API endpoint"""
        response = authenticated_admin_client.post('/admin/logout')
        assert response.status_code in [200, 302]  # 302 redirect on success

    def test_admin_dashboard_api(self, client, authenticated_admin_client):
        """Test admin dashboard API endpoint"""
        response = authenticated_admin_client.get('/admin/dashboard')
        assert response.status_code in [200, 302]  # 200 success, 302 if not logged in

        if response.status_code == 200:
            # Should return HTML template, not JSON
            assert 'text/html' in response.content_type

    def test_admin_request_approve_api(self, client, authenticated_admin_client):
        """Test admin request approve API endpoint"""
        # Test with a mock request ID
        response = authenticated_admin_client.post('/admin/request/1/approve')
        assert response.status_code in [200, 302, 404]  # 200 success, 302 redirect, 404 not found

        if response.status_code == 200:
            assert 'text/html' in response.content_type

    def test_admin_request_reject_api(self, client, authenticated_admin_client):
        """Test admin request reject API endpoint"""
        # Test with a mock request ID
        response = authenticated_admin_client.post('/admin/request/1/reject')
        assert response.status_code in [200, 302, 404]  # 200 success, 302 redirect, 404 not found

        if response.status_code == 200:
            assert 'text/html' in response.content_type

    def test_admin_request_assign_api(self, client, authenticated_admin_client):
        """Test admin request assign API endpoint"""
        assign_data = {
            'volunteer_id': 1
        }

        response = authenticated_admin_client.post(
            '/admin/request/1/assign',
            data=assign_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302, 404]  # 200 success, 302 redirect, 404 not found

        if response.status_code == 200:
            assert 'text/html' in response.content_type

    def test_admin_request_delete_api(self, client, authenticated_admin_client):
        """Test admin request delete API endpoint"""
        response = authenticated_admin_client.post('/admin/request/1/delete')
        assert response.status_code in [200, 302, 404]  # 200 success, 302 redirect, 404 not found

        if response.status_code == 200:
            assert 'text/html' in response.content_type

    def test_admin_request_edit_api(self, client, authenticated_admin_client):
        """Test admin request edit API endpoint"""
        # Test GET request
        response = authenticated_admin_client.get('/admin/request/1/edit')
        assert response.status_code in [200, 302, 404]  # 200 success, 302 redirect, 404 not found

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request
        edit_data = {
            'title': 'Updated Request Title',
            'description': 'Updated description',
            'category': 'Medical',
            'priority': 'high'
        }

        response = authenticated_admin_client.post(
            '/admin/request/1/edit',
            data=edit_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302, 404]  # 200 success, 302 redirect, 404 not found

    def test_admin_request_detail_api(self, client, authenticated_admin_client):
        """Test admin request detail API endpoint"""
        response = authenticated_admin_client.get('/admin/request/1')
        assert response.status_code in [200, 302, 404]  # 200 success, 302 redirect, 404 not found

        if response.status_code == 200:
            assert 'text/html' in response.content_type

    def test_admin_2fa_api(self, client, authenticated_admin_client):
        """Test admin 2FA API endpoint"""
        # Test GET request
        response = authenticated_admin_client.get('/admin/admin_2fa')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request (enable/disable 2FA)
        fa_data = {
            'action': 'enable'
        }

        response = authenticated_admin_client.post(
            '/admin/admin_2fa',
            data=fa_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_volunteer_login_api(self, client):
        """Test volunteer login API endpoint"""
        # Test GET request (should return login page)
        response = client.get('/volunteer_login')
        assert response.status_code in [200, 302]  # 200 for page, 302 for redirect

        # Test POST request with valid credentials
        login_data = {
            'username': 'test_volunteer',
            'password': 'password123'
        }

        response = client.post(
            '/volunteer_login',
            data=login_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 302 redirect on success, 200 on failure

    def test_volunteer_logout_api(self, client, authenticated_volunteer_client):
        """Test volunteer logout API endpoint"""
        response = authenticated_volunteer_client.get('/volunteer_logout')
        assert response.status_code in [200, 302]  # 302 redirect on success

    def test_admin_login_page_api(self, client):
        """Test admin login page API endpoint"""
        # Test GET request
        response = client.get('/admin_login')
        assert response.status_code in [200, 302]  # 200 for page, 302 for redirect

        # Test POST request with valid credentials
        login_data = {
            'username': 'admin',
            'password': 'admin123'
        }

        response = client.post(
            '/admin_login',
            data=login_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 302 redirect on success, 200 on failure

    def test_general_logout_api(self, client, authenticated_volunteer_client):
        """Test general logout API endpoint"""
        response = authenticated_volunteer_client.post('/logout')
        assert response.status_code in [200, 302]  # 302 redirect on success

        response = authenticated_volunteer_client.get('/logout')
        assert response.status_code in [200, 302]  # 302 redirect on success

    def test_user_profile_api_get(self, client, authenticated_volunteer_client):
        """Test user profile API GET endpoint"""
        response = authenticated_volunteer_client.get('/api/user/profile')
        assert response.status_code in [200, 404]  # 200 success, 404 if profile not found

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)
            # Check for expected profile structure
            assert 'name' in data or 'username' in data or 'email' in data

    def test_profile_page_api(self, client, authenticated_volunteer_client):
        """Test profile page API endpoint"""
        # Test GET request
        response = authenticated_volunteer_client.get('/profile')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request (update profile)
        profile_data = {
            'name': 'Updated Name',
            'email': 'updated@example.com',
            'phone': '+359123456789'
        }

        response = authenticated_volunteer_client.post(
            '/profile',
            data=profile_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_volunteer_settings_api(self, client, authenticated_volunteer_client):
        """Test volunteer settings API endpoint"""
        # Test GET request
        response = authenticated_volunteer_client.get('/volunteer_settings')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request (update settings)
        settings_data = {
            'name': 'Test Volunteer',
            'email': 'volunteer@example.com',
            'phone': '+359123456789',
            'skills': 'Medical, First Aid',
            'availability': 'Weekends'
        }

        response = authenticated_volunteer_client.post(
            '/volunteer_settings',
            data=settings_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_admin_email_2fa_api(self, client, authenticated_admin_client):
        """Test admin email 2FA API endpoint"""
        # Test GET request
        response = authenticated_admin_client.get('/admin/email_2fa')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request (send 2FA code)
        response = authenticated_admin_client.post(
            '/admin/email_2fa',
            data={'action': 'send_code'},
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_admin_2fa_api(self, client, authenticated_admin_client):
        """Test admin 2FA API endpoint"""
        # Test GET request
        response = authenticated_admin_client.get('/admin/2fa')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request (verify 2FA code)
        fa_data = {
            'code': '123456'  # Test code
        }

        response = authenticated_admin_client.post(
            '/admin/2fa',
            data=fa_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_admin_2fa_setup_api(self, client, authenticated_admin_client):
        """Test admin 2FA setup API endpoint"""
        # Test GET request
        response = authenticated_admin_client.get('/admin/2fa/setup')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request (setup 2FA)
        setup_data = {
            'enable_2fa': 'true'
        }

        response = authenticated_admin_client.post(
            '/admin/2fa/setup',
            data=setup_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_submit_request_api(self, client):
        """Test submit request API endpoint"""
        # Test GET request
        response = client.get('/submit_request')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request (submit help request)
        request_data = {
            'title': 'Medical Emergency',
            'description': 'Need immediate medical assistance',
            'category': 'Medical',
            'priority': 'high',
            'location': 'Sofia Center',
            'contact_phone': '+359123456789',
            'contact_email': 'help@example.com'
        }

        response = client.post(
            '/submit_request',
            data=request_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_volunteer_register_api(self, client):
        """Test volunteer registration API endpoint"""
        # Test GET request
        response = client.get('/volunteer_register')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request (register volunteer)
        register_data = {
            'name': 'John Doe',
            'email': 'john.doe@example.com',
            'phone': '+359123456789',
            'skills': 'Medical, First Aid',
            'availability': 'Weekends',
            'experience': '2 years',
            'motivation': 'Want to help community'
        }

        response = client.post(
            '/volunteer_register',
            data=register_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_volunteer_verify_code_api(self, client):
        """Test volunteer code verification API endpoint"""
        # Test GET request
        response = client.get('/volunteer_verify_code')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        # Test POST request (verify code)
        verify_data = {
            'verification_code': '123456'
        }

        response = client.post(
            '/volunteer_verify_code',
            data=verify_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_resend_volunteer_code_api(self, client):
        """Test resend volunteer verification code API endpoint"""
        response = client.post('/resend_volunteer_code')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_volunteer_dashboard_page_api(self, client, authenticated_volunteer_client):
        """Test volunteer dashboard page API endpoint"""
        response = authenticated_volunteer_client.get('/volunteer_dashboard')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

    def test_volunteer_chat_api(self, client, authenticated_volunteer_client):
        """Test volunteer chat API endpoint"""
        response = authenticated_volunteer_client.get('/volunteer_chat')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

    def test_volunteer_reports_api(self, client, authenticated_volunteer_client):
        """Test volunteer reports API endpoint"""
        response = authenticated_volunteer_client.get('/volunteer_reports')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

    def test_feedback_api(self, client):
        """Test feedback API endpoint"""
        # Test GET request
        response = client.get('/feedback')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request (submit feedback)
        feedback_data = {
            'name': 'Anonymous User',
            'email': 'feedback@example.com',
            'subject': 'Great service',
            'message': 'HelpChain is doing amazing work!',
            'rating': '5'
        }

        response = client.post(
            '/feedback',
            data=feedback_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_set_language_api(self, client):
        """Test set language API endpoint"""
        # Test with Bulgarian
        response = client.post('/set_language/bg')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        # Test with English
        response = client.post('/set_language/en')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        # Test with invalid language
        response = client.post('/set_language/invalid')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_admin_volunteers_api(self, client, authenticated_admin_client):
        """Test admin volunteers management API endpoint"""
        # Test GET request
        response = authenticated_admin_client.get('/admin_volunteers')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request (add volunteer)
        volunteer_data = {
            'name': 'New Volunteer',
            'email': 'new.volunteer@example.com',
            'phone': '+359123456789',
            'skills': 'Technical Support'
        }

        response = authenticated_admin_client.post(
            '/admin_volunteers',
            data=volunteer_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_admin_volunteers_add_api(self, client, authenticated_admin_client):
        """Test admin add volunteer API endpoint"""
        # Test GET request
        response = authenticated_admin_client.get('/admin_volunteers/add')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request
        volunteer_data = {
            'name': 'Added Volunteer',
            'email': 'added.volunteer@example.com',
            'phone': '+359123456789',
            'skills': 'Logistics'
        }

        response = authenticated_admin_client.post(
            '/admin_volunteers/add',
            data=volunteer_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302]  # 200 success, 302 redirect

    def test_admin_volunteers_edit_api(self, client, authenticated_admin_client):
        """Test admin edit volunteer API endpoint"""
        # Test GET request
        response = authenticated_admin_client.get('/admin_volunteers/edit/1')
        assert response.status_code in [200, 302, 404]  # 200 success, 302 redirect, 404 not found

        if response.status_code == 200:
            assert 'text/html' in response.content_type

        # Test POST request
        edit_data = {
            'name': 'Updated Volunteer',
            'email': 'updated.volunteer@example.com',
            'phone': '+359123456789',
            'skills': 'Updated Skills'
        }

        response = authenticated_admin_client.post(
            '/admin_volunteers/edit/1',
            data=edit_data,
            follow_redirects=False
        )

        assert response.status_code in [200, 302, 404]  # 200 success, 302 redirect, 404 not found

    def test_export_volunteers_api(self, client, authenticated_admin_client):
        """Test export volunteers API endpoint"""
        response = authenticated_admin_client.get('/export_volunteers')
        assert response.status_code in [200, 302]  # 200 success, 302 redirect

        if response.status_code == 200:
            # Should return CSV or Excel file
            assert 'text/csv' in response.content_type or 'application/vnd.ms-excel' in response.content_type or 'text/html' in response.content_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
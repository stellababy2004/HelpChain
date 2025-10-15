#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for analytics service fixes
Tests the get_db() function and AdminUser import fixes
"""

import sys
import os
import unittest

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, backend_path)

from flask import Flask


class TestAnalyticsFixes(unittest.TestCase):
    """Test analytics service fixes"""
    
    def setUp(self):
        """Set up test Flask app"""
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        self.app.config['TESTING'] = True
        
        # Import and initialize extensions
        from extensions import db
        self.db = db
        db.init_app(self.app)
        
        # Create app context
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Import all models to register them with SQLAlchemy
        import models
        import models_with_analytics
        
        # Create all tables
        db.create_all()
    
    def tearDown(self):
        """Tear down test database"""
        self.db.session.remove()
        self.db.drop_all()
        self.app_context.pop()
    
    def test_get_db_function_exists(self):
        """Test that get_db() function exists and is callable"""
        from analytics_service import get_db
        self.assertTrue(callable(get_db))
    
    def test_get_db_returns_database_instance(self):
        """Test that get_db() returns a valid database instance"""
        from analytics_service import get_db
        db_instance = get_db()
        self.assertIsNotNone(db_instance)
        self.assertTrue(hasattr(db_instance, 'session'))
    
    def test_admin_user_import_in_models_with_analytics(self):
        """Test that AdminUser is imported in models_with_analytics"""
        from models_with_analytics import AdminUser
        self.assertIsNotNone(AdminUser)
    
    def test_analytics_service_works_with_flask_context(self):
        """Test that analytics service works within Flask app context"""
        from analytics_service import analytics_service
        
        result = analytics_service.get_dashboard_analytics(days=30)
        
        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertIn('overview', result)
        self.assertIn('user_engagement', result)
        self.assertIn('chatbot_analytics', result)
        self.assertNotIn('error', result)
    
    def test_two_factor_auth_admin_user_relationship(self):
        """Test that TwoFactorAuth -> AdminUser relationship works"""
        from models_with_analytics import TwoFactorAuth
        from models import AdminUser
        from werkzeug.security import generate_password_hash
        from datetime import datetime, timedelta
        
        # Create an AdminUser
        admin = AdminUser(
            username='test_admin',
            email='test@example.com',
            password_hash=generate_password_hash('testpass')
        )
        self.db.session.add(admin)
        self.db.session.commit()
        
        # Create a TwoFactorAuth record
        twofa = TwoFactorAuth(
            admin_user_id=admin.id,
            session_token='test_token_123',
            expires_at=datetime.now() + timedelta(hours=1)
        )
        self.db.session.add(twofa)
        self.db.session.commit()
        
        # Verify relationship
        self.assertIsNotNone(twofa.admin_user)
        self.assertEqual(twofa.admin_user.username, 'test_admin')
    
    def test_admin_session_admin_user_relationship(self):
        """Test that AdminSession -> AdminUser relationship works"""
        from models_with_analytics import AdminSession
        from models import AdminUser
        from werkzeug.security import generate_password_hash
        
        # Create an AdminUser
        admin = AdminUser(
            username='test_admin2',
            email='test2@example.com',
            password_hash=generate_password_hash('testpass')
        )
        self.db.session.add(admin)
        self.db.session.commit()
        
        # Create an AdminSession record
        session = AdminSession(
            admin_user_id=admin.id,
            session_id='session_123',
            ip_address='127.0.0.1'
        )
        self.db.session.add(session)
        self.db.session.commit()
        
        # Verify relationship
        self.assertIsNotNone(session.admin_user)
        self.assertEqual(session.admin_user.username, 'test_admin2')
    
    def test_analytics_event_tracking(self):
        """Test that analytics event tracking works without conflicts"""
        from analytics_service import analytics_service
        from models_with_analytics import AnalyticsEvent
        
        # Track an event
        success = analytics_service.track_event(
            event_type='page_view',
            event_category='navigation',
            event_action='view',
            context={
                'session_id': 'test_session',
                'page_url': '/test',
                'user_type': 'guest'
            }
        )
        
        self.assertTrue(success)
        
        # Verify event was created
        events = AnalyticsEvent.query.all()
        self.assertGreater(len(events), 0)
        self.assertEqual(events[0].event_type, 'page_view')
    
    def test_no_sqlalchemy_instance_conflicts(self):
        """Test that multiple calls don't cause SQLAlchemy instance conflicts"""
        from analytics_service import analytics_service
        
        # Make multiple calls
        result1 = analytics_service.get_dashboard_analytics(days=30)
        result2 = analytics_service.get_dashboard_analytics(days=7)
        result3 = analytics_service.get_dashboard_analytics(days=90)
        
        # All should succeed
        self.assertIsInstance(result1, dict)
        self.assertIsInstance(result2, dict)
        self.assertIsInstance(result3, dict)
        
        # All should have proper structure
        for result in [result1, result2, result3]:
            self.assertIn('overview', result)
            self.assertNotIn('error', result)


if __name__ == '__main__':
    unittest.main()

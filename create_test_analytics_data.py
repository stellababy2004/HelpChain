#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to populate HelpChain database with test analytics data
"""

import sys
import os
from datetime import datetime, timedelta
import random
import json
from werkzeug.security import generate_password_hash

# Add backend to path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)

from appy import app, db
from models import User, Volunteer, HelpRequest, AdminUser
from models_with_analytics import (
    AnalyticsEvent,
    UserBehavior,
    ChatbotConversation,
    PerformanceMetrics,
)
from analytics_service import analytics_service


def create_test_data():
    """Create comprehensive test data for analytics"""

    with app.app_context():
        print("🚀 Starting test data creation...")

        # Clear existing data
        print("🧹 Clearing existing analytics data...")
        AnalyticsEvent.query.delete()
        UserBehavior.query.delete()
        ChatbotConversation.query.delete()
        PerformanceMetrics.query.delete()
        HelpRequest.query.delete()
        Volunteer.query.delete()
        User.query.delete()

        db.session.commit()

        # Create test users
        print("👥 Creating test users...")
        users = []
        for i in range(50):
            user = User(
                username=f"user{i+1}",
                email=f"user{i+1}@test.com",
                password_hash=generate_password_hash(f"password{i+1}"),
                role=random.choice(["user", "volunteer"]),
            )
            users.append(user)
            db.session.add(user)

        # Create test volunteers
        print("🤝 Creating test volunteers...")
        volunteers = []
        skills_list = [
            "Медицинска помощ",
            "Транспорт",
            "Домакинска помощ",
            "Образование",
            "Правна помощ",
            "Психологическа помощ",
        ]

        for i in range(25):
            volunteer = Volunteer(
                name=f"Volunteer {i+1}",
                email=f"volunteer{i+1}@test.com",
                phone=f"0888987{i:03d}",
                location=random.choice(["София", "Пловдив", "Варна", "Бургас", "Русе"]),
                skills=", ".join(random.sample(skills_list, random.randint(1, 3))),
            )
            volunteers.append(volunteer)
            db.session.add(volunteer)

        # Create test help requests
        print("📋 Creating test help requests...")
        statuses = ["Pending", "In Progress", "Completed", "Cancelled"]

        help_requests = []
        for i in range(100):
            request_date = datetime.now() - timedelta(days=random.randint(0, 30))
            hr = HelpRequest(
                user_id=random.choice(users).id if random.random() > 0.3 else None,
                title=f"Заявка за помощ {i+1}",
                description=f"Описание на заявка {i+1}. Нуждая се от спешна помощ.",
                status=random.choice(statuses),
                name=f"Име {i+1}",
                email=f"request{i+1}@test.com",
                phone=f"0888123{i:03d}",
                message=f"Подробно съобщение за помощ {i+1}",
                created_at=request_date,
                updated_at=request_date + timedelta(hours=random.randint(1, 72)),
            )
            help_requests.append(hr)
            db.session.add(hr)

        db.session.commit()
        print("✅ Basic data created")

        # Create analytics events for the last 30 days
        print("📊 Creating analytics events...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        current_date = start_date
        session_counter = 0

        while current_date <= end_date:
            # Create 10-50 sessions per day
            sessions_today = random.randint(10, 50)

            for session_num in range(sessions_today):
                session_id = f"session_{session_counter:06d}"
                session_counter += 1

                # User behavior for this session
                user_type = random.choice(["guest", "user", "volunteer"])
                device_type = random.choice(["desktop", "mobile", "tablet"])
                entry_page = random.choice(
                    ["/", "/analytics", "/volunteer_register", "/submit_request"]
                )

                # Create UserBehavior record
                user_behavior = UserBehavior(
                    session_id=session_id,
                    user_type=user_type,
                    device_info=device_type,
                    user_agent=f"Chrome/{random.randint(90, 120)}.0.0.0 Mobile Safari/537.36",
                    location=random.choice(
                        ["София", "Пловдив", "Варна", "Бургас", "Русе"]
                    ),
                    entry_page=entry_page,
                    exit_page=random.choice(
                        ["/", "/analytics", "/volunteer_register", "/submit_request"]
                    ),
                    session_start=current_date + timedelta(hours=random.randint(0, 23)),
                    total_time_spent=random.randint(30, 1800),  # 30 sec to 30 min
                    pages_visited=random.randint(1, 10),
                    bounce_rate=random.random() < 0.3,  # 30% bounce rate
                    conversion_action=(
                        random.choice(
                            [None, "registration", "help_request", "chatbot_use"]
                        )
                        if random.random() > 0.7
                        else None
                    ),
                )

                # Set session start time properly
                session_start = current_date + timedelta(
                    hours=random.randint(0, 23), minutes=random.randint(0, 59)
                )
                user_behavior.session_start = session_start
                user_behavior.last_activity = session_start + timedelta(
                    seconds=user_behavior.total_time_spent
                )

                db.session.add(user_behavior)

                # Create page view events for this session
                pages_viewed = user_behavior.pages_visited
                for page_num in range(pages_viewed):
                    page_url = random.choice(
                        [
                            "/",
                            "/analytics",
                            "/volunteer_register",
                            "/submit_request",
                            "/privacy",
                            "/terms",
                            "/faq",
                            "/chat",
                        ]
                    )

                    event_time = session_start + timedelta(
                        seconds=random.randint(0, user_behavior.total_time_spent)
                    )

                    event = AnalyticsEvent(
                        event_type="page_view",
                        event_category="navigation",
                        event_action="view",
                        event_label=page_url,
                        user_session=session_id,
                        user_type=user_type,
                        page_url=page_url,
                        page_title=f"HelpChain - {page_url.strip('/') or 'Home'}",
                        device_type=device_type,
                        created_at=event_time,
                    )
                    db.session.add(event)

                    # Add some user interactions
                    if random.random() > 0.7:
                        interaction_event = AnalyticsEvent(
                            event_type="user_interaction",
                            event_category="engagement",
                            event_action=random.choice(
                                ["click", "scroll", "form_start", "form_submit"]
                            ),
                            user_session=session_id,
                            user_type=user_type,
                            page_url=page_url,
                            created_at=event_time
                            + timedelta(seconds=random.randint(1, 30)),
                        )
                        db.session.add(interaction_event)

            current_date += timedelta(days=1)

        db.session.commit()
        print("✅ Analytics events created")

        # Create chatbot conversations
        print("🤖 Creating chatbot conversations...")
        conversation_types = ["greeting", "help_request", "information", "complaint"]
        response_types = ["static", "ai", "fallback"]

        for i in range(200):
            conv_date = datetime.now() - timedelta(days=random.randint(0, 30))

            conversation = ChatbotConversation(
                session_id=f"chat_session_{i:04d}",
                user_message=random.choice(
                    [
                        "Здравейте, как мога да помогна?",
                        "Имам нужда от помощ с пазаруване",
                        "Къде мога да се регистрирам като доброволец?",
                        "Как работи системата?",
                        "Имам проблем с регистрацията",
                    ]
                ),
                bot_response="Благодаря за съобщението ви. Ще се свържем с вас скоро.",
                response_type=random.choice(response_types),
                ai_confidence=(
                    random.uniform(0.7, 0.95) if random.random() > 0.3 else None
                ),
                processing_time=(
                    random.uniform(0.1, 2.0) if random.random() > 0.3 else None
                ),
                ai_tokens_used=(
                    random.randint(50, 200) if random.random() > 0.3 else None
                ),
                user_rating=(
                    random.choice([None, 3, 4, 5]) if random.random() > 0.6 else None
                ),
                page_url=random.choice(["/", "/analytics", "/contact"]),
                user_type=random.choice(["user", "volunteer", "guest"]),
            )
            db.session.add(conversation)

        db.session.commit()
        print("✅ Chatbot conversations created")

        # Create performance metrics
        print("⚡ Creating performance metrics...")
        endpoints = [
            "/",
            "/analytics",
            "/volunteer_register",
            "/submit_request",
            "/api/analytics/data",
            "/api/chat/rooms",
            "/chat",
        ]

        for i in range(500):
            metric_date = datetime.now() - timedelta(days=random.randint(0, 30))

            metric = PerformanceMetrics(
                metric_type=random.choice(
                    ["response_time", "cpu_usage", "memory_usage", "db_query_time"]
                ),
                metric_name=(
                    f"endpoint_{random.choice(endpoints)}"
                    if random.random() > 0.3
                    else "system_load"
                ),
                metric_value=random.uniform(
                    0.1, 5.0
                ),  # response time in seconds or percentage
                endpoint=random.choice(endpoints) if random.random() > 0.5 else None,
                created_at=metric_date,
            )
            db.session.add(metric)

        db.session.commit()
        print("✅ Performance metrics created")

        # Create some feedback events
        print("💬 Creating feedback events...")
        for i in range(20):
            feedback_date = datetime.now() - timedelta(days=random.randint(0, 30))

            analytics_service.track_event(
                event_type="user_feedback",
                event_category="engagement",
                event_action="submit_feedback",
                context={
                    "session_id": f"feedback_session_{i}",
                    "user_type": random.choice(["user", "volunteer", "guest"]),
                    "feedback_length": random.randint(10, 200),
                    "has_email": random.random() > 0.3,
                    "page_url": random.choice(["/", "/analytics", "/contact"]),
                    "ip_address": f"192.168.1.{random.randint(1, 255)}",
                },
            )

        print("🎉 All test data created successfully!")
        print("\n📊 Summary:")
        print(f"   Users: {len(users)}")
        print(f"   Volunteers: {len(volunteers)}")
        print(f"   Help Requests: {len(help_requests)}")
        print(f"   Analytics Events: {AnalyticsEvent.query.count()}")
        print(f"   User Behaviors: {UserBehavior.query.count()}")
        print(f"   Chatbot Conversations: {ChatbotConversation.query.count()}")
        print(f"   Performance Metrics: {PerformanceMetrics.query.count()}")

        print("\n🌐 Test the analytics at: http://127.0.0.1:5000/analytics")


if __name__ == "__main__":
    create_test_data()

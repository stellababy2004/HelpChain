#!/usr/bin/env python3
"""
Script to create database indexes for performance optimization
"""
from appy import app, db
from performance_optimization import DatabaseOptimizer

with app.app_context():
    print("Creating database indexes...")
    success = DatabaseOptimizer.create_analytics_indexes(db)
    if success:
        print("✅ Database indexes created successfully!")
    else:
        print("❌ Failed to create database indexes")

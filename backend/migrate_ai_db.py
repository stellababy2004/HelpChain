# -*- coding: utf-8 -*-
"""
Database migration script for AI features
Добавя нови полета за AI функционалност
"""

import os
import sys
sys.path.append(os.path.dirname(__file__))

from appy import app, db
from models import ChatbotConversation

def migrate_database():
    """Мигриране на базата данни за AI полета"""
    print("🔧 Започваме миграция на базата данни за AI функционалност...")
    
    with app.app_context():
        try:
            # Проверяваме дали полетата вече съществуват
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('chatbot_conversations')]
            
            ai_columns = [
                'ai_provider', 'ai_model', 'ai_confidence', 
                'ai_tokens_used', 'language_detected', 'processing_time'
            ]
            
            missing_columns = [col for col in ai_columns if col not in columns]
            
            if not missing_columns:
                print("✅ Всички AI полета вече съществуват в базата данни!")
                return True
                
            print(f"🔄 Добавяме липсващи колони: {missing_columns}")
            
            # Добавяме липсващите колони
            with db.engine.connect() as conn:
                if 'ai_provider' not in columns:
                    conn.execute(db.text("ALTER TABLE chatbot_conversations ADD COLUMN ai_provider VARCHAR(50)"))
                    print("✅ Добавена колона: ai_provider")
                    
                if 'ai_model' not in columns:
                    conn.execute(db.text("ALTER TABLE chatbot_conversations ADD COLUMN ai_model VARCHAR(100)"))
                    print("✅ Добавена колона: ai_model")
                    
                if 'ai_confidence' not in columns:
                    conn.execute(db.text("ALTER TABLE chatbot_conversations ADD COLUMN ai_confidence FLOAT"))
                    print("✅ Добавена колона: ai_confidence")
                    
                if 'ai_tokens_used' not in columns:
                    conn.execute(db.text("ALTER TABLE chatbot_conversations ADD COLUMN ai_tokens_used INTEGER"))
                    print("✅ Добавена колона: ai_tokens_used")
                    
                if 'language_detected' not in columns:
                    conn.execute(db.text("ALTER TABLE chatbot_conversations ADD COLUMN language_detected VARCHAR(10)"))
                    print("✅ Добавена колона: language_detected")
                    
                if 'processing_time' not in columns:
                    conn.execute(db.text("ALTER TABLE chatbot_conversations ADD COLUMN processing_time FLOAT"))
                    print("✅ Добавена колона: processing_time")
                    
                conn.commit()
            
            print("🎉 Миграцията завърши успешно!")
            return True
            
        except Exception as e:
            print(f"❌ Грешка при миграция: {e}")
            return False

if __name__ == "__main__":
    migrate_database()
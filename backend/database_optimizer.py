"""
Performance Test - Database Indexing Implementation
==================================================

След като видяхме, че cache системата работи в рамките на един процес, но не се запазва между
отделните Flask заявки в development режим, нека фокусираме върху втората критична оптимизация:
ИНДЕКСИРАНЕ НА БАЗАТА ДАННИ за 60-90% подобрение на SQL заявките.
"""

import os
import sys

sys.path.insert(
    0,
    r"c:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend",
)

import sqlite3
import time
from datetime import datetime


class DatabaseIndexOptimizer:
    def __init__(self, db_path):
        self.db_path = db_path

    def analyze_current_performance(self):
        """Анализира текущата performance на базата данни"""
        print("🔍 АНАЛИЗ НА БАЗАТА ДАННИ")
        print("=" * 50)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 1. Броя записи в analytics_events таблицата
            cursor.execute("SELECT COUNT(*) FROM analytics_events")
            event_count = cursor.fetchone()[0]
            print(f"📊 Analytics events: {event_count:,}")

            # 2. Тест на заявка без индекси
            print("\n⏱️  Тестване на заявки БЕЗ индекси:")

            start_time = time.time()
            cursor.execute(
                """
                SELECT event_type, COUNT(*) as count
                FROM analytics_events
                WHERE created_at >= date('now', '-30 days')
                GROUP BY event_type
                ORDER BY count DESC
            """
            )
            results = cursor.fetchall()
            query_time_no_index = time.time() - start_time

            print(f"   ⚡ Заявка за събития за 30 дни: {query_time_no_index:.3f}s")
            print(f"   📋 Резултати: {len(results)} типа събития")

            # 3. Проверка на съществуващи индекси
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='analytics_events'"
            )
            existing_indexes = cursor.fetchall()
            print(f"\n📑 Съществуващи индекси: {len(existing_indexes)}")
            for idx in existing_indexes:
                print(f"   - {idx[0]}")

            return query_time_no_index, event_count

        finally:
            conn.close()

    def create_performance_indexes(self):
        """Създава оптимизирани индекси за analytics заявки"""
        print("\n🔨 СЪЗДАВАНЕ НА PERFORMANCE ИНДЕКСИ")
        print("=" * 50)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        indexes_to_create = [
            {
                "name": "idx_analytics_timestamp",
                "sql": "CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics_events(created_at)",
                "purpose": "Ускорява date range филтри",
            },
            {
                "name": "idx_analytics_event_type",
                "sql": "CREATE INDEX IF NOT EXISTS idx_analytics_event_type ON analytics_events(event_type)",
                "purpose": "Ускорява филтри по тип събитие",
            },
            {
                "name": "idx_analytics_composite",
                "sql": "CREATE INDEX IF NOT EXISTS idx_analytics_composite ON analytics_events(created_at, event_type)",
                "purpose": "Комбинирани заявки по дата и тип",
            },
            {
                "name": "idx_analytics_user_timestamp",
                "sql": "CREATE INDEX IF NOT EXISTS idx_analytics_user_timestamp ON analytics_events(user_session, created_at)",
                "purpose": "Потребителски analytics по време",
            },
        ]

        try:
            for index in indexes_to_create:
                print(f"\n📍 Създаване на {index['name']}...")
                print(f"   💡 Цел: {index['purpose']}")

                start_time = time.time()
                cursor.execute(index["sql"])
                creation_time = time.time() - start_time

                print(f"   ✅ Създаден за {creation_time:.3f}s")

            conn.commit()
            print("\n✅ Всички индекси са създадени успешно!")

        except Exception as e:
            print(f"❌ Грешка при създаване на индекси: {e}")
            conn.rollback()
        finally:
            conn.close()

    def test_indexed_performance(self):
        """Тестване на performance след добавяне на индекси"""
        print("\n⚡ ТЕСТВАНЕ НА PERFORMANCE С ИНДЕКСИ")
        print("=" * 50)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Същата заявка като преди, но сега с индекси
            start_time = time.time()
            cursor.execute(
                """
                SELECT event_type, COUNT(*) as count
                FROM analytics_events
                WHERE created_at >= date('now', '-30 days')
                GROUP BY event_type
                ORDER BY count DESC
            """
            )
            results = cursor.fetchall()
            query_time_with_index = time.time() - start_time

            print(f"   ⚡ Заявка за събития за 30 дни: {query_time_with_index:.3f}s")
            print(f"   📋 Резултати: {len(results)} типа събития")

            return query_time_with_index

        finally:
            conn.close()

    def run_comprehensive_optimization(self):
        """Пълна оптимизация на базата данни"""
        print("🚀 DATABASE PERFORMANCE OPTIMIZATION")
        print("=" * 80)
        print(f"База данни: {self.db_path}")
        print(f"Време: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 1. Анализ на текущото състояние
        original_time, record_count = self.analyze_current_performance()

        if record_count == 0:
            print("⚠️  Няма данни в analytics_event таблицата за тестване")
            return

        # 2. Създаване на индекси
        self.create_performance_indexes()

        # 3. Тестване след оптимизация
        optimized_time = self.test_indexed_performance()

        # 4. Анализ на подобренията
        if original_time > 0:
            improvement = ((original_time - optimized_time) / original_time) * 100
            speedup = (
                original_time / optimized_time if optimized_time > 0 else float("inf")
            )

            print("\n📈 РЕЗУЛТАТИ ОТ ОПТИМИЗАЦИЯТА")
            print("=" * 50)
            print(f"🐌 Преди оптимизация:  {original_time:.3f}s")
            print(f"🚀 След оптимизация:   {optimized_time:.3f}s")
            print(f"📊 Подобрение:         {improvement:.1f}%")
            print(f"⚡ Ускорение:          {speedup:.1f}x по-бързо")

            if improvement > 80:
                print("🏆 ПРЕВЪЗХОДЕН РЕЗУЛТАТ! Огромно подобрение")
            elif improvement > 50:
                print("🎯 ОТЛИЧЕН РЕЗУЛТАТ! Значимо подобрение")
            elif improvement > 20:
                print("✅ ДОБЪР РЕЗУЛТАТ! Видимо подобрение")
            elif improvement > 0:
                print("⚠️  УМЕРЕН РЕЗУЛТАТ! Малко подобрение")
            else:
                print("❌ БЕЗ ПОДОБРЕНИЕ! Нужни допълнителни оптимизации")

        print(
            f"\n🎉 DATABASE OPTIMIZATION ЗАВЪРШЕНА - {datetime.now().strftime('%H:%M:%S')}"
        )


if __name__ == "__main__":
    # Намери базата данни
    db_paths = [
        r"c:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend\instance\site.db",
        r"c:\Users\Stella Barbarella\OneDrive\Documents\chatGPT\Projet BG\HelpChain\backend\instance\volunteers.db",
    ]

    for db_path in db_paths:
        if os.path.exists(db_path):
            print(f"🎯 Намерена база данни: {db_path}")

            optimizer = DatabaseIndexOptimizer(db_path)
            optimizer.run_comprehensive_optimization()
            break
    else:
        print("❌ Не е намерена база данни за оптимизация")

"""
Background Notification Processor за HelpChain
Този скрипт стартира фонов процес за обработка на notification queue
"""

import time

import schedule

from appy import app
from notification_service import notification_service


def process_notifications():
    """Обработка на notification queue"""
    print(
        f"🔄 Starting notification queue processing at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    with app.app_context():
        try:
            stats = notification_service.process_queue(max_items=100)
            print(f"📊 Processing complete: {stats}")
        except Exception as e:
            print(f"❌ Error processing queue: {str(e)}")


def start_background_processor():
    """Стартира фонов процес за нотификации"""
    print("🚀 Starting HelpChain Notification Background Processor...")

    # Планираме да се изпълнява на всеки 2 минути
    schedule.every(2).minutes.do(process_notifications)

    # Първоначално изпълнение
    process_notifications()

    print("⏰ Scheduler configured to run every 2 minutes")
    print("🔄 Background processor is running. Press Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Проверява на всеки 30 секунди
    except KeyboardInterrupt:
        print("\n🛑 Background processor stopped by user")
    except Exception as e:
        print(f"❌ Background processor error: {str(e)}")


if __name__ == "__main__":
    start_background_processor()

#!/usr/bin/env python3
"""
HelpChain Notification Viewer
Command-line tool to view email notifications
"""

import os
import sqlite3
from datetime import datetime

DB_PATH = "notifications.db"


def view_notifications(limit=10):
    """View recent notifications"""
    if not os.path.exists(DB_PATH):
        print("❌ Database not found. Run notification_dashboard.py first.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM notifications ORDER BY timestamp DESC LIMIT ?", (limit,))
        notifications = c.fetchall()

    if not notifications:
        print("📭 Няма нотификации.")
        return

    print("📧 HelpChain Нотификации")
    print("=" * 60)

    for notification in notifications:
        id, timestamp, recipient, subject, content, status, smtp_error = notification

        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%d.%m.%Y %H:%M:%S")
        except Exception:
            time_str = timestamp

        # Status emoji
        if status == "sent":
            status_emoji = "✅"
        elif status == "saved":
            status_emoji = "💾"
        else:
            status_emoji = "❌"

        print(f"{status_emoji} [{time_str}] {subject}")
        print(f"   📧 До: {recipient}")
        print(f"   📝 {content.replace(chr(10), chr(10) + '   ')}")
        if smtp_error:
            print(f"   ⚠️  SMTP грешка: {smtp_error}")
        print("-" * 60)

    print(f"\n📊 Общо нотификации: {len(notifications)}")


def clear_notifications():
    """Clear all notifications"""
    if not os.path.exists(DB_PATH):
        print("❌ Database not found.")
        return

    confirm = input("Сигурни ли сте, че искате да изтриете всички нотификации? (y/N): ")
    if confirm.lower() != "y":
        print("Отменено.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM notifications")
        deleted_count = c.rowcount
        conn.commit()

    print(f"✅ Изтрити {deleted_count} нотификации.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear_notifications()
    else:
        limit = 10
        if len(sys.argv) > 1:
            try:
                limit = int(sys.argv[1])
            except Exception:
                pass
        view_notifications(limit)

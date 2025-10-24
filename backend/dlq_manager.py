#!/usr/bin/env python3
"""
HelpChain DLQ Management Script
Utilities for managing the Dead Letter Queue (DLQ) for failed emails
"""

import json
import os
import sys
from datetime import datetime

try:
    from redis import Redis
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure redis is installed: pip install redis")
    sys.exit(1)


def show_dlq_stats():
    """Show statistics about the current DLQ"""
    try:
        r = Redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"))
        dlq_length = r.llen("dlq:emails")

        print("📊 DLQ Statistics:")
        print(f"   Total emails in DLQ: {dlq_length}")

        if dlq_length > 0:
            # Show a sample email
            sample = r.lindex("dlq:emails", 0)
            if sample:
                try:
                    payload = json.loads(sample)
                    print(
                        f"   Sample email: {payload.get('subject', 'N/A')} -> {payload.get('recipients', [])}"
                    )
                    print(f"   Failed at: {payload.get('failed_at', 'N/A')}")
                except json.JSONDecodeError:
                    print("   Sample email: <invalid JSON>")

        return dlq_length

    except Exception as e:
        print(f"❌ Error accessing DLQ: {e}")
        return 0


def requeue_dlq_manually(limit=100):
    """Manually trigger DLQ requeue"""
    print("🔄 To manually requeue DLQ emails, run:")
    print(f"   celery -A celery_app call tasks.requeue_dlq_emails --args='[{limit}]'")
    print(
        "   or from Python: from tasks import requeue_dlq_emails; requeue_dlq_emails.delay({limit})"
    )
    print(
        "Note: This requires the full Flask/Celery application context to be running."
    )
    print("Note: The scheduled task runs every 15 minutes with limit=100.")
    print(
        "Note: Email sending is rate-limited to 30 emails per minute to comply with Zoho limits."
    )


def clear_dlq():
    """Clear all emails from DLQ (use with caution!)"""
    confirm = input(
        "⚠️  This will permanently delete all emails from DLQ. Continue? (yes/no): "
    )
    if confirm.lower() != "yes":
        print("Operation cancelled.")
        return

    try:
        r = Redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"))
        deleted_count = r.delete("dlq:emails")
        print(f"🗑️  Cleared {deleted_count} emails from DLQ")
    except Exception as e:
        print(f"❌ Error clearing DLQ: {e}")


def inspect_dlq(limit=5):
    """Inspect emails in DLQ"""
    try:
        r = Redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"))
        emails = r.lrange("dlq:emails", 0, limit - 1)

        print(f"🔍 Inspecting first {limit} emails in DLQ:")
        for i, email_data in enumerate(emails, 1):
            try:
                payload = json.loads(email_data)
                print(f"\n📧 Email {i}:")
                print(f"   Subject: {payload.get('subject', 'N/A')}")
                print(f"   Recipients: {payload.get('recipients', [])}")
                print(f"   Message ID: {payload.get('message_id', 'N/A')}")
                print(f"   Failed at: {payload.get('failed_at', 'N/A')}")
                print(f"   Reason: {payload.get('reason', 'N/A')}")
            except json.JSONDecodeError:
                print(f"\n📧 Email {i}: <invalid JSON data>")

    except Exception as e:
        print(f"❌ Error inspecting DLQ: {e}")


def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("HelpChain DLQ Management Tool")
        print("Usage: python dlq_manager.py <command> [options]")
        print("")
        print("Commands:")
        print("  stats              Show DLQ statistics")
        print(
            "  requeue [limit]    Manually requeue emails from DLQ (default limit: 10)"
        )
        print("  inspect [limit]    Inspect emails in DLQ (default limit: 5)")
        print("  clear              Clear all emails from DLQ (dangerous!)")
        print("")
        print("Examples:")
        print("  python dlq_manager.py stats")
        print("  python dlq_manager.py requeue 20")
        print("  python dlq_manager.py inspect")
        return

    command = sys.argv[1].lower()

    if command == "stats":
        show_dlq_stats()

    elif command == "requeue":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        requeue_dlq_manually(limit)

    elif command == "inspect":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        inspect_dlq(limit)

    elif command == "clear":
        clear_dlq()

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()

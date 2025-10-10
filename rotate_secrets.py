#!/usr/bin/env python3
"""
Secrets Rotation Script for HelpChain
Handles periodic rotation of SECRET_KEY and API keys
"""

import os
import secrets
import string
import json
from datetime import datetime
import argparse
import sys


def generate_secret_key(length=64):
    """Generate a cryptographically secure secret key"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_api_key(length=32):
    """Generate an API key (alphanumeric only)"""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def rotate_secrets(env_file=".env", backup=True):
    """Rotate secrets in environment file"""

    if not os.path.exists(env_file):
        print(f"❌ Environment file {env_file} not found")
        return False

    # Backup current file
    if backup:
        backup_file = f"{env_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with open(env_file, "r") as src, open(backup_file, "w") as dst:
            dst.write(src.read())
        print(f"✅ Backup created: {backup_file}")

    # Read current environment
    env_vars = {}
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key] = value

    # Rotate secrets
    changes = {}

    # Rotate SECRET_KEY
    if "SECRET_KEY" in env_vars:
        old_key = env_vars["SECRET_KEY"]
        new_key = generate_secret_key()
        env_vars["SECRET_KEY"] = new_key
        changes["SECRET_KEY"] = {
            "old": old_key[:10] + "...",
            "new": new_key[:10] + "...",
        }

    # Rotate API keys (add more as needed)
    api_keys_to_rotate = ["OPENAI_API_KEY", "GEMINI_API_KEY", "SENTRY_DSN"]
    for api_key in api_keys_to_rotate:
        if api_key in env_vars and env_vars[api_key]:
            old_key = env_vars[api_key]
            new_key = generate_api_key()
            env_vars[api_key] = new_key
            changes[api_key] = {
                "old": old_key[:10] + "...",
                "new": new_key[:10] + "...",
            }

    # Write updated environment file
    with open(env_file, "w") as f:
        f.write("# HelpChain Environment Variables\n")
        f.write(f"# Last rotated: {datetime.now().isoformat()}\n\n")

        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    print("✅ Secrets rotated successfully!")
    print("\n🔄 Changes made:")
    for key, change in changes.items():
        print(f"  {key}: {change['old']} → {change['new']}")

    # Create rotation log
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "changes": changes,
        "backup_file": backup_file if backup else None,
    }

    with open("secrets_rotation.log", "a") as log_file:
        json.dump(log_entry, log_file, indent=2)
        log_file.write("\n")

    return True


def check_rotation_schedule(last_rotation_file=".last_rotation"):
    """Check if rotation is due (recommended: every 90 days)"""

    if os.path.exists(last_rotation_file):
        with open(last_rotation_file, "r") as f:
            last_rotation = datetime.fromisoformat(f.read().strip())

        days_since_rotation = (datetime.now() - last_rotation).days

        if days_since_rotation < 90:
            print(
                f"ℹ️  Last rotation was {days_since_rotation} days ago. Next rotation due in {90 - days_since_rotation} days."
            )
            return False
        else:
            print(
                f"⚠️  Last rotation was {days_since_rotation} days ago. Rotation is overdue!"
            )
            return True
    else:
        print("ℹ️  No previous rotation record found. Running initial rotation.")
        return True


def main():
    parser = argparse.ArgumentParser(description="Rotate HelpChain secrets")
    parser.add_argument("--env-file", default=".env", help="Environment file to update")
    parser.add_argument(
        "--force", action="store_true", help="Force rotation even if not due"
    )
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")

    args = parser.parse_args()

    print("🔐 HelpChain Secrets Rotation Tool")
    print("=" * 40)

    # Check if rotation is due
    if not args.force and not check_rotation_schedule():
        if input("Continue anyway? (y/N): ").lower() != "y":
            sys.exit(0)

    # Perform rotation
    if rotate_secrets(args.env_file, not args.no_backup):
        # Update last rotation timestamp
        with open(".last_rotation", "w") as f:
            f.write(datetime.now().isoformat())

        print("\n✅ Rotation completed successfully!")
        print("\n📋 Next steps:")
        print("1. Test application with new secrets")
        print("2. Update any external services with new API keys")
        print("3. Deploy changes to production")
        print("4. Monitor for any authentication issues")
    else:
        print("❌ Rotation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()

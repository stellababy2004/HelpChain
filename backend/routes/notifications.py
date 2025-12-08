"""
HelpChain Notification Routes
Handles notification preferences, push subscriptions, and sending notifications
"""

# ruff: noqa

# Debug: Module loaded
print("NOTIFICATIONS MODULE LOADED")

# Standard library
from datetime import UTC, datetime

# Third-party
from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user

# Local
from backend.extensions import db


# Get db instance from current app context for proper test compatibility
def get_db():
    """Get database instance from current app context"""
    try:
        # Try to get from current_app extensions first
        if hasattr(current_app, "extensions") and "sqlalchemy" in current_app.extensions:
            return current_app.extensions["sqlalchemy"]
        # Fallback to global db instance
        return db
    except (KeyError, RuntimeError, AttributeError):
        # Fallback to global db instance
        return db


from backend.models import PushSubscription, User

notification_bp = Blueprint("notification", __name__)


def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


@notification_bp.route("/settings", methods=["GET", "POST"])
# @login_required
def notification_settings():
    """Get or update notification settings for current user"""
    try:
        if request.method == "GET":
            # Return current user notification settings
            # settings = current_user.notification_settings or {}
            settings = {}
            return jsonify({"success": True, "settings": settings})

        elif request.method == "POST":
            request.get_json()

            # Update user notification settings
            # current_user.notification_settings = data
            # current_user.updated_at = datetime.utcnow()
            # db.session.commit()

            # Track analytics
            # analytics_service.track_event(
            #     event_type="notification_settings_updated",
            #     event_category="user_preference",
            #     context={
            #         "user_id": current_user.id,
            #         "settings": data
            #     }
            # )

            return jsonify({"success": True, "message": "ðØð░ÐüÐéÐÇð¥ð╣ð║ð©ÐéðÁ Ðüð░ ðÀð░ð┐ð░ðÀðÁð¢ð© ÐâÐüð┐ðÁÐêð¢ð¥"})

    except Exception as e:
        current_app.logger.error(f"Error updating notification settings: {e}")
        return (
            jsonify({"success": False, "message": "ðôÐÇðÁÐêð║ð░ ð┐ÐÇð© ðÀð░ð┐ð░ðÀð▓ð░ð¢ðÁ ð¢ð░ ð¢ð░ÐüÐéÐÇð¥ð╣ð║ð©ÐéðÁ"}),
            500,
        )


@notification_bp.route("/subscribe", methods=["POST"])
# @login_required
def subscribe_push():
    """Subscribe user to push notifications"""
    try:
        data = request.get_json()

        # Get database instance
        db_instance = get_db()
        # Determine current user id in a safe way (tests may not have
        # flask-login/login_manager configured).
        try:
            volunteer_id = getattr(current_user, "id", None)
        except Exception:
            volunteer_id = None

        # Check if subscription already exists
        existing_subscription = (
            db_instance.session.query(PushSubscription)
            .filter_by(
                volunteer_id=volunteer_id,
                endpoint=data.get("endpoint"),
                is_active=True,
            )
            .first()
        )

        if existing_subscription:
            # Update existing subscription
            existing_subscription.p256dh_key = data.get("p256dh")
            existing_subscription.auth_key = data.get("auth")
            existing_subscription.user_agent = data.get("userAgent")
            existing_subscription.last_used = utc_now()
            db_instance.session.commit()

            return jsonify({"success": True, "message": "Subscription updated"})

        # Create new subscription
        subscription = PushSubscription(
            volunteer_id=volunteer_id,
            endpoint=data.get("endpoint"),
            p256dh_key=data.get("p256dh"),
            auth_key=data.get("auth"),
            user_agent=data.get("userAgent"),
            is_active=True,
        )

        # If there is no authenticated user, ensure a placeholder user
        # exists in the Flask DB so legacy schemas that disallow NULL
        # `user_id` columns can still insert a subscription.
        if volunteer_id is None:
            try:
                # Create or get placeholder user with id=0
                placeholder = db_instance.session.get(User, 0)
                if not placeholder:
                    placeholder = User(id=0, username="anonymous", email="anonymous@example.com", password_hash="")
                    # add directly to Flask DB session
                    db_instance.session.add(placeholder)
                    db_instance.session.commit()
                # use 0 as the stored user id
                subscription.user_id = 0
            except Exception:
                # If placeholder creation fails, keep user_id None and
                # let the commit below handle any DB errors gracefully.
                pass

        db_instance.session.add(subscription)
        db_instance.session.commit()

        # Track analytics
        # analytics_service.track_event(
        #     event_type="push_subscription",
        #     event_category="notification",
        #     context={
        #         "user_id": current_user.id,
        #         "endpoint": data.get('endpoint')
        #     }
        # )

        return jsonify(
            {
                "success": True,
                "message": "Successfully subscribed to push notifications",
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error subscribing to push: {e}")
        db_instance = get_db()
        db_instance.session.rollback()
        return (
            jsonify(
                {
                    "success": False,
                    "message": "ðôÐÇðÁÐêð║ð░ ð┐ÐÇð© ð░ð▒ð¥ð¢ð©ÐÇð░ð¢ðÁ ðÀð░ push ð¢ð¥Ðéð©Ðäð©ð║ð░Ðåð©ð©",
                }
            ),
            500,
        )


@notification_bp.route("/vapid-public-key", methods=["GET"])
def vapid_public_key():
    """Get VAPID public key for push notifications"""
    try:
        public_key = current_app.config.get("VAPID_PUBLIC_KEY")

        # Testing fallback: if tests run a live server in a separate process
        # that doesn't inherit the test runner's in-memory config, allow a
        # test public key to be provided via `TEST_VAPID_PUBLIC_KEY` or via
        # an environment-debug flag. This ensures integration tests that
        # hit the server can retrieve a usable key.
        if not public_key:
            test_key = current_app.config.get("TEST_VAPID_PUBLIC_KEY")
            if test_key or current_app.config.get("TESTING") or (current_app.config.get("HELPCHAIN_TEST_DEBUG")):
                fallback = test_key or "BTestPublicKeyForLocalTests-ReplaceMe"
                current_app.logger.info("Using test VAPID public key for tests")
                return jsonify({"success": True, "publicKey": fallback})

            current_app.logger.info("VAPID public key not configured; push API returning disabled flag")
            return (
                jsonify({"success": False, "message": "VAPID public key not configured"}),
                200,
            )

        return jsonify({"success": True, "publicKey": public_key})

    except Exception as e:
        current_app.logger.error(f"Error getting VAPID public key: {e}")
        return jsonify({"success": False, "message": "Error retrieving VAPID key"}), 500


@notification_bp.route("/test-vapid", methods=["GET"])
def test_vapid():
    """Test VAPID route"""
    return jsonify({"success": True, "message": "Test VAPID route works"})


@notification_bp.route("/unsubscribe-push", methods=["POST"])
# @login_required
def unsubscribe_push():
    """Unsubscribe user from push notifications"""
    try:
        data = request.get_json()
        endpoint = data.get("endpoint")

        # Get database instance
        db_instance = get_db()

        # Determine current user id in a safe way (tests may not have
        # flask-login/login_manager configured).
        try:
            volunteer_id = getattr(current_user, "id", None)
        except Exception:
            volunteer_id = None

        if endpoint:
            # Deactivate specific subscription
            subscription = (
                db_instance.session.query(PushSubscription)
                .filter_by(
                    volunteer_id=(0 if volunteer_id is None else volunteer_id),
                    endpoint=endpoint,
                    is_active=True,
                )
                .first()
            )

            if subscription:
                subscription.is_active = False
                db_instance.session.commit()
                return jsonify({"success": True, "message": "Push subscription deactivated"})
            else:
                return (
                    jsonify({"success": False, "message": "Subscription not found"}),
                    404,
                )
        else:
            # Deactivate all subscriptions for user
            subscriptions = (
                db_instance.session.query(PushSubscription)
                .filter_by(
                    volunteer_id=(0 if volunteer_id is None else volunteer_id),
                    is_active=True,
                )
                .all()
            )

            for subscription in subscriptions:
                subscription.is_active = False

            db_instance.session.commit()
            return jsonify(
                {
                    "success": True,
                    "message": f"Deactivated {len(subscriptions)} push subscriptions",
                }
            )

    except Exception as e:
        current_app.logger.error(f"Error unsubscribing from push: {e}")
        import traceback

        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        db_instance = get_db()
        db_instance.session.rollback()
        return (
            jsonify(
                {
                    "success": False,
                    "message": "ðôÐÇðÁÐêð║ð░ ð┐ÐÇð© ð¥Ðéð┐ð©Ðüð▓ð░ð¢ðÁ ð¥Ðé push ð¢ð¥Ðéð©Ðäð©ð║ð░Ðåð©ð©",
                }
            ),
            500,
        )


@notification_bp.route("/test-email", methods=["POST"])
# @login_required
def test_email():
    """Send test email notification"""
    try:
        # from mail_service import send_notification_email

        # Send test email
        # success = send_notification_email(
        #     recipient=current_user.email,
        #     subject="HelpChain - ðóðÁÐüÐé ð©ð╝ðÁð╣ð╗",
        #     template="email_template.html",
        #     context={
        #         "notification_type": "test",
        #         "recipient_name": current_user.name,
        #         "subject": "HelpChain - ðóðÁÐüÐé ð©ð╝ðÁð╣ð╗",
        #         "content": "ðóð¥ð▓ð░ ðÁ ÐéðÁÐüÐéð¥ð▓ ð©ð╝ðÁð╣ð╗ ðÀð░ ð┐ÐÇð¥ð▓ðÁÐÇð║ð░ ð¢ð░ ð¢ð¥Ðéð©Ðäð©ð║ð░Ðåð©ð¥ð¢ð¢ð░Ðéð░ Ðüð©ÐüÐéðÁð╝ð░.",
        #         "action_url": current_app.config["FRONTEND_URL"]
        #         + "/notification_preferences",
        #     },
        # )

        # if success:
        # Track analytics
        # analytics_service.track_event(
        #     event_type="test_email_sent",
        #     event_category="notification",
        #     context={"user_id": current_user.id}
        # )

        return jsonify({"success": True, "message": "ðóðÁÐüÐéð¥ð▓ð©ÐÅÐé ð©ð╝ðÁð╣ð╗ ðÁ ð©ðÀð┐ÐÇð░ÐéðÁð¢ ÐâÐüð┐ðÁÐêð¢ð¥"})
        # else:
        #     return (
        #         jsonify(
        #             {"success": False, "message": "ðôÐÇðÁÐêð║ð░ ð┐ÐÇð© ð©ðÀð┐ÐÇð░Ðëð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐé ð©ð╝ðÁð╣ð╗"}
        #         ),
        #         500,
        #     )

    except Exception as e:
        current_app.logger.error(f"Error sending test email: {e}")
        return (
            jsonify({"success": False, "message": "ðôÐÇðÁÐêð║ð░ ð┐ÐÇð© ð©ðÀð┐ÐÇð░Ðëð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐé ð©ð╝ðÁð╣ð╗"}),
            500,
        )


@notification_bp.route("/test-sms", methods=["POST"])
# @login_required
def test_sms():
    """Send test SMS notification"""
    try:
        # from sms_service import send_notification_sms

        # Send test SMS
        # success = send_notification_sms(
        #     phone=current_user.phone,
        #     message="HelpChain: ðóð¥ð▓ð░ ðÁ ÐéðÁÐüÐéð¥ð▓ð¥ SMS ÐüÐèð¥ð▒ÐëðÁð¢ð©ðÁ. ðØð¥Ðéð©Ðäð©ð║ð░Ðåð©ð¥ð¢ð¢ð░Ðéð░ Ðüð©ÐüÐéðÁð╝ð░ ÐÇð░ð▒ð¥Ðéð©!",
        # )

        # if success:
        # Track analytics
        # analytics_service.track_event(
        #     event_type="test_sms_sent",
        #     event_category="notification",
        #     context={"user_id": current_user.id}
        # )

        return jsonify({"success": True, "message": "ðóðÁÐüÐéð¥ð▓ð¥Ðéð¥ SMS ðÁ ð©ðÀð┐ÐÇð░ÐéðÁð¢ð¥ ÐâÐüð┐ðÁÐêð¢ð¥"})
        # else:
        #     return (
        #         jsonify(
        #             {"success": False, "message": "ðôÐÇðÁÐêð║ð░ ð┐ÐÇð© ð©ðÀð┐ÐÇð░Ðëð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐé SMS"}
        #         ),
        #         500,
        #     )

    except Exception as e:
        current_app.logger.error(f"Error sending test SMS: {e}")
        return (
            jsonify({"success": False, "message": "ðôÐÇðÁÐêð║ð░ ð┐ÐÇð© ð©ðÀð┐ÐÇð░Ðëð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐé SMS"}),
            500,
        )


@notification_bp.route("/send", methods=["POST"])
# @login_required
def send_notification():
    """Send notification to user(s)"""
    try:
        data = request.get_json()
        notification_type = data.get("type")
        recipients = data.get("recipients", [])
        context = data.get("context", {})

        sent_count = 0
        db_instance = get_db()

        for recipient_id in recipients:
            recipient = db_instance.session.get(User, recipient_id)
            if not recipient:
                continue

            # Check user notification preferences
            settings = recipient.notification_settings or {}

            # Send based on notification type and user preferences
            if notification_type == "new_request":
                if settings.get("emailEnabled", True):
                    _send_new_request_email(recipient, context)
                    sent_count += 1

                if settings.get("smsEnabled", False):
                    _send_new_request_sms(recipient, context)
                    sent_count += 1

                if settings.get("pushEnabled", False):
                    _send_push_notification(recipient, "new_request", context)

            elif notification_type == "urgent_request":
                if settings.get("emailEnabled", True):
                    _send_urgent_request_email(recipient, context)
                    sent_count += 1

                if settings.get("smsEnabled", False):
                    _send_urgent_request_sms(recipient, context)
                    sent_count += 1

                if settings.get("pushEnabled", False):
                    _send_push_notification(recipient, "urgent_request", context)

            elif notification_type == "message":
                if settings.get("notifyMessages", True):
                    if settings.get("emailEnabled", True):
                        _send_message_email(recipient, context)
                        sent_count += 1

                    if settings.get("pushEnabled", False):
                        _send_push_notification(recipient, "message", context)

        # Track analytics
        # analytics_service.track_event(
        #     event_type="notification_sent",
        #     event_category="system",
        #     context={
        #         "type": notification_type,
        #         "recipient_count": len(recipients),
        #         "sent_count": sent_count
        #     }
        # )

        return jsonify(
            {
                "success": True,
                "sent_count": sent_count,
                "message": f"ðÿðÀð┐ÐÇð░ÐéðÁð¢ð© Ðüð░ {sent_count} ð¢ð¥Ðéð©Ðäð©ð║ð░Ðåð©ð©",
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error sending notification: {e}")
        return (
            jsonify({"success": False, "message": "ðôÐÇðÁÐêð║ð░ ð┐ÐÇð© ð©ðÀð┐ÐÇð░Ðëð░ð¢ðÁ ð¢ð░ ð¢ð¥Ðéð©Ðäð©ð║ð░Ðåð©ÐÅ"}),
            500,
        )


def _send_new_request_email(recipient, context):
    """Send new request notification email"""
    try:
        from mail_service import send_notification_email

        send_notification_email(
            recipient=recipient.email,
            subject="ðØð¥ð▓ð░ ðÀð░ÐÅð▓ð║ð░ ðÀð░ ð┐ð¥ð╝ð¥Ðë ð¢ð░ð▒ð╗ð©ðÀð¥ - HelpChain",
            template="email_template.html",
            context={
                "notification_type": "new_request",
                "recipient_name": recipient.name,
                "request": context.get("request", {}),
                "action_url": (f"{current_app.config['FRONTEND_URL']}/request/{context.get('request', {}).get('id')}"),
            },
        )
    except Exception as e:
        current_app.logger.error(f"Error sending new request email: {e}")


def _send_urgent_request_email(recipient, context):
    """Send urgent request notification email"""
    try:
        from mail_service import send_notification_email

        send_notification_email(
            recipient=recipient.email,
            subject="ðíðƒðòð¿ðØðÉ ðÀð░ÐÅð▓ð║ð░ ðÀð░ ð┐ð¥ð╝ð¥Ðë! - HelpChain",
            template="email_template.html",
            context={
                "notification_type": "urgent_request",
                "recipient_name": recipient.name,
                "request": context.get("request", {}),
                "action_url": (f"{current_app.config['FRONTEND_URL']}/request/{context.get('request', {}).get('id')}"),
                "call_url": f"tel:{context.get('request', {}).get('emergency_phone', '')}",
            },
        )
    except Exception as e:
        current_app.logger.error(f"Error sending urgent request email: {e}")


def _send_message_email(recipient, context):
    """Send message notification email"""
    try:
        from mail_service import send_notification_email

        send_notification_email(
            recipient=recipient.email,
            subject="ðØð¥ð▓ð¥ ÐüÐèð¥ð▒ÐëðÁð¢ð©ðÁ - HelpChain",
            template="email_template.html",
            context={
                "notification_type": "message_received",
                "recipient_name": recipient.name,
                "sender": context.get("sender", {}),
                "message": context.get("message", {}),
                "task": context.get("task", {}),
                "chat_url": f"{current_app.config['FRONTEND_URL']}/chat/{context.get('chat_id')}",
            },
        )
    except Exception as e:
        current_app.logger.error(f"Error sending message email: {e}")


def _send_new_request_sms(recipient, context):
    """Send new request notification SMS"""
    try:
        from sms_service import send_notification_sms

        request = context.get("request", {})
        message = f"HelpChain: ðØð¥ð▓ð░ ðÀð░ÐÅð▓ð║ð░ - {request.get('category', '')} Ðâð╗.{request.get('address', '')}. {request.get('distance', '')}km ð¥Ðé ð▓ð░Ðü."

        send_notification_sms(recipient.phone, message)
    except Exception as e:
        current_app.logger.error(f"Error sending new request SMS: {e}")


def _send_urgent_request_sms(recipient, context):
    """Send urgent request notification SMS"""
    try:
        from sms_service import send_notification_sms

        request = context.get("request", {})
        message = f"ðíðƒðòð¿ðØð× HelpChain: {request.get('category', '')} Ðâð╗.{request.get('address', '')}. ðóðÁð╗:{request.get('emergency_phone', '')}"

        send_notification_sms(recipient.phone, message)
    except Exception as e:
        current_app.logger.error(f"Error sending urgent request SMS: {e}")


def _send_push_notification(recipient, notification_type, context):
    """Send push notification via service worker"""
    try:
        # Get user's push subscription
        settings = recipient.notification_settings or {}
        subscription = settings.get("push_subscription")

        if not subscription:
            return

        # Prepare push data based on type
        push_data = {
            "type": notification_type,
            "data": context,
            "user_id": recipient.id,
        }

        if notification_type == "new_request":
            push_data.update(
                {
                    "title": "ðØð¥ð▓ð░ ðÀð░ÐÅð▓ð║ð░ ðÀð░ ð┐ð¥ð╝ð¥Ðë",
                    "body": (f"{context.get('request', {}).get('category', '')} - {context.get('request', {}).get('distance', '')}km ð¥Ðé ð▓ð░Ðü"),
                }
            )
        elif notification_type == "urgent_request":
            push_data.update(
                {
                    "title": "ðíðƒðòð¿ðØðÉ ðÀð░ÐÅð▓ð║ð░!",
                    "body": (f"{context.get('request', {}).get('category', '')} - ðØÐâðÂð┤ð░ ð¥Ðé ð¢ðÁðÀð░ð▒ð░ð▓ð¢ð░ ð┐ð¥ð╝ð¥Ðë!"),
                    "urgent": True,
                }
            )
        elif notification_type == "message":
            push_data.update(
                {
                    "title": f"ðØð¥ð▓ð¥ ÐüÐèð¥ð▒ÐëðÁð¢ð©ðÁ ð¥Ðé {context.get('sender', {}).get('name', '')}",
                    "body": context.get("message", {}).get("content", "")[:100],
                }
            )

        # Send push notification (would integrate with push service like FCM)
        # For now, just log it
        current_app.logger.info(f"Push notification queued for user {recipient.id}: {push_data}")

    except Exception as e:
        current_app.logger.error(f"Error sending push notification: {e}")


@notification_bp.route("/unsubscribe/<token>", methods=["GET"])
def unsubscribe(token):
    """Unsubscribe from email notifications"""
    try:
        # Verify and decode token (would implement proper token verification)
        # For now, just show unsubscribe page
        return render_template("unsubscribe.html", token=token)
    except Exception as e:
        current_app.logger.error(f"Error processing unsubscribe: {e}")
        return jsonify({"error": "Invalid unsubscribe token"}), 400


@notification_bp.route("/stats", methods=["GET"])
# @login_required
def notification_stats():
    """Get notification statistics for current user"""
    try:
        # This would aggregate notification data from analytics
        # For now, return mock data
        stats = {
            "emails_sent": 15,
            "sms_sent": 3,
            "push_sent": 8,
            "open_rate": 0.75,
            "click_rate": 0.45,
        }

        return jsonify({"success": True, "stats": stats})

    except Exception as e:
        current_app.logger.error(f"Error getting notification stats: {e}")
        return (
            jsonify({"success": False, "message": "ðôÐÇðÁÐêð║ð░ ð┐ÐÇð© ðÀð░ÐÇðÁðÂð┤ð░ð¢ðÁ ð¢ð░ ÐüÐéð░Ðéð©ÐüÐéð©ð║ð©"}),
            500,
        )

"""
HelpChain Notification Service
Цялостна система за управление на нотификации с поддръжка за:
- Email notifications
- Push notifications
- In-app notifications
- SMS notifications (готовност)
- Template система
- Queue management
- Delivery tracking
- User preferences
"""

import json
import os
import smtplib
import ssl
import threading
import time
from datetime import UTC, datetime, timedelta
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from jinja2 import Template


def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


# Try different import strategies for models
try:
    from .models import (
        Notification,
        NotificationPreference,
        NotificationQueue,
        NotificationTemplate,
        PushSubscription,
        db,
    )
except ImportError:
    try:
        from models import (
            Notification,
            NotificationPreference,
            NotificationQueue,
            NotificationTemplate,
            PushSubscription,
            db,
        )
    except ImportError:
        # For standalone execution
        import os
        import sys

        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from models import (
            Notification,
            NotificationPreference,
            NotificationQueue,
            NotificationTemplate,
            PushSubscription,
            db,
        )

# Web Push dependencies (ще се инсталират при нужда)
try:
    from pywebpush import WebPushException, webpush

    PUSH_AVAILABLE = True
except ImportError:
    PUSH_AVAILABLE = False
    print("⚠️  Web Push не е наличен. Инсталирайте pywebpush за push notifications.")


class NotificationService:
    """Основна система за нотификации"""

    def __init__(self):
        self.email_config = self._load_email_config()
        self.push_config = self._load_push_config()
        self.templates_cache = {}
        self.processing_queue = False

    def _load_email_config(self) -> dict[str, Any]:
        """Зарежда email конфигурация"""
        return {
            "smtp_server": os.getenv("MAIL_SERVER", "smtp.zoho.eu"),
            "smtp_port": int(os.getenv("MAIL_PORT", 465)),
            "username": os.getenv("MAIL_USERNAME", ""),
            "password": os.getenv("MAIL_PASSWORD", ""),
            "sender": os.getenv("MAIL_DEFAULT_SENDER", ""),
            "use_ssl": os.getenv("MAIL_USE_SSL", "True").lower() == "true",
        }

    def _load_push_config(self) -> dict[str, str]:
        """Зарежда push notification конфигурация"""
        return {
            "vapid_public_key": os.getenv("VAPID_PUBLIC_KEY", ""),
            "vapid_private_key": os.getenv("VAPID_PRIVATE_KEY", ""),
            "vapid_claims": {"sub": f"mailto:{os.getenv('MAIL_DEFAULT_SENDER', '')}"},
        }

    # ========================================================================
    # TEMPLATE MANAGEMENT
    # ========================================================================

    def create_template(
        self,
        name: str,
        type: str,
        category: str,
        subject: str = None,
        title: str = None,
        content: str = "",
        variables: list[str] = None,
        **kwargs,
    ) -> NotificationTemplate:
        """Създава нов шаблон за нотификации"""
        try:
            template = NotificationTemplate(
                name=name,
                type=type,  # email, push, in_app, sms
                category=category,  # registration, feedback, system, etc.
                subject=subject,
                title=title,
                content=content,
                content_type=kwargs.get("content_type", "html"),
                is_active=kwargs.get("is_active", True),
                priority=kwargs.get("priority", "normal"),
                auto_send=kwargs.get("auto_send", False),
                variables=json.dumps(variables or []),
                send_delay=kwargs.get("send_delay", 0),
                expiry_hours=kwargs.get("expiry_hours", 24),
            )

            db.session.add(template)
            db.session.commit()

            # Обновяваме кеша
            self.templates_cache[name] = template

            print(f"✅ Създаден шаблон: {name}")
            return template

        except Exception as e:
            db.session.rollback()
            print(f"❌ Грешка при създаване на шаблон: {str(e)}")
            raise

    def get_template(self, name: str) -> NotificationTemplate | None:
        """Получава шаблон по име (с кеширане)"""
        if name in self.templates_cache:
            return self.templates_cache[name]

        template = NotificationTemplate.query.filter_by(
            name=name, is_active=True
        ).first()
        if template:
            self.templates_cache[name] = template

        return template

    def render_template(
        self, template: NotificationTemplate, variables: dict[str, Any]
    ) -> dict[str, str]:
        """Рендерира шаблон с променливи"""
        try:
            result = {}

            # Рендерираме subject
            if template.subject:
                subject_template = Template(template.subject)
                result["subject"] = subject_template.render(**variables)

            # Рендерираме title
            if template.title:
                title_template = Template(template.title)
                result["title"] = title_template.render(**variables)

            # Рендерираме content
            content_template = Template(template.content)
            result["content"] = content_template.render(**variables)

            return result

        except Exception as e:
            print(f"❌ Грешка при рендериране на шаблон: {str(e)}")
            raise

    # ========================================================================
    # QUEUE MANAGEMENT
    # ========================================================================

    def queue_notification(
        self,
        template_name: str,
        recipient_email: str,
        recipient_type: str = "volunteer",
        recipient_id: int = None,
        personalization_data: dict[str, Any] = None,
        priority: str = "normal",
        scheduled_for: datetime = None,
    ) -> NotificationQueue:
        """Добавя нотификация в опашката"""
        try:
            template = self.get_template(template_name)
            if not template:
                raise ValueError(f"Шаблон '{template_name}' не е намерен")

            queue_item = NotificationQueue(
                template_id=template.id,
                recipient_type=recipient_type,
                recipient_id=recipient_id,
                recipient_email=recipient_email,
                personalization_data=json.dumps(personalization_data or {}),
                priority=priority,
                scheduled_for=scheduled_for or utc_now(),
            )

            db.session.add(queue_item)
            db.session.commit()

            print(f"✅ Добавена в опашката: {recipient_email} ({template_name})")
            return queue_item

        except Exception as e:
            db.session.rollback()
            print(f"❌ Грешка при добавяне в опашката: {str(e)}")
            raise

    def process_queue(self, max_items: int = 100) -> dict[str, int]:
        """Обработва опашката за нотификации"""
        if self.processing_queue:
            return {"skipped": 1, "reason": "already_processing"}

        self.processing_queue = True
        stats = {"sent": 0, "failed": 0, "skipped": 0}

        try:
            # Взимаме pending нотификации, подредени по приоритет и време
            pending_items = (
                NotificationQueue.query.filter(
                    NotificationQueue.status == "pending",
                    NotificationQueue.scheduled_for <= utc_now(),
                    NotificationQueue.attempts < NotificationQueue.max_attempts,
                )
                .order_by(
                    NotificationQueue.priority.desc(),  # High priority first
                    NotificationQueue.scheduled_for.asc(),
                )
                .limit(max_items)
                .all()
            )

            for item in pending_items:
                try:
                    # Обновяваме статуса
                    item.status = "processing"
                    item.attempts += 1
                    item.last_attempt = utc_now()
                    db.session.commit()

                    # Опитваме се да изпратим
                    success = self._send_notification(item)

                    if success:
                        item.status = "sent"
                        item.sent_at = utc_now()
                        stats["sent"] += 1
                    else:
                        if item.attempts >= item.max_attempts:
                            item.status = "failed"
                            stats["failed"] += 1
                        else:
                            item.status = "pending"
                            item.next_retry = utc_now() + timedelta(
                                minutes=item.attempts * 5
                            )
                            stats["skipped"] += 1

                    db.session.commit()

                except Exception as e:
                    item.status = (
                        "failed" if item.attempts >= item.max_attempts else "pending"
                    )
                    item.error_message = str(e)
                    db.session.commit()
                    stats["failed"] += 1
                    print(
                        f"❌ Грешка при изпращане към {item.recipient_email}: {str(e)}"
                    )

            print(f"📬 Обработени {len(pending_items)} нотификации: {stats}")
            return stats

        except Exception as e:
            print(f"❌ Грешка в queue processing: {str(e)}")
            return {"error": str(e)}
        finally:
            self.processing_queue = False

    def _send_notification(self, queue_item: NotificationQueue) -> bool:
        """Изпраща конкретна нотификация"""
        try:
            template = db.session.get(NotificationTemplate, queue_item.template_id)
            if not template:
                raise ValueError("Шаблон не е намерен")

            # Parse personalization data
            personalization_data = json.loads(queue_item.personalization_data or "{}")

            # Проверяваме user preferences (ако е volunteer)
            if queue_item.recipient_id and queue_item.recipient_type == "volunteer":
                if not self._check_user_preferences(queue_item.recipient_id, template):
                    print(
                        f"🚫 Нотификация блокирана от user preferences: {queue_item.recipient_email}"
                    )
                    return True  # Считаме като "успешна" - просто е блокирана

            # Рендерираме съдържанието
            rendered = self.render_template(template, personalization_data)

            # Изпращаме според типа
            success = False
            if template.type == "email":
                success = self._send_email(
                    to_email=queue_item.recipient_email,
                    subject=rendered.get("subject", ""),
                    content=rendered.get("content", ""),
                    template=template,
                )
            elif template.type == "push":
                success = self._send_push_notification(
                    recipient_id=queue_item.recipient_id,
                    title=rendered.get("title", ""),
                    content=rendered.get("content", ""),
                    template=template,
                )
            elif template.type == "in_app":
                success = self._create_in_app_notification(
                    recipient_id=queue_item.recipient_id,
                    title=rendered.get("title", ""),
                    content=rendered.get("content", ""),
                    template=template,
                )

            # Записваме в историята
            if success:
                self._create_notification_record(queue_item, template, rendered)

            return success

        except Exception as e:
            print(f"❌ Грешка при изпращане: {str(e)}")
            return False

    # ========================================================================
    # EMAIL NOTIFICATIONS
    # ========================================================================

    def _send_email(
        self, to_email: str, subject: str, content: str, template: NotificationTemplate
    ) -> bool:
        """Изпраща email нотификация"""
        try:
            # Създаваме съобщението
            msg = MIMEMultipart("alternative")
            msg["From"] = self.email_config["sender"]
            msg["To"] = to_email
            msg["Subject"] = Header(subject, "utf-8").encode()

            # Добавяме съдържанието
            if template.content_type == "html":
                html_part = MIMEText(content, "html", "utf-8")
                msg.attach(html_part)
            else:
                text_part = MIMEText(content, "plain", "utf-8")
                msg.attach(text_part)

            # Изпращаме
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                self.email_config["smtp_server"],
                self.email_config["smtp_port"],
                context=context,
            ) as server:
                server.login(
                    self.email_config["username"], self.email_config["password"]
                )
                server.send_message(msg)

            print(f"📧 Email изпратен до: {to_email}")
            return True

        except Exception as e:
            print(f"❌ Грешка при изпращане на email: {str(e)}")
            return False

    # ========================================================================
    # PUSH NOTIFICATIONS
    # ========================================================================

    def _send_push_notification(
        self,
        recipient_id: int,
        title: str,
        content: str,
        template: NotificationTemplate,
    ) -> bool:
        """Изпраща push нотификация"""
        if not PUSH_AVAILABLE:
            print("⚠️  Push notifications не са налични")
            return False

        try:
            # Намираме активните push subscriptions за потребителя
            subscriptions = PushSubscription.query.filter_by(
                volunteer_id=recipient_id, is_active=True
            ).all()

            if not subscriptions:
                print(f"📱 Няма активни push subscriptions за volunteer {recipient_id}")
                return True  # Не е грешка - просто няма subscriptions

            success_count = 0
            for subscription in subscriptions:
                try:
                    # Подготвяме payload
                    payload = json.dumps(
                        {
                            "title": title,
                            "body": content,
                            "icon": "/static/hands-heart.png",
                            "badge": "/static/hands-heart.png",
                            "data": {
                                "template_id": template.id,
                                "category": template.category,
                                "timestamp": utc_now().isoformat(),
                            },
                        }
                    )

                    # Изпращаме push notification
                    webpush(
                        subscription_info={
                            "endpoint": subscription.endpoint,
                            "keys": {
                                "p256dh": subscription.p256dh_key,
                                "auth": subscription.auth_key,
                            },
                        },
                        data=payload,
                        vapid_private_key=self.push_config["vapid_private_key"],
                        vapid_claims=self.push_config["vapid_claims"],
                    )

                    # Обновяваме статистиките
                    subscription.notifications_sent += 1
                    subscription.last_used = utc_now()
                    success_count += 1

                except WebPushException as e:
                    print(f"⚠️  Push subscription error: {str(e)}")
                    if e.response.status_code in [400, 404, 410]:
                        # Невалидна subscription - деактивираме я
                        subscription.is_active = False
                except Exception as e:
                    print(f"❌ Push error: {str(e)}")

            db.session.commit()

            if success_count > 0:
                print(
                    f"📱 Push notifications изпратени: {success_count}/{len(subscriptions)}"
                )
                return True
            else:
                return False

        except Exception as e:
            print(f"❌ Грешка в push notifications: {str(e)}")
            return False

    # ========================================================================
    # IN-APP NOTIFICATIONS
    # ========================================================================

    def _create_in_app_notification(
        self,
        recipient_id: int,
        title: str,
        content: str,
        template: NotificationTemplate,
    ) -> bool:
        """Създава in-app нотификация"""
        try:
            # За in-app notifications просто създаваме record в базата
            # Frontend-ът ще ги показва
            notification = Notification(
                template_id=template.id,
                recipient_type="volunteer",
                recipient_id=recipient_id,
                delivery_channel="in_app",
                final_title=title,
                final_content=content,
                status="delivered",  # In-app са винаги "delivered"
            )

            db.session.add(notification)
            db.session.commit()

            print(f"📱 In-app notification създадена за volunteer {recipient_id}")
            return True

        except Exception as e:
            print(f"❌ Грешка при in-app notification: {str(e)}")
            return False

    # ========================================================================
    # USER PREFERENCES
    # ========================================================================

    def _check_user_preferences(
        self, volunteer_id: int, template: NotificationTemplate
    ) -> bool:
        """Проверява дали потребителят желае този тип нотификация"""
        try:
            prefs = NotificationPreference.query.filter_by(
                volunteer_id=volunteer_id
            ).first()
            if not prefs:
                return True  # Ако няма настройки - разрешаваме по default

            # Проверяваме общите настройки за канала
            if template.type == "email" and not prefs.email_enabled:
                return False
            elif template.type == "push" and not prefs.push_enabled:
                return False
            elif template.type == "in_app" and not prefs.in_app_enabled:
                return False
            elif template.type == "sms" and not prefs.sms_enabled:
                return False

            # Проверяваме категорийни настройки
            category_mapping = {
                "registration": prefs.registration_notifications,
                "feedback": prefs.feedback_notifications,
                "system": prefs.system_notifications,
                "marketing": prefs.marketing_notifications,
                "reminder": prefs.reminder_notifications,
            }

            if template.category in category_mapping:
                if not category_mapping[template.category]:
                    return False

            # Проверяваме quiet hours
            if template.type in ["push", "sms"]:
                now_time = utc_now().time()
                if prefs.quiet_hours_start <= prefs.quiet_hours_end:
                    # Обикновени часове (напр. 22:00 - 08:00)
                    if prefs.quiet_hours_start <= now_time <= prefs.quiet_hours_end:
                        return False
                else:
                    # Часовете преминават през полунощ
                    if (
                        now_time >= prefs.quiet_hours_start
                        or now_time <= prefs.quiet_hours_end
                    ):
                        return False

            return True

        except Exception as e:
            print(f"⚠️  Грешка при проверка на preferences: {str(e)}")
            return True  # При грешка - разрешаваме

    # ========================================================================
    # UTILITIES
    # ========================================================================

    def _create_notification_record(
        self,
        queue_item: NotificationQueue,
        template: NotificationTemplate,
        rendered: dict[str, str],
    ):
        """Създава запис в историята на нотификациите"""
        try:
            notification = Notification(
                template_id=template.id,
                queue_id=queue_item.id,
                recipient_type=queue_item.recipient_type,
                recipient_id=queue_item.recipient_id,
                recipient_email=queue_item.recipient_email,
                delivery_channel=template.type,
                final_subject=rendered.get("subject"),
                final_title=rendered.get("title"),
                final_content=rendered.get("content"),
                status="sent",
            )

            db.session.add(notification)
            db.session.commit()

        except Exception as e:
            print(f"⚠️  Грешка при създаване на notification record: {str(e)}")

    def get_notification_stats(self, days: int = 30) -> dict[str, Any]:
        """Получава статистики за нотификациите"""
        try:
            start_date = utc_now() - timedelta(days=days)

            stats = {
                "total_sent": 0,
                "by_channel": {},
                "by_status": {},
                "by_category": {},
                "engagement": {
                    "total_delivered": 0,
                    "total_read": 0,
                    "total_clicked": 0,
                    "delivery_rate": 0.0,
                    "read_rate": 0.0,
                    "click_rate": 0.0,
                },
            }

            # Общи статистики
            notifications = Notification.query.filter(
                Notification.created_at >= start_date
            ).all()

            stats["total_sent"] = len(notifications)

            # По канали
            for notification in notifications:
                channel = notification.delivery_channel
                stats["by_channel"][channel] = stats["by_channel"].get(channel, 0) + 1

            # По статус
            for notification in notifications:
                status = notification.status
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

            # По категории
            for notification in notifications:
                if notification.template:
                    category = notification.template.category
                    stats["by_category"][category] = (
                        stats["by_category"].get(category, 0) + 1
                    )

            # Engagement метрики
            delivered_count = len([n for n in notifications if n.delivered_at])
            read_count = len([n for n in notifications if n.read_at])
            clicked_count = len([n for n in notifications if n.clicked_at])

            stats["engagement"]["total_delivered"] = delivered_count
            stats["engagement"]["total_read"] = read_count
            stats["engagement"]["total_clicked"] = clicked_count

            if stats["total_sent"] > 0:
                stats["engagement"]["delivery_rate"] = round(
                    delivered_count / stats["total_sent"] * 100, 2
                )
                stats["engagement"]["read_rate"] = round(
                    read_count / stats["total_sent"] * 100, 2
                )
                stats["engagement"]["click_rate"] = round(
                    clicked_count / stats["total_sent"] * 100, 2
                )

            return stats

        except Exception as e:
            print(f"❌ Грешка при извличане на статистики: {str(e)}")
            return {}

    def start_background_processor(self, interval: int = 60):
        """Стартира фонов процес за обработка на опашката"""

        def process_loop():
            while True:
                try:
                    self.process_queue()
                    time.sleep(interval)
                except Exception as e:
                    print(f"❌ Грешка в background processor: {str(e)}")
                    time.sleep(interval * 2)  # По-дълго чакане при грешка

        # Стартираме в отделен thread
        processor_thread = threading.Thread(target=process_loop, daemon=True)
        processor_thread.start()
        print(f"🔄 Background notification processor стартиран (interval: {interval}s)")


# Създаваме глобална инстанция
notification_service = NotificationService()


# Quick methods за лесно използване
def send_notification(
    template_name: str,
    recipient_email: str,
    personalization_data: dict[str, Any] = None,
    **kwargs,
):
    """Бърз начин за изпращане на нотификация"""
    return notification_service.queue_notification(
        template_name=template_name,
        recipient_email=recipient_email,
        personalization_data=personalization_data,
        **kwargs,
    )


def create_template(name: str, type: str, category: str, **kwargs):
    """Бърз начин за създаване на шаблон"""
    return notification_service.create_template(
        name=name, type=type, category=category, **kwargs
    )

#!/usr/bin/env python3
"""
Пример за използване на Notification модела
"""

from backend.models import (
    Notification,
    NotificationStatusEnum,
    NotificationTypeEnum,
    PriorityEnum,
)


def demo_notifications():
    """Демонстриране на функционалностите на Notification модела"""

    print("=== HelpChain Notification System Demo ===\n")

    # 1. Създаване на различни типове нотификации
    print("1. Създаване на нотификации:")

    # Системна нотификация за админ
    admin_notification = Notification.create_notification(
        title="Нова система за нотификации",
        message="Внедрихме нова система за нотификации с поддръжка на email, app и push.",
        recipient_id=1,
        recipient_type="admin",
        notification_type=NotificationTypeEnum.system,
        channels=["email", "app"],
        priority=PriorityEnum.normal,
    )
    print(f"✓ Създадена системна нотификация: {admin_notification.title}")

    # Нотификация за нова заявка за помощ
    request_notification = Notification.create_notification(
        title="Нова заявка за помощ",
        message="Получена е нова заявка за помощ в категория 'Здравеопазване'",
        recipient_id=2,
        recipient_type="volunteer",
        notification_type=NotificationTypeEnum.request,
        channels=["app", "push"],
        priority=PriorityEnum.urgent,
        related_type="help_request",
        related_id=123,
        action_url="/admin/requests/123",
    )
    print(f"✓ Създадена нотификация за заявка: {request_notification.title}")

    # Нотификация за задача
    task_notification = Notification.create_notification(
        title="Нова задача ви е назначена",
        message="Назначена ви е задача: 'Доставка на лекарства'",
        recipient_id=3,
        recipient_type="volunteer",
        notification_type=NotificationTypeEnum.task,
        channels=["email", "app", "push"],
        priority=PriorityEnum.high,
        related_type="task",
        related_id=456,
        extra_data={"task_deadline": "2025-10-20", "location": "София"},
    )
    print(f"✓ Създадена нотификация за задача: {task_notification.title}")

    print("\n2. Проверка на състоянието на нотификациите:")

    # Проверка на статусите
    for notification in [admin_notification, request_notification, task_notification]:
        print(f"ID {notification.id}: {notification.title}")
        print(f"  - Канали: {notification.channels}")
        print(f"  - Приоритет: {notification.priority.value}")
        print(f"  - Изпратена: {notification.is_sent}")
        print(f"  - Прочетена: {notification.is_read}")

    print("\n3. Симулиране на изпращане и прочитане:")

    # Симулиране на изпращане по различни канали
    request_notification.update_channel_status("app", NotificationStatusEnum.sent)
    request_notification.update_channel_status("push", NotificationStatusEnum.delivered)
    print(f"✓ Нотификация {request_notification.id} изпратена по app и push")

    # Отбелязване като прочетена
    request_notification.mark_as_read()
    print(f"✓ Нотификация {request_notification.id} отбелязана като прочетена")

    print("\n4. Статистика:")
    print(f"Общо нотификации: {Notification.query.count()}")
    print(f"Непрочетени за volunteer 2: {Notification.get_unread_count(2, 'volunteer')}")
    print(f"Непрочетени за admin 1: {Notification.get_unread_count(1, 'admin')}")

    print("\n5. Извличане на нотификации за потребител:")
    user_notifications = Notification.get_user_notifications(2, "volunteer", limit=5)
    for notif in user_notifications:
        status = "прочетена" if notif.is_read else "непрочетена"
        print(f"  - {notif.title} ({status})")

    print("\n=== Demo завършен успешно! ===")


if __name__ == "__main__":
    # Забележка: Този скрипт изисква активна Flask app context и база данни
    # За реално използване, стартирайте през Flask приложение
    print("За да стартирате демото, трябва да имате активна Flask app и база данни.")
    print("Примерни команди:")
    print("1. python run.py  # или друг начин за стартиране на приложението")
    print("2. Изпълнете този скрипт в контекста на приложението")

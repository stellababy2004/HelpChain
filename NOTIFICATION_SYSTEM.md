# HelpChain Notification System

## Обзор

Системата за нотификации в HelpChain поддържа три типа канали за комуникация:

- **Email** - Имейл нотификации
- **App** - In-app нотификации в уеб приложението
- **Push** - Push нотификации (за бъдеща имплементация с PWA/Service Workers)

## Модел Notification

### Основни полета

- `title` - Заглавие на нотификацията
- `message` - Съдържание на нотификацията
- `notification_type` - Тип на нотификацията (system, request, task, message, achievement, reminder, alert)
- `recipient_id` - ID на получателя
- `recipient_type` - Тип на получателя (user, admin, volunteer)
- `channels` - JSON масив с канали за изпращане ["email", "app", "push"]
- `priority` - Приоритет (low, normal, urgent)

### Статус полета

- `email_status` - Статус на имейл нотификацията
- `app_status` - Статус на app нотификацията
- `push_status` - Статус на push нотификацията
- `is_read` - Дали е прочетена
- `read_at` - Кога е прочетена

### Свързани обекти

- `related_type` - Тип на свързания обект (help_request, task, etc.)
- `related_id` - ID на свързания обект
- `action_url` - URL за действие при кликване
- `extra_data` - Допълнителни данни в JSON формат

## Използване

### Създаване на нотификация

```python
from backend.models import Notification, NotificationTypeEnum, PriorityEnum

# Създаване на нотификация за нова заявка
notification = Notification.create_notification(
    title="Нова заявка за помощ",
    message="Получена е нова заявка в категория 'Здравеопазване'",
    recipient_id=1,
    recipient_type="volunteer",
    notification_type=NotificationTypeEnum.request,
    channels=["email", "app", "push"],
    priority=PriorityEnum.urgent,
    related_type="help_request",
    related_id=123,
    action_url="/volunteer/requests/123"
)
```

### Проверка на статус

```python
# Проверка дали е изпратена
if notification.is_sent:
    print("Нотификацията е изпратена")

# Проверка дали е доставена
if notification.is_delivered:
    print("Нотификацията е доставена")

# Отбелязване като прочетена
notification.mark_as_read()
```

### Обновяване на статус по канал

```python
# Имейлът е изпратен успешно
notification.update_channel_status("email", NotificationStatusEnum.sent)

# Push нотификацията е доставена
notification.update_channel_status("push", NotificationStatusEnum.delivered)
```

### Извличане на нотификации

```python
# Брой непрочетени нотификации
unread_count = Notification.get_unread_count(user_id, "volunteer")

# Извличане на нотификациите за потребител
notifications = Notification.get_user_notifications(user_id, "volunteer", limit=20)

# Отбелязване на всички като прочетени
Notification.mark_all_as_read(user_id, "volunteer")
```

## Типове нотификации

- `system` - Системни съобщения и обновления
- `request` - Нови заявки за помощ
- `task` - Задачи и assignments
- `message` - Чат съобщения
- `achievement` - Постижения и badges
- `reminder` - Напомняния
- `alert` - Важни предупреждения

## Приоритети

- `low` - Нисък приоритет
- `normal` - Нормален приоритет
- `urgent` - Спешни нотификации

## Статуси

- `pending` - Очаква изпращане
- `sent` - Изпратена успешно
- `delivered` - Доставена до получателя
- `read` - Прочетена от потребителя
- `failed` - Неуспешно изпращане
- `cancelled` - Отменена

## Интеграция с други системи

### Email интеграция

Нотификациите с канал "email" могат да се интегрират с Flask-Mail за изпращане на имейли.

### Push нотификации

За push нотификации може да се използва Firebase Cloud Messaging или подобна услуга.

### In-app нотификации

App нотификациите се показват в уеб интерфейса и се съхраняват в базата данни.

## Бъдещи разширения

- Планирани нотификации (scheduled_at)
- Групови нотификации
- Темплейти за нотификации
- Настройки за предпочитания на потребителите
- Архив и история на нотификациите

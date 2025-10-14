"""
HelpChain Multilingual Database Initialization
Инициализира базата данни с основни езици и начални преводи
"""

from datetime import datetime
from .models import (
    db,
    SupportedLanguage,
    TranslationKey,
    Translation,
)


def initialize_supported_languages():
    """Инициализира основните поддържани езици"""

    languages_data = [
        {
            "code": "bg",
            "name": "Bulgarian",
            "native_name": "Български",
            "is_default": True,
            "is_active": True,
            "is_rtl": False,
            "flag_emoji": "🇧🇬",
            "currency_code": "BGN",
            "date_format": "%d.%m.%Y",
            "time_format": "%H:%M",
            "translation_quality": "native",
        },
        {
            "code": "en",
            "name": "English",
            "native_name": "English",
            "is_default": False,
            "is_active": True,
            "is_rtl": False,
            "flag_emoji": "🇺🇸",
            "currency_code": "USD",
            "date_format": "%m/%d/%Y",
            "time_format": "%I:%M %p",
            "translation_quality": "professional",
        },
        {
            "code": "de",
            "name": "German",
            "native_name": "Deutsch",
            "is_default": False,
            "is_active": True,
            "is_rtl": False,
            "flag_emoji": "🇩🇪",
            "currency_code": "EUR",
            "date_format": "%d.%m.%Y",
            "time_format": "%H:%M",
            "translation_quality": "ai",
        },
        {
            "code": "fr",
            "name": "French",
            "native_name": "Français",
            "is_default": False,
            "is_active": True,
            "is_rtl": False,
            "flag_emoji": "🇫🇷",
            "currency_code": "EUR",
            "date_format": "%d/%m/%Y",
            "time_format": "%H:%M",
            "translation_quality": "ai",
        },
        {
            "code": "es",
            "name": "Spanish",
            "native_name": "Español",
            "is_default": False,
            "is_active": True,
            "is_rtl": False,
            "flag_emoji": "🇪🇸",
            "currency_code": "EUR",
            "date_format": "%d/%m/%Y",
            "time_format": "%H:%M",
            "translation_quality": "ai",
        },
        {
            "code": "ru",
            "name": "Russian",
            "native_name": "Русский",
            "is_default": False,
            "is_active": True,
            "is_rtl": False,
            "flag_emoji": "🇷🇺",
            "currency_code": "RUB",
            "date_format": "%d.%m.%Y",
            "time_format": "%H:%M",
            "translation_quality": "ai",
        },
    ]

    print("🌐 Initializing supported languages...")

    for lang_data in languages_data:
        existing_lang = SupportedLanguage.query.filter_by(
            code=lang_data["code"]
        ).first()

        if not existing_lang:
            language = SupportedLanguage(**lang_data)
            db.session.add(language)
            print(f"   ✅ Added {lang_data['native_name']} ({lang_data['code']})")
        else:
            print(f"   ⏭️  Skipped {lang_data['native_name']} (already exists)")

    try:
        db.session.commit()
        print("✅ Languages initialized successfully")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error initializing languages: {str(e)}")
        return False


def initialize_base_translation_keys():
    """Инициализира основните ключове за превод"""

    base_keys = [
        # Navigation
        {
            "key": "nav.home",
            "source_text": "Начало",
            "category": "navigation",
            "description": "Home page navigation link",
        },
        {
            "key": "nav.volunteers",
            "source_text": "Доброволци",
            "category": "navigation",
            "description": "Volunteers page navigation link",
        },
        {
            "key": "nav.about",
            "source_text": "За нас",
            "category": "navigation",
            "description": "About page navigation link",
        },
        {
            "key": "nav.contact",
            "source_text": "Контакт",
            "category": "navigation",
            "description": "Contact page navigation link",
        },
        {
            "key": "nav.admin",
            "source_text": "Администрация",
            "category": "navigation",
            "description": "Admin panel navigation link",
        },
        # Common UI Elements
        {
            "key": "common.save",
            "source_text": "Запази",
            "category": "ui",
            "description": "Save button text",
        },
        {
            "key": "common.cancel",
            "source_text": "Отказ",
            "category": "ui",
            "description": "Cancel button text",
        },
        {
            "key": "common.delete",
            "source_text": "Изтрий",
            "category": "ui",
            "description": "Delete button text",
        },
        {
            "key": "common.edit",
            "source_text": "Редактирай",
            "category": "ui",
            "description": "Edit button text",
        },
        {
            "key": "common.view",
            "source_text": "Преглед",
            "category": "ui",
            "description": "View button text",
        },
        {
            "key": "common.search",
            "source_text": "Търсене",
            "category": "ui",
            "description": "Search button text",
        },
        {
            "key": "common.loading",
            "source_text": "Зареждане...",
            "category": "ui",
            "description": "Loading indicator text",
        },
        {
            "key": "common.error",
            "source_text": "Грешка",
            "category": "ui",
            "description": "Generic error message",
        },
        {
            "key": "common.success",
            "source_text": "Успешно",
            "category": "ui",
            "description": "Generic success message",
        },
        {
            "key": "common.warning",
            "source_text": "Внимание",
            "category": "ui",
            "description": "Generic warning message",
        },
        # Forms
        {
            "key": "form.name",
            "source_text": "Име",
            "category": "form",
            "description": "Name field label",
        },
        {
            "key": "form.email",
            "source_text": "Email",
            "category": "form",
            "description": "Email field label",
        },
        {
            "key": "form.phone",
            "source_text": "Телефон",
            "category": "form",
            "description": "Phone field label",
        },
        {
            "key": "form.message",
            "source_text": "Съобщение",
            "category": "form",
            "description": "Message field label",
        },
        {
            "key": "form.submit",
            "source_text": "Изпрати",
            "category": "form",
            "description": "Submit button text",
        },
        {
            "key": "form.required",
            "source_text": "Задължително поле",
            "category": "form",
            "description": "Required field validation message",
        },
        {
            "key": "form.invalid_email",
            "source_text": "Невалиден email адрес",
            "category": "form",
            "description": "Invalid email validation message",
        },
        {
            "key": "form.invalid_phone",
            "source_text": "Невалиден телефонен номер",
            "category": "form",
            "description": "Invalid phone validation message",
        },
        # Volunteer Management
        {
            "key": "volunteer.title",
            "source_text": "Доброволци",
            "category": "volunteer",
            "description": "Volunteers page title",
        },
        {
            "key": "volunteer.add",
            "source_text": "Добави доброволец",
            "category": "volunteer",
            "description": "Add volunteer button",
        },
        {
            "key": "volunteer.edit",
            "source_text": "Редактирай доброволец",
            "category": "volunteer",
            "description": "Edit volunteer button",
        },
        {
            "key": "volunteer.status",
            "source_text": "Статус",
            "category": "volunteer",
            "description": "Volunteer status field",
        },
        {
            "key": "volunteer.skills",
            "source_text": "Умения",
            "category": "volunteer",
            "description": "Volunteer skills field",
        },
        {
            "key": "volunteer.availability",
            "source_text": "Наличност",
            "category": "volunteer",
            "description": "Volunteer availability field",
        },
        # Admin Interface
        {
            "key": "admin.dashboard",
            "source_text": "Администрация",
            "category": "admin",
            "description": "Admin dashboard title",
        },
        {
            "key": "admin.statistics",
            "source_text": "Статистики",
            "category": "admin",
            "description": "Statistics section title",
        },
        {
            "key": "admin.analytics",
            "source_text": "Аналитика",
            "category": "admin",
            "description": "Analytics section title",
        },
        {
            "key": "admin.notifications",
            "source_text": "Нотификации",
            "category": "admin",
            "description": "Notifications section title",
        },
        {
            "key": "admin.translations",
            "source_text": "Преводи",
            "category": "admin",
            "description": "Translations section title",
        },
        # Welcome Messages
        {
            "key": "welcome.title",
            "source_text": "Добре дошли в HelpChain",
            "category": "welcome",
            "description": "Main welcome message title",
        },
        {
            "key": "welcome.subtitle",
            "source_text": "Платформа за свързване на нуждаещи се с доброволци",
            "category": "welcome",
            "description": "Welcome message subtitle",
        },
        {
            "key": "welcome.get_started",
            "source_text": "Започнете сега",
            "category": "welcome",
            "description": "Get started button text",
        },
        # Notifications
        {
            "key": "notification.new_volunteer",
            "source_text": "Нов доброволец се регистрира",
            "category": "notification",
            "description": "New volunteer notification",
        },
        {
            "key": "notification.help_request",
            "source_text": "Нова заявка за помощ",
            "category": "notification",
            "description": "New help request notification",
        },
        {
            "key": "notification.volunteer_assigned",
            "source_text": "Доброволец е назначен",
            "category": "notification",
            "description": "Volunteer assigned notification",
        },
    ]

    print("📝 Initializing translation keys...")

    added_count = 0
    for key_data in base_keys:
        existing_key = TranslationKey.query.filter_by(key=key_data["key"]).first()

        if not existing_key:
            translation_key = TranslationKey(**key_data)
            db.session.add(translation_key)
            added_count += 1
            print(f"   ✅ Added key: {key_data['key']}")
        else:
            print(f"   ⏭️  Skipped key: {key_data['key']} (already exists)")

    try:
        db.session.commit()
        print(f"✅ Translation keys initialized successfully ({added_count} new keys)")
        return added_count
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error initializing translation keys: {str(e)}")
        return 0


def initialize_default_translations():
    """Инициализира преводи за default език (български)"""

    print("🔤 Initializing default translations...")

    # Получаваме българския език
    bg_language = SupportedLanguage.query.filter_by(code="bg", is_default=True).first()
    if not bg_language:
        print("❌ Bulgarian language not found")
        return 0

    # Получаваме всички ключове без превод на български
    keys_without_bg = (
        db.session.query(TranslationKey)
        .outerjoin(
            Translation,
            (Translation.key_id == TranslationKey.id)
            & (Translation.language_id == bg_language.id)
            & (Translation.is_current),
        )
        .filter(Translation.id.is_(None))
        .all()
    )

    added_count = 0
    for key in keys_without_bg:
        # За българския език използваме source_text като превод
        translation = Translation(
            key_id=key.id,
            language_id=bg_language.id,
            translated_text=key.source_text,
            status="approved",
            translation_method="manual",
            translator_name="system",
            version=1,
            is_current=True,
            approved_at=datetime.utcnow(),
        )

        db.session.add(translation)
        added_count += 1
        print(f"   ✅ Added BG translation: {key.key}")

    try:
        db.session.commit()
        print(
            f"✅ Default translations initialized successfully ({added_count} translations)"
        )
        return added_count
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error initializing default translations: {str(e)}")
        return 0


def initialize_sample_english_translations():
    """Инициализира примерни преводи на английски"""

    english_translations = {
        "nav.home": "Home",
        "nav.volunteers": "Volunteers",
        "nav.about": "About Us",
        "nav.contact": "Contact",
        "nav.admin": "Administration",
        "common.save": "Save",
        "common.cancel": "Cancel",
        "common.delete": "Delete",
        "common.edit": "Edit",
        "common.view": "View",
        "common.search": "Search",
        "common.loading": "Loading...",
        "common.error": "Error",
        "common.success": "Success",
        "common.warning": "Warning",
        "form.name": "Name",
        "form.email": "Email",
        "form.phone": "Phone",
        "form.message": "Message",
        "form.submit": "Submit",
        "form.required": "Required field",
        "form.invalid_email": "Invalid email address",
        "form.invalid_phone": "Invalid phone number",
        "volunteer.title": "Volunteers",
        "volunteer.add": "Add Volunteer",
        "volunteer.edit": "Edit Volunteer",
        "volunteer.status": "Status",
        "volunteer.skills": "Skills",
        "volunteer.availability": "Availability",
        "admin.dashboard": "Administration",
        "admin.statistics": "Statistics",
        "admin.analytics": "Analytics",
        "admin.notifications": "Notifications",
        "admin.translations": "Translations",
        "welcome.title": "Welcome to HelpChain",
        "welcome.subtitle": "Platform connecting those in need with volunteers",
        "welcome.get_started": "Get Started",
        "notification.new_volunteer": "New volunteer registered",
        "notification.help_request": "New help request",
        "notification.volunteer_assigned": "Volunteer assigned",
    }

    print("🇺🇸 Initializing English translations...")

    # Получаваме английския език
    en_language = SupportedLanguage.query.filter_by(code="en").first()
    if not en_language:
        print("❌ English language not found")
        return 0

    added_count = 0
    for key_name, translated_text in english_translations.items():
        # Намираме ключа
        translation_key = TranslationKey.query.filter_by(key=key_name).first()
        if not translation_key:
            print(f"   ⚠️  Key not found: {key_name}")
            continue

        # Проверяваме дали вече има превод
        existing_translation = Translation.query.filter_by(
            key_id=translation_key.id, language_id=en_language.id, is_current=True
        ).first()

        if existing_translation:
            print(f"   ⏭️  Skipped: {key_name} (already has translation)")
            continue

        # Създаваме превод
        translation = Translation(
            key_id=translation_key.id,
            language_id=en_language.id,
            translated_text=translated_text,
            status="approved",
            translation_method="manual",
            translator_name="system",
            version=1,
            is_current=True,
            approved_at=datetime.utcnow(),
        )

        db.session.add(translation)
        added_count += 1
        print(f"   ✅ Added EN translation: {key_name}")

    try:
        db.session.commit()
        print(
            f"✅ English translations initialized successfully ({added_count} translations)"
        )
        return added_count
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error initializing English translations: {str(e)}")
        return 0


def full_multilingual_initialization():
    """Пълна инициализация на многоезичната система"""

    print("=" * 60)
    print("🌐 HELPCHAIN MULTILINGUAL SYSTEM INITIALIZATION")
    print("=" * 60)

    # 1. Създаваме всички таблици
    print("\n📦 Creating database tables...")
    try:
        db.create_all()
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Error creating tables: {str(e)}")
        return False

    # 2. Инициализираме езиците
    if not initialize_supported_languages():
        return False

    # 3. Инициализираме ключовете за превод
    if initialize_base_translation_keys() == 0:
        print("⚠️  No new translation keys added")

    # 4. Инициализираме default преводите
    if initialize_default_translations() == 0:
        print("⚠️  No new default translations added")

    # 5. Инициализираме английските преводи
    if initialize_sample_english_translations() == 0:
        print("⚠️  No new English translations added")

    print("\n" + "=" * 60)
    print("✅ MULTILINGUAL SYSTEM INITIALIZATION COMPLETE")
    print("=" * 60)

    return True


if __name__ == "__main__":
    # Standalone initialization script
    from appy import app

    with app.app_context():
        full_multilingual_initialization()

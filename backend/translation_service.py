"""
HelpChain Translation Service
Цялостна система за многоезична поддръжка с поддръжка за:
- Dynamic language switching
- Translation management
- AI-powered translations
- Content localization
- Translation memory
- Quality control
"""

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.ai_service import ai_service


def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


from backend.extensions import db
from backend.models import (
    ContentTranslation,
    SupportedLanguage,
    Translation,
    TranslationKey,
    UserLanguagePreference,
)

# AI Translation dependencies
try:
    # ai_service вече е импортиран по-горе
    AI_TRANSLATION_AVAILABLE = True
except ImportError:
    AI_TRANSLATION_AVAILABLE = False
    print("⚠️  AI Translation не е налично. AI преводите няма да работят.")


class TranslationService:
    """Основна система за многоезична поддръжка"""

    def __init__(self):
        self.default_language = "bg"
        self.fallback_language = "en"
        self.cache = {}
        self.cache_timeout = 3600  # 1 час
        self.cache_lock = threading.RLock()
        self.translation_patterns = {}

    # ========================================================================
    # LANGUAGE MANAGEMENT
    # ========================================================================

    def get_supported_languages(self) -> list[SupportedLanguage]:
        """Получава всички поддържани езици"""
        return (
            SupportedLanguage.query.filter_by(is_active=True)
            .order_by(SupportedLanguage.is_default.desc(), SupportedLanguage.name)
            .all()
        )

    def get_language_by_code(self, code: str) -> SupportedLanguage | None:
        """Получава език по код"""
        return SupportedLanguage.query.filter_by(code=code, is_active=True).first()

    def get_default_language(self) -> SupportedLanguage:
        """Получава default езика"""
        default = SupportedLanguage.query.filter_by(
            is_default=True, is_active=True
        ).first()
        if not default:
            default = SupportedLanguage.query.filter_by(
                code=self.default_language
            ).first()
        return default

    def detect_user_language(
        self, request_headers: dict = None, user_id: int = None
    ) -> str:
        """Определя предпочитания език на потребителя"""
        # 1. Проверяваме user preferences (ако е логнат)
        if user_id:
            user_pref = UserLanguagePreference.query.filter_by(
                volunteer_id=user_id, is_primary=True
            ).first()
            if user_pref:
                return user_pref.language.code

        # 2. Проверяваме Accept-Language header
        if request_headers and "Accept-Language" in request_headers:
            accepted = request_headers["Accept-Language"]
            # Парсираме "bg-BG,bg;q=0.9,en;q=0.8"
            languages = self._parse_accept_language(accepted)
            for lang_code in languages:
                if self.get_language_by_code(lang_code):
                    return lang_code

        # 3. Fallback към default
        return self.default_language

    def _parse_accept_language(self, accept_lang: str) -> list[str]:
        """Парсира Accept-Language header"""
        languages = []
        for item in accept_lang.split(","):
            lang = item.split(";")[0].strip().lower()
            # Вземаме само основния код (bg от bg-BG)
            lang_code = lang.split("-")[0]
            if lang_code not in languages:
                languages.append(lang_code)
        return languages

    # ========================================================================
    # TRANSLATION KEY MANAGEMENT
    # ========================================================================

    def register_translation_key(
        self,
        key: str,
        source_text: str,
        category: str = "general",
        context: str = None,
        description: str = None,
        requires_html: bool = False,
        max_length: int = None,
    ) -> TranslationKey:
        """Регистрира нов ключ за превод"""
        try:
            # Проверяваме дали вече съществува
            existing = TranslationKey.query.filter_by(key=key).first()
            if existing:
                # Обновяваме usage_count
                existing.usage_count += 1
                existing.last_used = utc_now()
                if existing.source_text != source_text:
                    existing.source_text = source_text
                    existing.updated_at = utc_now()
                db.session.commit()
                return existing

            # Създаваме нов
            translation_key = TranslationKey(
                key=key,
                source_text=source_text,
                category=category,
                context=context,
                description=description,
                requires_html=requires_html,
                max_length=max_length,
                usage_count=1,
                last_used=utc_now(),
            )

            db.session.add(translation_key)
            db.session.commit()

            # Почистваме кеша
            self._clear_cache()

            print(f"📝 Registered translation key: {key}")
            return translation_key

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error registering translation key: {str(e)}")
            raise

    def bulk_register_keys(self, keys_data: list[dict[str, Any]]) -> int:
        """Bulk регистрация на ключове"""
        registered_count = 0

        try:
            for key_data in keys_data:
                key = key_data.get("key")
                if not key:
                    continue

                existing = TranslationKey.query.filter_by(key=key).first()
                if not existing:
                    translation_key = TranslationKey(
                        key=key,
                        source_text=key_data.get("source_text", ""),
                        category=key_data.get("category", "general"),
                        context=key_data.get("context"),
                        description=key_data.get("description"),
                        requires_html=key_data.get("requires_html", False),
                        max_length=key_data.get("max_length"),
                    )
                    db.session.add(translation_key)
                    registered_count += 1

            db.session.commit()
            self._clear_cache()

            print(f"📝 Bulk registered {registered_count} translation keys")
            return registered_count

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error in bulk registration: {str(e)}")
            return 0

    # ========================================================================
    # TRANSLATION RETRIEVAL
    # ========================================================================

    def get_translation(
        self,
        key: str,
        language_code: str = None,
        variables: dict[str, Any] = None,
        fallback_to_source: bool = True,
    ) -> str:
        """Получава превод за ключ"""
        if not language_code:
            language_code = self.default_language

        # Проверяваме кеша
        cache_key = f"{key}:{language_code}"
        with self.cache_lock:
            cached = self.cache.get(cache_key)
            if cached and cached["timestamp"] > utc_now() - timedelta(
                seconds=self.cache_timeout
            ):
                text = cached["text"]
            else:
                text = self._fetch_translation_from_db(
                    key, language_code, fallback_to_source
                )
                self.cache[cache_key] = {"text": text, "timestamp": utc_now()}

        # Обработваме променливите
        if variables and text:
            text = self._process_variables(text, variables)

        return text or key  # Fallback към ключа ако няма превод

    def get_translations_batch(
        self, keys: list[str], language_code: str = None
    ) -> dict[str, str]:
        """Получава batch от преводи"""
        if not language_code:
            language_code = self.default_language

        results = {}
        uncached_keys = []

        # Проверяваме кеша
        with self.cache_lock:
            for key in keys:
                cache_key = f"{key}:{language_code}"
                cached = self.cache.get(cache_key)
                if cached and cached["timestamp"] > utc_now() - timedelta(
                    seconds=self.cache_timeout
                ):
                    results[key] = cached["text"]
                else:
                    uncached_keys.append(key)

        # Вземаме некешираните от DB
        if uncached_keys:
            db_results = self._fetch_translations_batch_from_db(
                uncached_keys, language_code
            )

            with self.cache_lock:
                for key, text in db_results.items():
                    cache_key = f"{key}:{language_code}"
                    self.cache[cache_key] = {
                        "text": text,
                        "timestamp": utc_now(),
                    }
                    results[key] = text

        return results

    def _fetch_translation_from_db(
        self, key: str, language_code: str, fallback_to_source: bool = True
    ) -> str:
        """Вземa превод от базата данни"""
        try:
            # Намираме ключа
            translation_key = TranslationKey.query.filter_by(key=key).first()
            if not translation_key:
                # Auto-register ключа със самия ключ като source text
                translation_key = self.register_translation_key(key, key)

            # Намираме езика
            language = self.get_language_by_code(language_code)
            if not language:
                language = self.get_default_language()

            # Намираме превода
            translation = Translation.query.filter_by(
                key_id=translation_key.id,
                language_id=language.id,
                is_current=True,
                status="approved",
            ).first()

            if translation:
                return translation.translated_text

            # Fallback опции
            if fallback_to_source:
                # Опитваме се с fallback езика
                if language_code != self.fallback_language:
                    fallback_lang = self.get_language_by_code(self.fallback_language)
                    if fallback_lang:
                        fallback_translation = Translation.query.filter_by(
                            key_id=translation_key.id,
                            language_id=fallback_lang.id,
                            is_current=True,
                            status="approved",
                        ).first()
                        if fallback_translation:
                            return fallback_translation.translated_text

                # Последен fallback - source text
                return translation_key.source_text

            return None

        except Exception as e:
            print(f"❌ Error fetching translation for {key}: {str(e)}")
            return None

    def _fetch_translations_batch_from_db(
        self, keys: list[str], language_code: str
    ) -> dict[str, str]:
        """Batch вземане на преводи от DB"""
        try:
            language = self.get_language_by_code(language_code)
            if not language:
                language = self.get_default_language()

            # JOIN query за по-добра производителност
            results = (
                db.session.query(TranslationKey.key, Translation.translated_text)
                .join(Translation, Translation.key_id == TranslationKey.id)
                .filter(
                    TranslationKey.key.in_(keys),
                    Translation.language_id == language.id,
                    Translation.is_current,
                    Translation.status == "approved",
                )
                .all()
            )

            return {key: text for key, text in results}

        except Exception as e:
            print(f"❌ Error fetching batch translations: {str(e)}")
            return {}

    def _process_variables(self, text: str, variables: dict[str, Any]) -> str:
        """Обработва променливи в текста"""
        try:
            # Поддържаме както {{ var }} така и {var} формати
            for var_name, var_value in variables.items():
                # Flask/Jinja2 style
                text = text.replace(f"{{{{{var_name}}}}}", str(var_value))
                # Python format style
                text = text.replace(f"{{{var_name}}}", str(var_value))

            return text

        except Exception as e:
            print(f"⚠️  Error processing variables: {str(e)}")
            return text

    # ========================================================================
    # TRANSLATION MANAGEMENT
    # ========================================================================

    def add_translation(
        self,
        key: str,
        language_code: str,
        translated_text: str,
        translator_name: str = None,
        status: str = "draft",
        translation_method: str = "manual",
    ) -> Translation | None:
        """Добавя нов превод"""
        try:
            # Намираме ключа
            translation_key = TranslationKey.query.filter_by(key=key).first()
            if not translation_key:
                raise ValueError(f"Translation key '{key}' not found")

            # Намираме езика
            language = self.get_language_by_code(language_code)
            if not language:
                raise ValueError(f"Language '{language_code}' not supported")

            # Проверяваме дали вече има текущ превод
            existing = Translation.query.filter_by(
                key_id=translation_key.id, language_id=language.id, is_current=True
            ).first()

            if existing:
                # Деактивираме стария
                existing.is_current = False
                existing.version += 1

            # Създаваме новия
            translation = Translation(
                key_id=translation_key.id,
                language_id=language.id,
                translated_text=translated_text,
                status=status,
                translation_method=translation_method,
                translator_name=translator_name,
                version=existing.version + 1 if existing else 1,
                is_current=True,
            )

            if status == "approved":
                translation.approved_at = utc_now()

            db.session.add(translation)
            db.session.commit()

            # Почистваме кеша
            self._clear_cache_for_key(key)

            print(f"✅ Added translation: {key} ({language_code})")
            return translation

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding translation: {str(e)}")
            return None

    def bulk_add_translations(self, translations_data: list[dict[str, Any]]) -> int:
        """Bulk добавяне на преводи"""
        added_count = 0

        try:
            for trans_data in translations_data:
                key = trans_data.get("key")
                language_code = trans_data.get("language_code")
                translated_text = trans_data.get("translated_text")

                if not all([key, language_code, translated_text]):
                    continue

                translation = self.add_translation(
                    key=key,
                    language_code=language_code,
                    translated_text=translated_text,
                    translator_name=trans_data.get("translator_name"),
                    status=trans_data.get("status", "approved"),
                    translation_method=trans_data.get("translation_method", "manual"),
                )

                if translation:
                    added_count += 1

            print(f"✅ Bulk added {added_count} translations")
            return added_count

        except Exception as e:
            print(f"❌ Error in bulk translation addition: {str(e)}")
            return 0

    # ========================================================================
    # AI TRANSLATION
    # ========================================================================

    def auto_translate_missing(
        self,
        target_language_code: str,
        source_language_code: str = None,
        max_translations: int = 100,
    ) -> int:
        """Автоматично превежда липсващи текстове с AI"""
        if not AI_TRANSLATION_AVAILABLE:
            print("⚠️  AI Translation не е налично")
            return 0

        if not source_language_code:
            source_language_code = self.default_language

        try:
            target_language = self.get_language_by_code(target_language_code)
            source_language = self.get_language_by_code(source_language_code)

            if not target_language or not source_language:
                raise ValueError("Invalid language codes")

            # Намираме ключове без превод в target езика
            missing_keys = (
                db.session.query(TranslationKey)
                .outerjoin(
                    Translation,
                    (Translation.key_id == TranslationKey.id)
                    & (Translation.language_id == target_language.id)
                    & (Translation.is_current),
                )
                .filter(Translation.id.is_(None))
                .limit(max_translations)
                .all()
            )

            translated_count = 0

            for key in missing_keys:
                # Получаваме source текста
                source_translation = Translation.query.filter_by(
                    key_id=key.id, language_id=source_language.id, is_current=True
                ).first()

                source_text = (
                    source_translation.translated_text
                    if source_translation
                    else key.source_text
                )

                # AI превод
                ai_translation = self._translate_with_ai(
                    text=source_text,
                    target_language=target_language.code,
                    source_language=source_language.code,
                )

                if ai_translation:
                    translation = Translation(
                        key_id=key.id,
                        language_id=target_language.id,
                        translated_text=ai_translation["text"],
                        status="review",  # AI преводите трябва да се прегледат
                        translation_method="ai",
                        ai_provider=ai_translation.get("provider", "openai"),
                        ai_confidence=ai_translation.get("confidence", 0.8),
                        original_ai_text=ai_translation["text"],
                        is_current=True,
                    )

                    db.session.add(translation)
                    translated_count += 1

            db.session.commit()
            self._clear_cache()

            print(f"🤖 AI translated {translated_count} keys to {target_language_code}")
            return translated_count

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error in AI translation: {str(e)}")
            return 0

    def _translate_with_ai(
        self, text: str, target_language: str, source_language: str = "bg"
    ) -> dict[str, Any] | None:
        """Превежда текст с AI"""
        if not AI_TRANSLATION_AVAILABLE:
            return None

        try:
            # Подготвяме prompt за AI
            language_names = {
                "bg": "Bulgarian",
                "en": "English",
                "de": "German",
                "fr": "French",
                "es": "Spanish",
                "ru": "Russian",
            }

            source_lang_name = language_names.get(source_language, source_language)
            target_lang_name = language_names.get(target_language, target_language)

            prompt = f"""
            Translate the following text from {source_lang_name} to {target_lang_name}.
            Preserve any HTML tags and formatting. Be accurate and natural.

            Text to translate:
            {text}

            Translation:
            """

            # Използваме AI service
            response = ai_service.generate_response(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3,  # По-ниска temperature за по-точни преводи
            )

            if response and response.get("success"):
                return {
                    "text": response["response"].strip(),
                    "provider": "openai",
                    "confidence": 0.8,  # Default confidence
                }

            return None

        except Exception as e:
            print(f"❌ AI translation error: {str(e)}")
            return None

    # ========================================================================
    # CONTENT TRANSLATION
    # ========================================================================

    def translate_content(
        self,
        content_type: str,
        content_id: int,
        language_code: str,
        title: str = None,
        content: str = None,
        **kwargs,
    ) -> ContentTranslation | None:
        """Превежда динамично съдържание"""
        try:
            language = self.get_language_by_code(language_code)
            if not language:
                raise ValueError(f"Language '{language_code}' not supported")

            # Проверяваме дали вече съществува
            existing = ContentTranslation.query.filter_by(
                content_type=content_type,
                content_id=content_id,
                language_id=language.id,
            ).first()

            if existing:
                # Обновяваме съществуващия
                if title is not None:
                    existing.title = title
                if content is not None:
                    existing.content = content

                for field in ["excerpt", "meta_title", "meta_description", "slug"]:
                    if field in kwargs:
                        setattr(existing, field, kwargs[field])

                existing.updated_at = utc_now()
                result = existing
            else:
                # Създаваме нов
                result = ContentTranslation(
                    content_type=content_type,
                    content_id=content_id,
                    language_id=language.id,
                    title=title,
                    content=content,
                    excerpt=kwargs.get("excerpt"),
                    meta_title=kwargs.get("meta_title"),
                    meta_description=kwargs.get("meta_description"),
                    slug=kwargs.get("slug"),
                    status=kwargs.get("status", "draft"),
                    translator_id=kwargs.get("translator_id"),
                    translation_notes=kwargs.get("translation_notes"),
                )
                db.session.add(result)

            db.session.commit()
            print(
                f"✅ Content translated: {content_type}:{content_id} ({language_code})"
            )
            return result

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error translating content: {str(e)}")
            return None

    def get_content_translation(
        self, content_type: str, content_id: int, language_code: str
    ) -> ContentTranslation | None:
        """Получава превод на съдържание"""
        language = self.get_language_by_code(language_code)
        if not language:
            return None

        return ContentTranslation.query.filter_by(
            content_type=content_type,
            content_id=content_id,
            language_id=language.id,
            status="published",
        ).first()

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def _clear_cache(self):
        """Почиства целия кеш"""
        with self.cache_lock:
            self.cache.clear()

    def _clear_cache_for_key(self, key: str):
        """Почиства кеша за конкретен ключ"""
        with self.cache_lock:
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{key}:")]
            for k in keys_to_remove:
                del self.cache[k]

    def get_translation_stats(self) -> dict[str, Any]:
        """Получава статистики за преводите"""
        try:
            languages = self.get_supported_languages()
            stats = {
                "total_keys": TranslationKey.query.filter_by(is_active=True).count(),
                "total_translations": Translation.query.filter_by(
                    is_current=True
                ).count(),
                "languages": [],
            }

            for language in languages:
                lang_translations = Translation.query.filter_by(
                    language_id=language.id, is_current=True
                ).count()

                completion_percentage = 0
                if stats["total_keys"] > 0:
                    completion_percentage = round(
                        (lang_translations / stats["total_keys"]) * 100, 1
                    )

                stats["languages"].append(
                    {
                        "code": language.code,
                        "name": language.name,
                        "native_name": language.native_name,
                        "translations_count": lang_translations,
                        "completion_percentage": completion_percentage,
                        "is_default": language.is_default,
                    }
                )

            return stats

        except Exception as e:
            print(f"❌ Error getting translation stats: {str(e)}")
            return {}

    def format_date(self, date_obj, language_code: str = None) -> str:
        """Форматира дата според езиковите настройки"""
        if not language_code:
            language_code = self.default_language

        language = self.get_language_by_code(language_code)
        if language and language.date_format:
            return date_obj.strftime(language.date_format)

        # Default format
        return date_obj.strftime("%d.%m.%Y")

    def format_time(self, time_obj, language_code: str = None) -> str:
        """Форматира време според езиковите настройки"""
        if not language_code:
            language_code = self.default_language

        language = self.get_language_by_code(language_code)
        if language and language.time_format:
            return time_obj.strftime(language.time_format)

        # Default format
        return time_obj.strftime("%H:%M")


# Създаваме глобална инстанция
translation_service = TranslationService()


# Quick helper functions
def t(key: str, language_code: str = None, **variables) -> str:
    """Бърз helper за превод"""
    return translation_service.get_translation(key, language_code, variables)


def get_supported_languages() -> list[SupportedLanguage]:
    """Бърз helper за поддържани езици"""
    return translation_service.get_supported_languages()


def detect_language(request_headers: dict = None, user_id: int = None) -> str:
    """Бърз helper за определяне на език"""
    return translation_service.detect_user_language(request_headers, user_id)

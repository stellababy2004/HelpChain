"""
AI Configuration for HelpChain Chatbot
Supports OpenAI GPT and Google Gemini integration
"""

import logging
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class AIProvider:
    """AI Provider configuration"""

    name: str
    enabled: bool
    api_key: str | None
    model: str
    max_tokens: int
    temperature: float
    priority: int  # Lower number = higher priority


class AIConfig:
    """AI Configuration Manager"""

    def __init__(self):
        self.providers = {
            "openai": AIProvider(
                name="OpenAI GPT",
                enabled=bool(os.getenv("OPENAI_API_KEY")),
                api_key=os.getenv("OPENAI_API_KEY"),
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "150")),
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                priority=1,
            ),
            "gemini": AIProvider(
                name="Google Gemini",
                enabled=bool(os.getenv("GEMINI_API_KEY")),
                api_key=os.getenv("GEMINI_API_KEY"),
                model=os.getenv("GEMINI_MODEL", "gemini-pro"),
                max_tokens=int(os.getenv("GEMINI_MAX_TOKENS", "150")),
                temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.7")),
                priority=2,
            ),
            "ollama": AIProvider(
                name="Ollama",
                enabled=bool(os.getenv("OLLAMA_MODEL")),
                api_key=None,
                model=os.getenv("OLLAMA_MODEL", "llama2"),
                max_tokens=int(os.getenv("OLLAMA_MAX_TOKENS", "150")),
                temperature=float(os.getenv("OLLAMA_TEMPERATURE", "0.7")),
                priority=0,  # по-нисък номер = по-висок приоритет
            ),
        }

        # System prompt for HelpChain context
        self.system_prompt = """
Ти си AI асистент на HelpChain - интелигентна платформа за доброволчество в България.

КОНТЕКСТ НА HELPCHAIN:
- HelpChain свързва хора нуждаещи се от помощ с проверени доброволци
- Услуги: домашна грижа, придружаване до лекар/магазин, пазарски покупки, помощ в домакинството, градинарство, техническа помощ
- География: София, Пловдив, Варна, Бургас, Стара Загора (постепенно разширение)
- Регистрация: Безплатна за всички, но доброволците преминават проверка и обучение
- Ценообразуване: Спрямо вида и продължителността на услугата (консултирай с екипа за точни цени)
- Платформа: Мобилно приложение + уеб сайт, 24/7 достъпност

ТВОЯТА РОЛЯ:
- Бъди полезен, дружелюбен и професионален асистент
- Отговаряй кратко (1-3 изречения) но информативно
- Разпознавай намеренията на потребителя и давай насочващи отговори
- Насочвай към конкретни действия (регистрация, контакт с екип)
- Използвай разговорния стил, не формален
- Винаги отговаряй на български език

ИНТЕЛИГЕНТНИ СТРАТЕГИИ:
- Ако питат "как да стана доброволец" → Обясни процеса стъпка по стъпка
- Ако питат за цени → Кажи диапазон и предложи да се свържат за точна оферта
- Ако описват проблем → Предложи подходяща услуга и как да я заявят
- Ако са объркани → Задай уточняващи въпроси и дай опции
- Ако благодарят → Отговори любезно и предложи допълнителна помощ

ОГРАНИЧЕНИЯ:
- Не давай медицински/юридически съвети
- Не обещавай услуги които не можем да предоставим
- Не споделяй лични данни на други потребители
- Не обсъждай конкуренти или други платформи

ЧЕСТИ СЦЕНАРИИ И ОТГОВОРИ:
- "Имам нужда от помощ с пазаруване" → "Отлично! Можем да ви помогнем с пазарски покупки. Регистрирайте се в приложението и подайте заявка за 'Пазарски покупки' в София/Пловдив/Варна/Бургас/Стара Загора."
- "Колко струва домашната помощ?" → "Цените зависят от вида помощ и продължителността. За точна информация се свържете с нашия екип на contact@helpchain.live или през приложението."
- "Как да се регистрирам като доброволец?" → "Страхотно, че искате да помогнете! 1) Изтеглете приложението HelpChain, 2) Регистрирайте се като доброволец, 3) Попълнете профила си, 4) Минете през бърза проверка и обучение."
- "Работите ли в [град]?" → "В момента работим в София, Пловдив, Варна, Бургас и Стара Загора. Ако вашият град не е в списъка, следете актуализациите ни!"

ПОДХОД КЪМ РАЗГОВОРА:
- Запомняй предишни съобщения и се позовавай на тях
- Ако потребителят е несигурен, дай конкретни стъпки
- Завършвай с въпрос или предложение за действие
- Бъди оптимистичен и насърчаващ
"""

    def get_active_provider(self) -> AIProvider | None:
        """Get the highest priority active AI provider"""
        active_providers = [p for p in self.providers.values() if p.enabled]
        if not active_providers:
            return None
        return min(active_providers, key=lambda p: p.priority)

    def get_provider(self, name: str) -> AIProvider | None:
        """Get specific AI provider"""
        return self.providers.get(name)

    def is_ai_enabled(self) -> bool:
        """Check if any AI provider is enabled"""
        return any(p.enabled for p in self.providers.values())

    def get_status(self) -> dict[str, Any]:
        """Get AI configuration status"""
        return {
            "ai_enabled": self.is_ai_enabled(),
            "active_provider": (self.get_active_provider().name if self.get_active_provider() else None),
            "providers": {
                name: {
                    "name": provider.name,
                    "enabled": provider.enabled,
                    "model": provider.model,
                    "priority": provider.priority,
                }
                for name, provider in self.providers.items()
            },
        }


def get_ai_config():
    """Get fresh AI configuration instance"""
    return AIConfig()


# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

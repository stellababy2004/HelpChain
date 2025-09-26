# -*- coding: utf-8 -*-
"""
AI Configuration for HelpChain Chatbot
Supports OpenAI GPT and Google Gemini integration
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AIProvider:
    """AI Provider configuration"""

    name: str
    enabled: bool
    api_key: Optional[str]
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
        }

        # System prompt for HelpChain context
        self.system_prompt = """
Ти си AI асистент на HelpChain - платформа за доброволчество в България.

КОНТЕКСТ НА HELPCHAIN:
- HelpChain е платформа която свързва хора нуждаещи се от помощ с доброволци
- Услугите включват: домашна грижа, придружаване, пазарски, помощ в домакинството
- Работим в София, Пловдив, Варна, Бургас и Стара Загора
- Регистрацията е безплатна, но има такса за услугите
- Доброволците преминават проверка и обучение

ТВОЯТА РОЛЯ:
- Отговаряй кратко и полезно (максимум 2-3 изречения)
- Винаги бъди мил, отзивчив и професионален
- Насочвай към регистрация когато е подходящо
- За сложни въпроси предлагай контакт с екипа
- Отговаряй САМО на български език

ОГРАНИЧЕНИЯ:
- Не даваш медицински съвети
- Не обещаваш услуги които не предлагаме
- Не споделяш лична информация за потребители
"""

    def get_active_provider(self) -> Optional[AIProvider]:
        """Get the highest priority active AI provider"""
        active_providers = [p for p in self.providers.values() if p.enabled]
        if not active_providers:
            return None
        return min(active_providers, key=lambda p: p.priority)

    def get_provider(self, name: str) -> Optional[AIProvider]:
        """Get specific AI provider"""
        return self.providers.get(name)

    def is_ai_enabled(self) -> bool:
        """Check if any AI provider is enabled"""
        return any(p.enabled for p in self.providers.values())

    def get_status(self) -> Dict[str, Any]:
        """Get AI configuration status"""
        return {
            "ai_enabled": self.is_ai_enabled(),
            "active_provider": (
                self.get_active_provider().name if self.get_active_provider() else None
            ),
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


# Global AI configuration instance
ai_config = AIConfig()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

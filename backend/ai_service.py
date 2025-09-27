# -*- coding: utf-8 -*-
"""
AI Service for HelpChain Chatbot
Integrates with OpenAI GPT and Google Gemini
"""

# Import AI SDKs safely: if the package isn't installed the module variable
# will be set to None and the app will continue to run with fallbacks.
try:
    import openai
except Exception:
    openai = None
try:
    import requests
except Exception:
    requests = None

try:
    import google.generativeai as genai
except Exception:
    genai = None
try:
    from langdetect import detect
except Exception:
    # Fallback detect function when langdetect is not installed.
    # We default to Bulgarian ('bg') to keep behavior predictable.
    import logging as _logging

    _logging.warning("langdetect not installed — defaulting language detection to 'bg'")

    def detect(text: str) -> str:  # type: ignore
        return "bg"


import traceback
import os
import unicodedata
import re
from typing import Optional, Dict, Any, Tuple
from ai_config import ai_config, logger


def _safe_message(exc: Exception) -> str:
    """Return a UTF-8 safe string for an exception.

    Build a concise message using the exception class and args, then
    force it through UTF-8 encoding with backslashreplace to avoid
    raising UnicodeEncodeError when the environment default encoding is
    latin-1 or otherwise incompatible.
    """
    try:
        cls_name = exc.__class__.__name__
        args = getattr(exc, "args", ()) or ()
        try:
            # Create a readable args representation, prefer plain strings
            args_parts = []
            for a in args:
                if isinstance(a, str):
                    args_parts.append(a)
                else:
                    try:
                        args_parts.append(repr(a))
                    except Exception:
                        args_parts.append("<unrepresentable>")
            args_str = ", ".join(args_parts)
        except Exception:
            args_str = repr(args)

        msg = f"{cls_name}: {args_str}"
        # Force UTF-8-safe representation
        safe = msg.encode("utf-8", "backslashreplace").decode("utf-8")
        return safe
    except Exception:
        try:
            return repr(exc).encode("utf-8", "backslashreplace").decode("utf-8")
        except Exception:
            return "<unprintable exception>"


def _sanitize_api_key(raw_key: Any) -> Tuple[str, list]:
    """Clean and validate an API key string.

    Returns a tuple (cleaned_key, issues) where issues is a list of
    human-readable problem descriptions (empty if no issues).
    """
    issues = []
    if not isinstance(raw_key, str):
        issues.append("API key is not a string")
        return ("", issues)

    # Normalize and trim
    s = unicodedata.normalize("NFKC", raw_key).strip()

    # Remove invisible/control characters (category Cc and Cf)
    cleaned_chars = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat in ("Cc", "Cf"):
            # skip control/formatting chars like zero-width space
            continue
        cleaned_chars.append(ch)
    cleaned = "".join(cleaned_chars)

    # Remove common Unicode whitespace variants
    cleaned = re.sub(r"[\u2000-\u200B\uFEFF]", "", cleaned)

    if not cleaned:
        issues.append("API key is empty after trimming")
        return ("", issues)

    # Basic sanity checks
    if not cleaned.isascii():
        issues.append("API key contains non-ASCII characters")

    # Placeholder detection: look for obvious localized placeholders
    lower = cleaned.lower()
    placeholder_indicators = [
        "ваш",
        "your",
        "ключ",
        "key",
        "placeholder",
        "tua",
        "tuo",
        "вашия",
        "ваш_к",
        "sk-ваш",
    ]
    for ph in placeholder_indicators:
        if ph in lower:
            issues.append('API key looks like a placeholder (contains "%s")' % ph)
            break

    # Ensure likely format: starts with sk-
    if not lower.startswith("sk-"):
        issues.append('API key does not start with "sk-"')

    # If there are issues, attempt to extract a likely ASCII sk-... substring from the raw input
    if issues:
        try:
            # Search the original (raw) key for a contiguous ASCII-looking secret like sk-<chars>
            m = re.search(r"(sk-[A-Za-z0-9_-]{20,100})", raw_key)
            if m:
                extracted = m.group(1)
                # If extraction yields an improvement, return it and note the extraction
                if extracted and extracted != cleaned:
                    cleaned = extracted
                    # Re-evaluate ASCII/start checks
                    issues = []
                    if not cleaned.isascii():
                        issues.append("Extracted key contains non-ASCII characters")
                    if not cleaned.lower().startswith("sk-"):
                        issues.append('Extracted key does not start with "sk-"')
                    if not issues:
                        issues.append(
                            "Extracted key from input (used for connectivity test)"
                        )
        except Exception:
            # If extraction fails silently, keep original issues
            pass

    return (cleaned, issues)


class AIService:
    """AI Service for generating intelligent responses"""

    def __init__(self):
        self.setup_providers()

    def setup_providers(self):
        """Initialize AI providers"""
        try:
            # Setup OpenAI (only if SDK is available)
            openai_provider = ai_config.get_provider("openai")
            if openai_provider and openai_provider.enabled:
                if openai is None:
                    logger.warning(
                        "⚠️ OpenAI SDK not installed - OpenAI provider disabled at runtime"
                    )
                else:
                    openai.api_key = openai_provider.api_key
                    logger.info("✅ OpenAI configured successfully")

            # Setup Gemini (only if SDK is available)
            gemini_provider = ai_config.get_provider("gemini")
            if gemini_provider and gemini_provider.enabled:
                if genai is None:
                    logger.warning(
                        "⚠️ Google Generative AI SDK not installed - Gemini provider disabled at runtime"
                    )
                else:
                    genai.configure(api_key=gemini_provider.api_key)
                    logger.info("✅ Gemini configured successfully")

        except Exception as e:
            logger.error(f"❌ Error setting up AI providers: {e}")

    async def generate_response(
        self, user_message: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate AI response to user message

        Args:
            user_message: User's question/message
            context: Optional context (conversation history, user info, etc.)

        Returns:
            Dict with response, confidence, provider used, etc.
        """
        try:
            # Detect language
            try:
                detected_lang = detect(user_message)
            except Exception:
                detected_lang = "bg"  # Default to Bulgarian

            # Development mock mode: allow local dev without an API key
            mock_flag = os.getenv("AI_DEV_MOCK", "").lower() in ("1", "true", "yes")
            if mock_flag:
                # Simple canned reply useful for UI/workflow testing
                return {
                    "response": "Това е mock отговор за разработка. (AI_DEV_MOCK=1)",
                    "confidence": 0.5,
                    "provider": "mock",
                    "language_detected": "bg",
                }

            # Get active provider
            provider = ai_config.get_active_provider()
            if not provider:
                return {
                    "response": "Извинявам се, AI услугата временно не е достъпна. Моля опитайте пак по-късно.",
                    "confidence": 0.0,
                    "provider": "fallback",
                    "error": "No AI provider available",
                }

            # Prepare the conversation context
            conversation_context = self._build_context(
                user_message, context, detected_lang
            )

            # Generate response based on provider
            if provider.name == "OpenAI GPT":
                result = await self._generate_openai_response(
                    conversation_context, provider
                )
            elif provider.name == "Google Gemini":
                result = await self._generate_gemini_response(
                    conversation_context, provider
                )
            else:
                raise ValueError(f"Unknown provider: {provider.name}")

            # Post-process response
            result["language_detected"] = detected_lang
            result["provider"] = provider.name

            logger.info(f"🤖 AI Response generated via {provider.name}")
            return result
        except Exception as e:
            logger.error(f"❌ Error generating AI response: {_safe_message(e)}")
            logger.error(traceback.format_exc())
            return {
                "response": "Извинявам се, възникна грешка при генерирането на отговора. Моля свържете се с нашия екип за помощ.",
                "confidence": 0.0,
                "provider": "error_fallback",
                "error": _safe_message(e),
            }

    def _build_context(
        self, user_message: str, context: Optional[Dict[str, Any]], language: str
    ) -> str:
        """Build conversation context for AI"""

        context_parts = [ai_config.system_prompt]

        if context and context.get("conversation_history"):
            context_parts.append("\nПОСЛЕДНИ СЪОБЩЕНИЯ:")
            for msg in context["conversation_history"][-3:]:  # Last 3 messages
                context_parts.append(f"Потребител: {msg.get('user_message', '')}")
                context_parts.append(f"Асистент: {msg.get('bot_response', '')}")

        if language != "bg":
            context_parts.append(
                f"\nЗАБЕЛЕЖКА: Потребителят пише на {language}, но отговори ЗАДЪЛЖИТЕЛНО на български език."
            )

        context_parts.append(f"\nВЪПРОС НА ПОТРЕБИТЕЛЯ: {user_message}")
        context_parts.append("\nТВОЯТ ОТГОВОР (кратко, полезно, на български):")

        return "\n".join(context_parts)

    async def _generate_openai_response(self, context: str, provider) -> Dict[str, Any]:
        """Generate response using OpenAI"""
        try:
            if openai is None:
                raise RuntimeError(
                    "OpenAI SDK is not installed. Install with 'pip install openai' to enable this provider."
                )

            # Support both pre-1.0 (openai.ChatCompletion.create) and openai>=1.0 (OpenAI client)
            ai_response = None
            tokens_used = None

            # Old-style API
            if hasattr(openai, "ChatCompletion"):
                response = openai.ChatCompletion.create(
                    model=provider.model,
                    messages=[{"role": "system", "content": context}],
                    max_tokens=provider.max_tokens,
                    temperature=provider.temperature,
                    top_p=0.9,
                    frequency_penalty=0.1,
                    presence_penalty=0.1,
                )
                ai_response = response.choices[0].message.content.strip()
                # usage may be an object with total_tokens
                try:
                    tokens_used = response.usage.total_tokens
                except Exception:
                    tokens_used = None

            else:
                # New-style openai>=1.0 API: instantiate client and call chat completions
                try:
                    client = openai.OpenAI()
                except Exception as e:
                    raise RuntimeError(
                        "Detected openai>=1.0 but failed to instantiate OpenAI client. "
                        "See https://github.com/openai/openai-python for migration instructions. "
                        f"Original error: {e}"
                    )

                # Call chat completions on the new client
                resp = client.chat.completions.create(
                    model=provider.model,
                    messages=[{"role": "system", "content": context}],
                    max_tokens=provider.max_tokens,
                    temperature=provider.temperature,
                )

                # Parse response (new SDK structures can vary) -- try common access patterns
                try:
                    ai_response = resp.choices[0].message.content.strip()
                except Exception:
                    try:
                        ai_response = resp.choices[0]["message"]["content"].strip()
                    except Exception:
                        ai_response = str(resp)

                # tokens usage may be present
                usage = getattr(resp, "usage", None)
                if usage is None and isinstance(resp, dict):
                    usage = resp.get("usage")

                if usage:
                    try:
                        tokens_used = usage.total_tokens
                    except Exception:
                        try:
                            tokens_used = usage.get("total_tokens")
                        except Exception:
                            tokens_used = None

            confidence = self._calculate_confidence(ai_response or "")

            return {
                "response": ai_response,
                "confidence": confidence,
                "tokens_used": tokens_used,
                "model": provider.model,
            }

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def _generate_gemini_response(self, context: str, provider) -> Dict[str, Any]:
        """Generate response using Google Gemini"""
        try:
            if genai is None:
                raise RuntimeError(
                    "Google Generative AI SDK is not installed. Install the appropriate package to enable Gemini provider."
                )
            model = genai.GenerativeModel(provider.model)

            generation_config = genai.types.GenerationConfig(
                max_output_tokens=provider.max_tokens,
                temperature=provider.temperature,
                top_p=0.9,
                top_k=40,
            )

            response = model.generate_content(
                context, generation_config=generation_config
            )

            ai_response = response.text.strip()
            confidence = self._calculate_confidence(ai_response)

            return {
                "response": ai_response,
                "confidence": confidence,
                "tokens_used": len(context.split())
                + len(ai_response.split()),  # Approximate
                "model": provider.model,
            }

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    def _calculate_confidence(self, response: str) -> float:
        """Calculate confidence score for the response"""
        # Simple heuristic confidence calculation
        if len(response) < 10:
            return 0.3
        elif len(response) < 30:
            return 0.6
        elif "извинявам се" in response.lower() or "не знам" in response.lower():
            return 0.4
        elif any(
            word in response.lower()
            for word in ["регистрация", "helpchain", "доброволец", "услуга"]
        ):
            return 0.9
        else:
            return 0.7

    def get_ai_status(self) -> Dict[str, Any]:
        """Get AI service status"""
        status = ai_config.get_status()
        status["service_ready"] = ai_config.is_ai_enabled()
        return status

    def test_connection(self) -> Dict[str, Any]:
        """Test AI provider connections"""
        results = {}
        mock_flag = os.getenv("AI_DEV_MOCK", "").lower() in ("1", "true", "yes")

        for name, provider in ai_config.providers.items():
            if mock_flag:
                results[name] = {
                    "status": "ok",
                    "message": "Mock mode enabled (AI_DEV_MOCK)",
                }
                continue

            if not provider.enabled:
                results[name] = {
                    "status": "disabled",
                    "message": "API key not provided",
                }
                continue

            try:
                if name == "openai":
                    # Test OpenAI (support both old and new SDK interfaces)
                    if openai is None:
                        results[name] = {
                            "status": "disabled",
                            "message": "openai package not installed",
                        }
                    else:
                        # Try to use old API if present
                        try:
                            # Prefer direct REST call to OpenAI to avoid SDK-internal encoding issues.
                            if requests is None:
                                # Fall back to SDK check if requests isn't available
                                raise RuntimeError("requests package not available")

                            # HTTP headers must be ASCII; ensure the API key is ASCII to avoid
                            # UnicodeEncodeError from the underlying HTTP library.
                            raw_key = provider.api_key
                            cleaned_key, issues = _sanitize_api_key(raw_key)
                            if issues:
                                results[name] = {
                                    "status": "error",
                                    "message": "; ".join(issues),
                                }
                                continue

                            # Do the REST check with the cleaned/normalized key
                            headers = {"Authorization": f"Bearer {cleaned_key}"}
                            # If requests isn't available, fallback to SDK-based check below
                            if requests is None:
                                raise RuntimeError("requests package not available")

                            resp = requests.get(
                                "https://api.openai.com/v1/models",
                                headers=headers,
                                timeout=5,
                            )
                            if resp.status_code == 200:
                                results[name] = {
                                    "status": "ok",
                                    "message": "Connection successful",
                                }
                            elif resp.status_code == 401:
                                results[name] = {
                                    "status": "error",
                                    "message": "Incorrect API key provided",
                                }
                            else:
                                results[name] = {
                                    "status": "error",
                                    "message": f"HTTP {resp.status_code}: {resp.text[:300]}",
                                }
                        except Exception as e:
                            # If requests is missing or REST check failed, try SDK fallback
                            if requests is None and openai is not None:
                                try:
                                    # SDK fallback: try minimal call to list models or create a tiny completion
                                    try:
                                        # Old-style
                                        if hasattr(openai, "ChatCompletion"):
                                            openai.api_key = provider.api_key
                                            openai.ChatCompletion.create(
                                                model="gpt-3.5-turbo",
                                                messages=[
                                                    {"role": "user", "content": "Test"}
                                                ],
                                                max_tokens=1,
                                            )
                                            results[name] = {
                                                "status": "ok",
                                                "message": "Connection successful (via SDK fallback)",
                                            }
                                            continue
                                        else:
                                            client = openai.OpenAI()
                                            client.chat.completions.create(
                                                model="gpt-3.5-turbo",
                                                messages=[
                                                    {"role": "user", "content": "Test"}
                                                ],
                                                max_tokens=1,
                                            )
                                            results[name] = {
                                                "status": "ok",
                                                "message": "Connection successful (via SDK fallback)",
                                            }
                                            continue
                                    except Exception as sdk_e:
                                        results[name] = {
                                            "status": "error",
                                            "message": _safe_message(sdk_e),
                                        }
                                        continue
                                except Exception:
                                    results[name] = {
                                        "status": "error",
                                        "message": _safe_message(e),
                                    }
                            else:
                                results[name] = {
                                    "status": "error",
                                    "message": _safe_message(e),
                                }

                elif name == "gemini":
                    # Test Gemini
                    if genai is None:
                        results[name] = {
                            "status": "disabled",
                            "message": "google.generativeai package not installed",
                        }
                    else:
                        genai.configure(api_key=provider.api_key)
                        model = genai.GenerativeModel("gemini-pro")
                        _response = model.generate_content("Тест")
                        results[name] = {
                            "status": "ok",
                            "message": "Connection successful",
                        }

            except Exception as e:
                results[name] = {"status": "error", "message": _safe_message(e)}

        return results


# Global AI service instance
ai_service = AIService()

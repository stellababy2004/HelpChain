import os
import pytest
from unittest.mock import patch
from backend.ai_service import AIService


class TestAIService:
    """Test suite for AI Service functions"""

    @pytest.mark.asyncio
    async def test_generate_response_mock_mode(self):
        """Test generate_response in mock mode"""
        # Set mock mode
        os.environ["AI_DEV_MOCK"] = "1"

        try:
            # Create service instance
            service = AIService()

            # Test generate_response
            result = await service.generate_response("Test message")

            # Assertions
            assert isinstance(result, dict)
            assert "response" in result
            assert "confidence" in result
            assert "provider" in result
            assert result["provider"] == "mock"
            assert result["confidence"] == 0.8
            assert "Благодаря за въпроса" in result["response"]

        finally:
            # Clean up
            os.environ.pop("AI_DEV_MOCK", None)

    @pytest.mark.asyncio
    async def test_generate_response_no_provider(self):
        """Test generate_response when no provider is available"""
        # Mock ai_config to return no active provider
        with patch("backend.ai_service.get_ai_config") as mock_config:
            mock_config.get_active_provider.return_value = None

            service = AIService()
            result = await service.generate_response("Test message")

            assert result["provider"] == "error_fallback"
            assert result["confidence"] == 0.0
            assert "Извинявам се, възникна грешка" in result["response"]

    def test_calculate_confidence(self):
        """Test confidence calculation"""
        service = AIService()

        # Test short response
        assert service._calculate_confidence("Hi") == 0.3

        # Test medium response (len=29)
        assert service._calculate_confidence("This is medium length respons") == 0.6

        # Test apology response
        assert service._calculate_confidence("Извинявам се, не мога да помогна") == 0.4

        # Test relevant response
        assert (
            service._calculate_confidence("Регистрацията в HelpChain е безплатна")
            == 0.9
        )

        # Test normal response
        assert (
            service._calculate_confidence("Това е нормален отговор на български") == 0.7
        )

    def test_build_context(self):
        """Test context building"""
        service = AIService()

        context = service._build_context("Test question", None, "bg")

        assert "ПОСЛЕДНИ СЪОБЩЕНИЯ:" not in context  # No history
        assert "ВЪПРОС НА ПОТРЕБИТЕЛЯ: Test question" in context
        assert "ТВОЯТ ОТГОВОР (кратко, полезно, на български):" in context

    def test_build_context_with_history(self):
        """Test context building with conversation history"""
        service = AIService()

        history = [
            {"user_message": "Hello", "bot_response": "Hi there"},
            {"user_message": "How are you?", "bot_response": "I'm fine"},
        ]

        context = service._build_context(
            "Test question", {"conversation_history": history}, "bg"
        )

        assert "ПОСЛЕДНИ СЪОБЩЕНИЯ:" in context
        assert "Потребител: Hello" in context
        assert "Асистент: Hi there" in context

    def test_get_ai_status(self):
        """Test getting AI status"""
        service = AIService()
        status = service.get_ai_status()

        assert isinstance(status, dict)
        assert "service_ready" in status

    def test_sanitize_api_key_valid(self):
        """Test API key sanitization with valid key"""
        from backend.ai_service import _sanitize_api_key

        key = "sk-1234567890abcdef"
        cleaned, issues = _sanitize_api_key(key)

        assert cleaned == key
        assert issues == []

    def test_sanitize_api_key_placeholder(self):
        """Test API key sanitization with placeholder"""
        from backend.ai_service import _sanitize_api_key

        key = "ваш_openai_key"
        cleaned, issues = _sanitize_api_key(key)

        assert "placeholder" in " ".join(issues).lower()

    def test_safe_message(self):
        """Test _safe_message function"""
        from backend.ai_service import _safe_message

        exc = ValueError("Test error")
        msg = _safe_message(exc)

        assert "ValueError" in msg
        assert "Test error" in msg

    def test_sanitize_api_key_edge_cases(self):
        """Test API key sanitization with edge cases"""
        from backend.ai_service import _sanitize_api_key

        # Empty key
        cleaned, issues = _sanitize_api_key("")
        assert cleaned == ""
        assert "empty" in " ".join(issues).lower()

        # Non-string
        cleaned, issues = _sanitize_api_key(123)
        assert cleaned == ""
        assert "not a string" in " ".join(issues).lower()

        # Valid key
        key = "sk-1234567890abcdef"
        cleaned, issues = _sanitize_api_key(key)
        assert cleaned == key
        assert issues == []

    def test_build_context_with_empty_history(self):
        """Test context building with empty conversation history"""
        service = AIService()

        context = service._build_context(
            "Test question", {"conversation_history": []}, "bg"
        )

        assert "ПОСЛЕДНИ СЪОБЩЕНИЯ:" not in context
        assert "ВЪПРОС НА ПОТРЕБИТЕЛЯ: Test question" in context

    def test_build_context_with_long_history(self):
        """Test context building with more than 3 messages (should truncate)"""
        service = AIService()

        history = [
            {"user_message": f"Question {i}", "bot_response": f"Answer {i}"}
            for i in range(5)
        ]

        context = service._build_context(
            "New question", {"conversation_history": history}, "bg"
        )

        # Should only include last 3 messages
        assert "Question 2" not in context
        assert "Question 3" in context
        assert "Question 4" in context

    def test_build_context_foreign_language(self):
        """Test context building with non-Bulgarian language"""
        service = AIService()

        context = service._build_context("Hello", None, "en")

        assert "ЗАБЕЛЕЖКА: Потребителят пише на en" in context
        assert "Отговаряй ЗАДЪЛЖИТЕЛНО на български език" in context

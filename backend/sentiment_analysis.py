"""
Sentiment Analysis Service - AI-базиран анализ на обратна връзка
AI система за анализ на емоционалния тон на потребителските отзиви
"""

import time
from typing import Any

# Try relative imports first, fall back to absolute imports for standalone execution
try:
    from .ai_service import ai_service
    from .extensions import db
    from .models_with_analytics import Feedback
except ImportError:
    try:
        from ai_service import ai_service
        from extensions import db
        from models_with_analytics import Feedback
    except ImportError:
        # Fallback for testing
        ai_service = None
        db = None
        Feedback = None


class SentimentAnalysisService:
    """AI-базиран engine за анализ на емоционалния тон на обратната връзка"""

    def __init__(self):
        self.ai_service = ai_service

    def analyze_sentiment(self, text: str, language: str = "bg") -> dict[str, Any]:
        """
        Анализира емоционалния тон на текста

        Args:
            text: Текстът за анализ
            language: Език на текста ('bg' или 'en')

        Returns:
            dict с резултатите от анализа
        """
        if not text or not text.strip():
            return {
                "sentiment_score": 0.0,
                "sentiment_label": "neutral",
                "confidence": 0.0,
                "ai_processed": False,
                "error": "Empty text provided",
            }

        start_time = time.time()

        try:
            # Prepare prompt based on language
            if language.lower() == "bg":
                prompt = f"""
                Анализирай емоционалния тон на следната обратна връзка и определи:
                1. Емоционален тон: положителен, отрицателен или неутрален
                2. Числен резултат: от -1.0 (много отрицателен) до +1.0 (много положителен)
                3. Ниво на увереност: от 0.0 до 1.0

                Обратна връзка: "{text}"

                Отговори само с JSON в следния формат:
                {{
                    "sentiment": "positive|negative|neutral",
                    "score": число_от_-1_до_1,
                    "confidence": число_от_0_до_1,
                    "reasoning": "кратко_обяснение"
                }}
                """
            else:
                prompt = f"""
                Analyze the sentiment of the following feedback and determine:
                1. Emotional tone: positive, negative, or neutral
                2. Numerical score: from -1.0 (very negative) to +1.0 (very positive)
                3. Confidence level: from 0.0 to 1.0

                Feedback: "{text}"

                Respond only with JSON in this format:
                {{
                    "sentiment": "positive|negative|neutral",
                    "score": number_from_-1_to_1,
                    "confidence": number_from_0_to_1,
                    "reasoning": "brief_explanation"
                }}
                """

            # Get AI response
            ai_response = ai_service.generate_response(prompt, "system")

            if not ai_response or "response" not in ai_response:
                return self._fallback_sentiment_analysis(text)

            response_text = ai_response["response"]

            # Try to parse JSON response
            import json

            try:
                result = json.loads(response_text)
                sentiment = result.get("sentiment", "neutral").lower()
                score = float(result.get("score", 0.0))
                confidence = float(result.get("confidence", 0.5))

                # Validate and normalize values
                if sentiment not in ["positive", "negative", "neutral"]:
                    sentiment = "neutral"

                score = max(-1.0, min(1.0, score))
                confidence = max(0.0, min(1.0, confidence))

                processing_time = time.time() - start_time

                return {
                    "sentiment_score": score,
                    "sentiment_label": sentiment,
                    "sentiment_confidence": confidence,
                    "ai_processed": True,
                    "ai_provider": ai_response.get("provider", "unknown"),
                    "processing_time": processing_time,
                    "reasoning": result.get("reasoning", ""),
                }

            except (json.JSONDecodeError, ValueError, KeyError) as e:
                print(f"Failed to parse AI sentiment response: {e}")
                return self._fallback_sentiment_analysis(text)

        except Exception as e:
            print(f"Error in sentiment analysis: {e}")
            return self._fallback_sentiment_analysis(text)

    def _fallback_sentiment_analysis(self, text: str) -> dict[str, Any]:
        """
        Fallback sentiment analysis using simple keyword matching
        """
        text_lower = text.lower()

        # Bulgarian positive keywords
        positive_bg = [
            "отлично",
            "прекрасно",
            "благодаря",
            "помогнахте",
            "благодарим",
            "добре",
            "супер",
            "чудесно",
            "великолепно",
            "перфектно",
            "помощ",
            "подкрепа",
            "благодарен",
            "доволен",
            "успех",
        ]

        # Bulgarian negative keywords
        negative_bg = [
            "лошо",
            "проблем",
            "грешка",
            "не работи",
            "бавно",
            "разочарован",
            "ядосан",
            "неудовлетворен",
            "трудно",
            "неудобно",
            "нефункциониращо",
            "непомощ",
        ]

        # English keywords
        positive_en = [
            "excellent",
            "great",
            "thank you",
            "helpful",
            "amazing",
            "good",
            "super",
            "wonderful",
            "perfect",
            "awesome",
            "support",
            "grateful",
            "satisfied",
            "success",
        ]

        negative_en = [
            "bad",
            "problem",
            "error",
            "doesn't work",
            "slow",
            "disappointed",
            "angry",
            "unsatisfied",
            "difficult",
            "inconvenient",
            "broken",
            "useless",
        ]

        # Count positive and negative keywords
        positive_count = 0
        negative_count = 0

        for word in positive_bg + positive_en:
            positive_count += text_lower.count(word)

        for word in negative_bg + negative_en:
            negative_count += text_lower.count(word)

        # Calculate score
        total_keywords = positive_count + negative_count
        if total_keywords == 0:
            score = 0.0
            label = "neutral"
            confidence = 0.3
        else:
            score = (positive_count - negative_count) / max(total_keywords, 1)
            score = max(-1.0, min(1.0, score))

            if score > 0.1:
                label = "positive"
            elif score < -0.1:
                label = "negative"
            else:
                label = "neutral"

            confidence = min(
                0.7, total_keywords / 10.0
            )  # Higher confidence with more keywords

        return {
            "sentiment_score": score,
            "sentiment_label": label,
            "sentiment_confidence": confidence,
            "ai_processed": False,
            "ai_provider": "fallback",
            "processing_time": 0.001,
            "reasoning": f"Keyword analysis: {positive_count} positive, {negative_count} negative",
        }

    def analyze_feedback(self, feedback_id: int) -> dict[str, Any]:
        """
        Анализира конкретна обратна връзка по ID

        Args:
            feedback_id: ID на обратната връзка

        Returns:
            Резултатите от анализа
        """
        if not db or not Feedback:
            return {"error": "Database not available"}

        try:
            feedback = Feedback.query.get(feedback_id)
            if not feedback:
                return {"error": "Feedback not found"}

            if feedback.ai_processed:
                # Return existing analysis
                return {
                    "feedback_id": feedback.id,
                    "sentiment_score": feedback.sentiment_score,
                    "sentiment_label": feedback.sentiment_label,
                    "sentiment_confidence": feedback.sentiment_confidence,
                    "ai_processed": feedback.ai_processed,
                    "ai_provider": feedback.ai_provider,
                    "processing_time": feedback.ai_processing_time,
                    "already_analyzed": True,
                }

            # Analyze sentiment
            result = self.analyze_sentiment(feedback.message)

            # Update feedback record
            feedback.sentiment_score = result["sentiment_score"]
            feedback.sentiment_label = result["sentiment_label"]
            feedback.sentiment_confidence = result["sentiment_confidence"]
            feedback.ai_processed = result["ai_processed"]
            feedback.ai_provider = result.get("ai_provider")
            feedback.ai_processing_time = result.get("processing_time")

            db.session.commit()

            result["feedback_id"] = feedback.id
            return result

        except Exception as e:
            print(f"Error analyzing feedback {feedback_id}: {e}")
            db.session.rollback()
            return {"error": str(e)}

    def get_sentiment_analytics(self, days: int = 30) -> dict[str, Any]:
        """
        Получава аналитика за емоционалния тон на обратната връзка

        Args:
            days: Брой дни назад за анализ

        Returns:
            Статистики за емоционалния тон
        """
        if not db or not Feedback:
            return {"error": "Database not available"}

        try:
            from datetime import datetime, timedelta

            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Get all feedback in the period
            feedbacks = Feedback.query.filter(Feedback.timestamp >= cutoff_date).all()

            total_feedback = len(feedbacks)
            analyzed_feedback = len([f for f in feedbacks if f.ai_processed])

            if total_feedback == 0:
                return {
                    "total_feedback": 0,
                    "analyzed_feedback": 0,
                    "analysis_rate": 0.0,
                    "sentiment_distribution": {
                        "positive": 0,
                        "negative": 0,
                        "neutral": 0,
                    },
                    "average_score": 0.0,
                    "average_confidence": 0.0,
                    "trends": [],
                }

            # Sentiment distribution
            sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
            total_score = 0.0
            total_confidence = 0.0
            analyzed_count = 0

            for feedback in feedbacks:
                if feedback.sentiment_label:
                    sentiment_counts[feedback.sentiment_label] += 1

                if feedback.sentiment_score is not None:
                    total_score += feedback.sentiment_score
                    analyzed_count += 1

                if feedback.sentiment_confidence is not None:
                    total_confidence += feedback.sentiment_confidence

            # Calculate averages
            average_score = total_score / analyzed_count if analyzed_count > 0 else 0.0
            average_confidence = (
                total_confidence / analyzed_count if analyzed_count > 0 else 0.0
            )

            # Calculate percentages
            sentiment_percentages = {}
            for sentiment, count in sentiment_counts.items():
                sentiment_percentages[sentiment] = round(
                    (count / total_feedback) * 100, 1
                )

            # Simple trend data (last 7 days)
            trend_data = []
            for i in range(7):
                day_start = datetime.utcnow() - timedelta(days=i + 1)
                day_end = datetime.utcnow() - timedelta(days=i)

                day_feedbacks = [
                    f for f in feedbacks if day_start <= f.timestamp < day_end
                ]
                day_score = (
                    sum(f.sentiment_score for f in day_feedbacks if f.sentiment_score)
                    / len(day_feedbacks)
                    if day_feedbacks
                    else 0.0
                )

                trend_data.append(
                    {
                        "date": day_start.strftime("%Y-%m-%d"),
                        "feedback_count": len(day_feedbacks),
                        "average_score": round(day_score, 2),
                    }
                )

            trend_data.reverse()  # Oldest first

            return {
                "total_feedback": total_feedback,
                "analyzed_feedback": analyzed_feedback,
                "analysis_rate": round((analyzed_feedback / total_feedback) * 100, 1),
                "sentiment_distribution": sentiment_counts,
                "sentiment_percentages": sentiment_percentages,
                "average_score": round(average_score, 2),
                "average_confidence": round(average_confidence, 2),
                "trends": trend_data,
                "period_days": days,
            }

        except Exception as e:
            print(f"Error getting sentiment analytics: {e}")
            return {"error": str(e)}

    def batch_analyze_unprocessed_feedback(self, limit: int = 50) -> dict[str, Any]:
        """
        Анализира всички необработени обратни връзки

        Args:
            limit: Максимален брой за обработка

        Returns:
            Резултати от batch анализа
        """
        if not db or not Feedback:
            return {"error": "Database not available"}

        try:
            # Get unprocessed feedback
            unprocessed = (
                Feedback.query.filter_by(ai_processed=False).limit(limit).all()
            )

            processed_count = 0
            errors = []

            for feedback in unprocessed:
                try:
                    result = self.analyze_sentiment(feedback.message)

                    feedback.sentiment_score = result["sentiment_score"]
                    feedback.sentiment_label = result["sentiment_label"]
                    feedback.sentiment_confidence = result["sentiment_confidence"]
                    feedback.ai_processed = result["ai_processed"]
                    feedback.ai_provider = result.get("ai_provider")
                    feedback.ai_processing_time = result.get("processing_time")

                    processed_count += 1

                except Exception as e:
                    errors.append(f"Feedback {feedback.id}: {str(e)}")
                    continue

            db.session.commit()

            return {
                "processed": processed_count,
                "total_found": len(unprocessed),
                "errors": errors,
                "success_rate": (
                    round((processed_count / len(unprocessed)) * 100, 1)
                    if unprocessed
                    else 0.0
                ),
            }

        except Exception as e:
            print(f"Error in batch analysis: {e}")
            db.session.rollback()
            return {"error": str(e)}


# Global instance
sentiment_analysis_service = SentimentAnalysisService()

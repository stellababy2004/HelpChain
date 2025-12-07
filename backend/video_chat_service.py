"""
Video Chat Service for HelpChain
WebRTC-based video chat functionality
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from .models import User, VideoChatSession, db


def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


logger = logging.getLogger(__name__)

# In-memory storage for active sessions (in production, use Redis)
active_sessions = {}


class VideoChatService:
    """Service for managing video chat sessions"""

    @staticmethod
    def create_session(initiator_id: int, participant_id: int) -> VideoChatSession | None:
        """Create a new video chat session"""
        try:
            # Check if users exist
            initiator = db.session.get(User, initiator_id)
            participant = db.session.get(User, participant_id)

            if not initiator or not participant:
                logger.error(f"User not found: initiator={initiator_id}, participant={participant_id}")
                return None

            # Generate unique session ID
            session_id = str(uuid.uuid4())

            # Create session record
            session = VideoChatSession(
                session_id=session_id,
                initiator_id=initiator_id,
                participant_id=participant_id,
                status="pending",
            )

            db.session.add(session)
            db.session.commit()

            # Store in active sessions
            active_sessions[session_id] = {
                "session": session,
                "participants": {initiator_id, participant_id},
                "offer": None,
                "answer": None,
                "ice_candidates": [],
            }

            logger.info(f"Created video chat session: {session_id}")
            return session

        except Exception as e:
            logger.error(f"Error creating video chat session: {e}")
            db.session.rollback()
            return None

    @staticmethod
    def get_session(session_id: str) -> VideoChatSession | None:
        """Get session by ID"""
        return VideoChatSession.query.filter_by(session_id=session_id).first()

    @staticmethod
    def accept_session(session_id: str, user_id: int) -> bool:
        """Accept a video chat session"""
        try:
            session = VideoChatSession.query.filter_by(session_id=session_id).first()
            if not session or session.participant_id != user_id:
                return False

            session.status = "active"
            session.started_at = utc_now()
            db.session.commit()

            if session_id in active_sessions:
                active_sessions[session_id]["status"] = "active"

            logger.info(f"Accepted video chat session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error accepting video chat session: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def end_session(session_id: str, user_id: int) -> bool:
        """End a video chat session"""
        try:
            session = VideoChatSession.query.filter_by(session_id=session_id).first()
            if not session or user_id not in [
                session.initiator_id,
                session.participant_id,
            ]:
                return False

            session.status = "completed"
            session.ended_at = utc_now()
            if session.started_at:
                session.duration = int((session.ended_at - session.started_at).total_seconds())
            db.session.commit()

            # Remove from active sessions
            if session_id in active_sessions:
                del active_sessions[session_id]

            logger.info(f"Ended video chat session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error ending video chat session: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def store_offer(session_id: str, offer: dict[str, Any]) -> bool:
        """Store WebRTC offer"""
        if session_id in active_sessions:
            active_sessions[session_id]["offer"] = offer
            return True
        return False

    @staticmethod
    def store_answer(session_id: str, answer: dict[str, Any]) -> bool:
        """Store WebRTC answer"""
        if session_id in active_sessions:
            active_sessions[session_id]["answer"] = answer
            return True
        return False

    @staticmethod
    def add_ice_candidate(session_id: str, candidate: dict[str, Any]) -> bool:
        """Add ICE candidate"""
        if session_id in active_sessions:
            active_sessions[session_id]["ice_candidates"].append(candidate)
            return True
        return False

    @staticmethod
    def get_session_data(session_id: str) -> dict[str, Any] | None:
        """Get session data for WebRTC signaling"""
        return active_sessions.get(session_id)

    @staticmethod
    def get_user_sessions(user_id: int) -> list:
        """Get all sessions for a user"""
        return (
            VideoChatSession.query.filter(
                db.or_(
                    VideoChatSession.initiator_id == user_id,
                    VideoChatSession.participant_id == user_id,
                )
            )
            .order_by(VideoChatSession.created_at.desc())
            .all()
        )

    @staticmethod
    def get_active_sessions(user_id: int) -> list:
        """Get active sessions for a user"""
        return VideoChatSession.query.filter(
            db.or_(
                VideoChatSession.initiator_id == user_id,
                VideoChatSession.participant_id == user_id,
            ),
            VideoChatSession.status.in_(["pending", "active"]),
        ).all()


# Global instance
video_chat_service = VideoChatService()

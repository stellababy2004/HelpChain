import logging
from datetime import datetime, timezone

logger = logging.getLogger("security")


def log_security_event(event_type: str, **fields):
    """
    Minimal, dependency-free security logger.
    Keeps app startup resilient in constrained deploy environments.
    """
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **fields,
    }
    logger.info("[SECURITY] %s", payload)

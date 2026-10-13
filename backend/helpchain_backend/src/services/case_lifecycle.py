"""Shared lifecycle guards for operational Case mutations."""

from __future__ import annotations

from typing import Any

from werkzeug.exceptions import Conflict


CLOSED_CASE_STATUS = "closed"
CLOSED_CASE_READ_ONLY_MESSAGE = "Closed cases are operationally read-only."


def case_is_closed(case_row: Any) -> bool:
    """Return whether the case has reached the closed terminal state."""
    return (
        (getattr(case_row, "status", None) or "").strip().lower()
        == CLOSED_CASE_STATUS
    )


def require_case_operationally_writable(case_row: Any) -> None:
    """Reject normal operational writes once a Case is closed."""
    if case_is_closed(case_row):
        raise Conflict(description=CLOSED_CASE_READ_ONLY_MESSAGE)

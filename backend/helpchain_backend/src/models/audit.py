from datetime import UTC, datetime, timezone


def utc_now() -> datetime:
	"""Return a naive UTC datetime for compatibility with the rest of the codebase.

	This file no longer contains the AuditLog model (it lives in `models.py`).
	We keep this small helper to preserve backward compatibility for imports.
	"""
	return datetime.now(UTC).replace(tzinfo=None)

# Този файл вече не съдържа модел AuditLog. Използвайте дефиницията от models.py!

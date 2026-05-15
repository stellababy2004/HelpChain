from datetime import UTC, datetime


def test_format_datetime_fr_converts_utc_to_paris(app):
    fmt = app.jinja_env.filters["format_datetime_fr"]

    value = datetime(2026, 5, 15, 6, 5, 56, tzinfo=UTC)

    assert fmt(value) == "15 mai 2026 · 08:05"


def test_format_datetime_fr_handles_none_and_naive_utc(app):
    fmt = app.jinja_env.filters["format_datetime_fr"]

    assert fmt(None) == "—"
    assert fmt(datetime(2026, 5, 15, 6, 5, 56)) == "15 mai 2026 · 08:05"


def test_format_datetime_fr_accepts_iso_strings(app):
    fmt = app.jinja_env.filters["format_datetime_fr"]

    assert fmt("2026-05-15T06:05:56+00:00") == "15 mai 2026 · 08:05"

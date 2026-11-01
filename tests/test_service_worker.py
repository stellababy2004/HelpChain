from pathlib import Path


def test_service_worker_offline_fallback_always_returns_response():
    sources = [
        Path("static/sw.js").read_text(encoding="utf-8"),
        Path("backend/helpchain_backend/src/static/sw.js").read_text(encoding="utf-8"),
    ]

    for source in sources:
        assert "event.respondWith(" in source
        assert "caches.match(event.request).then" in source
        assert 'new Response("", { status: 503, statusText: "Offline" })' in source

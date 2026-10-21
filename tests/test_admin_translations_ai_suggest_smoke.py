import sys
import types

import pytest


def test_admin_translations_ai_suggest_uses_hf_when_available(authenticated_admin_client, monkeypatch):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._ui_registry_get",
        lambda _key: {"default": "Creer un dossier", "domain": "public"},
    )
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._hf_translate_fr_to",
        lambda locale, text: "Fall erstellen" if locale == "de" else None,
    )

    resp = authenticated_admin_client.post(
        "/admin/translations/ai-suggest",
        data={"key": "case_create", "locale": "de", "provider": "hf_local"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload is not None
    assert payload["provider"] == "hf_local"
    suggestions = payload.get("suggestions") or []
    assert len(suggestions) >= 1
    assert suggestions[0]["text"] == "Fall erstellen"


@pytest.mark.parametrize(
    "locale,model_name,revision",
    [
        (
            "en",
            "Helsinki-NLP/opus-mt-fr-en",
            "c4aed37b318c763fd177aa449b44e3b783cc6c02",
        ),
        (
            "de",
            "Helsinki-NLP/opus-mt-fr-de",
            "db80d261062d75a60e1d4897f13673313a33d50b",
        ),
        (
            "bg",
            "Helsinki-NLP/opus-mt-fr-bg",
            "617ad12c5336703f8ec16fec90d9cc5eab920339",
        ),
    ],
)
def test_hf_translator_pins_tokenizer_and_model_revision(
    monkeypatch, locale, model_name, revision
):
    from backend.helpchain_backend.src.routes import admin

    calls = []

    class FakeTokenizer:
        @classmethod
        def from_pretrained(cls, requested_model, **kwargs):
            calls.append(("tokenizer", requested_model, kwargs))
            return cls()

        def __call__(self, text, **kwargs):
            return {"input": text}

        def decode(self, generated, **kwargs):
            return "translated"

    class FakeModel:
        @classmethod
        def from_pretrained(cls, requested_model, **kwargs):
            calls.append(("model", requested_model, kwargs))
            return cls()

        def generate(self, **kwargs):
            return [[1]]

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        types.SimpleNamespace(
            MarianMTModel=FakeModel,
            MarianTokenizer=FakeTokenizer,
        ),
    )
    monkeypatch.setattr(admin, "_HF_TRANSLATORS", {})
    monkeypatch.setattr(admin, "_HF_TRANSLATOR_FAILED", set())

    assert admin._hf_translate_fr_to(locale=locale, text="Bonjour") == "translated"
    assert calls == [
        ("tokenizer", model_name, {"revision": revision}),
        ("model", model_name, {"revision": revision}),
    ]


def test_hf_translator_does_not_load_model_for_unsupported_locale(monkeypatch):
    from backend.helpchain_backend.src.routes import admin

    calls = []
    fake_transformers = types.SimpleNamespace(
        MarianMTModel=types.SimpleNamespace(
            from_pretrained=lambda *args, **kwargs: calls.append("model")
        ),
        MarianTokenizer=types.SimpleNamespace(
            from_pretrained=lambda *args, **kwargs: calls.append("tokenizer")
        ),
    )
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    assert admin._hf_translate_fr_to(locale="es", text="Bonjour") is None
    assert calls == []


def test_admin_translations_ai_suggest_falls_back_to_rules(authenticated_admin_client, monkeypatch):
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._ui_registry_get",
        lambda _key: {"default": "Demande", "domain": "public"},
    )
    monkeypatch.setattr(
        "backend.helpchain_backend.src.routes.admin._hf_translate_fr_to",
        lambda locale, text: None,
    )

    resp = authenticated_admin_client.post(
        "/admin/translations/ai-suggest",
        data={"key": "request_label", "locale": "de", "provider": "hf_local"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload is not None
    suggestions = payload.get("suggestions") or []
    assert len(suggestions) >= 1

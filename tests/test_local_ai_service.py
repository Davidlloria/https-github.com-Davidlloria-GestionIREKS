from __future__ import annotations

from app.services.api_settings_service import ApiSettingsService
from app.services.local_ai_service import LocalAIService
from app.services.local_ai_settings_service import LocalAISettingsService


def test_local_ai_settings_round_trip(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "api_config.json"
    monkeypatch.setattr(ApiSettingsService, "CONFIG_PATH", config_path)
    settings = LocalAISettingsService()

    settings.save(enabled=True, base_url="http://localhost:8080/v1", model="local-model")

    assert settings.load() == {
        "enabled": True,
        "base_url": "http://localhost:8080/v1",
        "model": "local-model",
    }


def test_local_ai_settings_uses_native_ollama_url_by_default(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "api_config.json"
    monkeypatch.setattr(ApiSettingsService, "CONFIG_PATH", config_path)

    assert LocalAISettingsService().load()["base_url"] == "http://127.0.0.1:11434"


def test_local_ai_rejects_non_loopback_urls(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="https://example.com/v1", model="model")
    monkeypatch.setattr(service, "_post_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))

    result = service.generate_process("Resume estos datos")

    assert result.ok is False
    assert "127.0.0.1" in result.message


def test_local_ai_uses_native_ollama_chat_endpoint(monkeypatch) -> None:
    service = LocalAIService(
        enabled=True,
        base_url="http://127.0.0.1:11434/v1/",
        model="qwen3.5:4b",
    )
    captured: dict[str, object] = {}

    def fake_post(url: str, payload: dict):
        captured["url"] = url
        captured["payload"] = payload
        return {"message": {"content": "Respuesta local"}}

    monkeypatch.setattr(service, "_post_json", fake_post)

    result = service.generate_process("Resume estos datos")

    assert result.ok is True
    assert result.text == "Respuesta local"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"]["model"] == "qwen3.5:4b"
    assert captured["payload"]["think"] is False
    assert captured["payload"]["options"] == {"temperature": 0.2, "num_predict": 1200}


def test_local_ai_json_mode_requests_native_ollama_json(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="http://localhost:8080/v1", model="local-model")
    captured: dict[str, object] = {}

    def fake_post(_url: str, payload: dict):
        captured.update(payload)
        return {"message": {"content": '{"query_type":"general"}'}}

    monkeypatch.setattr(service, "_post_json", fake_post)

    result = service.generate_json("Devuelve JSON")

    assert result.ok is True
    assert captured["format"] == "json"
    assert "response_format" not in captured
    assert captured["think"] is False
    assert captured["options"] == {"temperature": 0.0, "num_predict": 400}


def test_local_ai_json_mode_accepts_a_strict_schema(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="http://localhost:11434", model="local-model")
    captured: dict[str, object] = {}
    schema = {
        "type": "object",
        "properties": {"query_type": {"type": "string", "enum": ["general"]}},
        "required": ["query_type"],
        "additionalProperties": False,
    }

    def fake_post(_url: str, payload: dict):
        captured.update(payload)
        return {"message": {"content": '{"query_type":"general"}'}}

    monkeypatch.setattr(service, "_post_json", fake_post)

    result = service.generate_json("Devuelve JSON", schema=schema)

    assert result.ok is True
    assert captured["format"] == schema


def test_local_ai_returns_controlled_message_for_empty_ollama_content(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="http://localhost:11434", model="local-model")
    monkeypatch.setattr(service, "_post_json", lambda *_args: {"message": {"content": ""}})

    result = service.test_connection()

    assert result.ok is False
    assert result.text == ""
    assert "contenido" in result.message.lower()

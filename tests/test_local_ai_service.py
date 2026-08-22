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


def test_local_ai_rejects_non_loopback_urls(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="https://example.com/v1", model="model")
    monkeypatch.setattr(service, "_post_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))

    result = service.generate_process("Resume estos datos")

    assert result.ok is False
    assert "127.0.0.1" in result.message


def test_local_ai_uses_openai_compatible_chat_endpoint(monkeypatch) -> None:
    service = LocalAIService(
        enabled=True,
        base_url="http://127.0.0.1:11434/v1/",
        model="qwen3.5:4b",
    )
    captured: dict[str, object] = {}

    def fake_post(url: str, payload: dict):
        captured["url"] = url
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "Respuesta local"}}]}

    monkeypatch.setattr(service, "_post_json", fake_post)

    result = service.generate_process("Resume estos datos")

    assert result.ok is True
    assert result.text == "Respuesta local"
    assert captured["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert captured["payload"]["model"] == "qwen3.5:4b"


def test_local_ai_json_mode_requests_json_object(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="http://localhost:8080/v1", model="local-model")
    captured: dict[str, object] = {}

    def fake_post(_url: str, payload: dict):
        captured.update(payload)
        return {"choices": [{"message": {"content": '{"query_type":"general"}'}}]}

    monkeypatch.setattr(service, "_post_json", fake_post)

    result = service.generate_json("Devuelve JSON")

    assert result.ok is True
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["temperature"] == 0.0

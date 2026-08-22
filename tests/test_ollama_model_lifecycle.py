from __future__ import annotations

from app.services.local_ai_service import LocalAIService, OllamaModelLifecycle
from app import main


def test_disabled_lifecycle_makes_no_requests(monkeypatch) -> None:
    service = LocalAIService(enabled=False)
    lifecycle = OllamaModelLifecycle(service)
    monkeypatch.setattr(lifecycle, "_get_json", lambda *_: (_ for _ in ()).throw(AssertionError()))
    lifecycle.preload_async()
    lifecycle.unload()


def test_preload_uses_tags_and_native_chat_payload(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="http://127.0.0.1:11434/v1", model="model")
    lifecycle = OllamaModelLifecycle(service)
    calls = []
    monkeypatch.setattr(lifecycle, "_get_json", lambda url: calls.append(("get", url)) or {})
    monkeypatch.setattr(service, "_post_json", lambda url, payload: calls.append(("post", url, payload)) or {})
    lifecycle._preload()
    assert calls[0] == ("get", "http://127.0.0.1:11434/api/tags")
    assert calls[1][1] == "http://127.0.0.1:11434/api/chat"
    assert calls[1][2] == {"model": "model", "messages": [], "stream": False, "think": False, "keep_alive": -1}


def test_unload_is_controlled_when_connection_fails(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="http://localhost:11434", model="model")
    lifecycle = OllamaModelLifecycle(service)
    monkeypatch.setattr(service, "_post_json", lambda *_: (_ for _ in ()).throw(ConnectionError()))
    lifecycle.unload()
    assert "descargar" in lifecycle.status


def test_unload_uses_generate_with_zero_keep_alive(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="http://localhost:11434", model="model")
    lifecycle = OllamaModelLifecycle(service)
    captured = {}
    monkeypatch.setattr(service, "_post_json", lambda url, payload: captured.update(url=url, payload=payload) or {})
    lifecycle.unload()
    assert captured == {"url": "http://localhost:11434/api/generate", "payload": {"model": "model", "stream": False, "keep_alive": 0}}


def test_application_connects_lifecycle_once_and_schedules_preload(monkeypatch) -> None:
    class Signal:
        def __init__(self) -> None:
            self.calls = []

        def connect(self, callback) -> None:
            self.calls.append(callback)

    class AppDouble:
        def __init__(self) -> None:
            self.values = {}
            self.aboutToQuit = Signal()

        def property(self, key):
            return self.values.get(key)

        def setProperty(self, key, value) -> None:
            self.values[key] = value

    scheduled = []
    app = AppDouble()
    monkeypatch.setattr(main.QTimer, "singleShot", lambda delay, callback: scheduled.append((delay, callback)))
    first = main._connect_local_ai_lifecycle(app)
    second = main._connect_local_ai_lifecycle(app)
    assert len(app.aboutToQuit.calls) == 1
    assert len(scheduled) == 1
    assert first is not second

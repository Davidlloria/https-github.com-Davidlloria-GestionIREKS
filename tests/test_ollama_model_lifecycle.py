from __future__ import annotations

from app.services.local_ai_service import LocalAIService, OllamaModelLifecycle
from app import main


class _FakeProcess:
    def __init__(self, *, return_code=None) -> None:
        self.return_code = return_code
        self.terminated = False
        self.killed = False
        self.wait_timeouts = []

    def poll(self):
        return self.return_code

    def terminate(self) -> None:
        self.terminated = True
        self.return_code = 0

    def kill(self) -> None:
        self.killed = True
        self.return_code = -1

    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        return self.return_code


def test_disabled_lifecycle_makes_no_requests(monkeypatch) -> None:
    service = LocalAIService(enabled=False)
    lifecycle = OllamaModelLifecycle(service)
    monkeypatch.setattr(lifecycle, "_get_json", lambda *_: (_ for _ in ()).throw(AssertionError()))
    lifecycle.preload_async()
    assert lifecycle.status_code == "disabled"
    assert lifecycle.status == "IA local desactivada"
    lifecycle.unload()


def test_preload_uses_tags_and_native_chat_payload(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="http://127.0.0.1:11434/v1", model="model")
    lifecycle = OllamaModelLifecycle(
        service,
        process_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    calls = []
    monkeypatch.setattr(lifecycle, "_get_json", lambda url: calls.append(("get", url)) or {})

    def post_json(url, payload):
        assert lifecycle.status_code == "loading"
        calls.append(("post", url, payload))
        return {}

    monkeypatch.setattr(service, "_post_json", post_json)
    lifecycle._preload()
    assert calls[0] == ("get", "http://127.0.0.1:11434/api/tags")
    assert calls[1][1] == "http://127.0.0.1:11434/api/chat"
    assert calls[1][2] == {"model": "model", "messages": [], "stream": False, "think": False, "keep_alive": -1}
    assert lifecycle.status_code == "ready"
    assert lifecycle.status == "IA local disponible"


def test_preload_exposes_not_installed_status_when_ollama_is_missing(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="http://127.0.0.1:11434", model="model")
    lifecycle = OllamaModelLifecycle(service)
    monkeypatch.setattr(lifecycle, "_get_json", lambda *_: (_ for _ in ()).throw(ConnectionError()))
    monkeypatch.setattr(lifecycle, "_resolve_ollama_executable", lambda: "")

    lifecycle._preload()

    assert lifecycle.status_code == "not_installed"
    assert lifecycle.status == "Ollama no está instalado"


def test_preload_starts_missing_server_and_stops_only_owned_process(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="http://127.0.0.1:11555/v1", model="model")
    process = _FakeProcess()
    process_calls = []

    def process_factory(args, **kwargs):
        process_calls.append((args, kwargs))
        return process

    lifecycle = OllamaModelLifecycle(
        service,
        startup_timeout=1.0,
        poll_interval=0.01,
        ollama_executable="C:/Ollama/ollama.exe",
        process_factory=process_factory,
    )
    health_checks = []

    def get_json(url):
        health_checks.append(url)
        if len(health_checks) == 1:
            raise ConnectionError
        return {}

    post_calls = []
    monkeypatch.setattr(lifecycle, "_get_json", get_json)
    monkeypatch.setattr(service, "_post_json", lambda url, payload: post_calls.append((url, payload)) or {})

    lifecycle._preload()

    assert lifecycle.status_code == "ready"
    assert process_calls[0][0] == ["C:/Ollama/ollama.exe", "serve"]
    assert process_calls[0][1]["env"]["OLLAMA_HOST"] == "127.0.0.1:11555"
    assert lifecycle._server_process is process

    lifecycle.unload()

    assert process.terminated is True
    assert process.killed is False
    assert lifecycle._server_process is None
    assert len(post_calls) == 2


def test_preload_reports_unavailable_when_started_process_exits(monkeypatch) -> None:
    service = LocalAIService(enabled=True, base_url="http://127.0.0.1:11434", model="model")
    process = _FakeProcess(return_code=1)
    lifecycle = OllamaModelLifecycle(
        service,
        startup_timeout=1.0,
        poll_interval=0.01,
        ollama_executable="C:/Ollama/ollama.exe",
        process_factory=lambda *_args, **_kwargs: process,
    )
    monkeypatch.setattr(lifecycle, "_get_json", lambda *_: (_ for _ in ()).throw(ConnectionError()))

    lifecycle._preload()

    assert lifecycle.status_code == "unavailable"
    assert lifecycle.status == "IA local no disponible"
    assert lifecycle._server_process is None


def test_lifecycle_health_timeout_does_not_shorten_model_request_timeout() -> None:
    service = LocalAIService(enabled=True, timeout=180.0)

    lifecycle = OllamaModelLifecycle(service, timeout=2.0)

    assert lifecycle.timeout == 2.0
    assert lifecycle.service.timeout == 180.0


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

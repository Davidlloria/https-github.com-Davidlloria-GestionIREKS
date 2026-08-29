from __future__ import annotations

import math
from urllib.error import HTTPError

import pytest

from app.services.local_embedding_service import (
    DEFAULT_EMBEDDING_MODEL,
    MAX_EMBEDDING_BATCH_SIZE,
    LocalEmbeddingService,
)


def _service(**kwargs) -> LocalEmbeddingService:
    return LocalEmbeddingService(enabled=True, base_url="http://127.0.0.1:11434", **kwargs)


class _Settings:
    def __init__(self, embedding_model=None):
        self.embedding_model = embedding_model

    def load(self):
        return {
            "enabled": False,
            "base_url": "http://localhost:11434",
            "embedding_model": self.embedding_model,
        }


def test_uses_native_ollama_endpoint_and_exact_payload(monkeypatch) -> None:
    service = _service(model="embeddinggemma")
    captured = {}
    monkeypatch.setattr(
        service, "_post_json",
        lambda url, payload: captured.update(url=url, payload=payload) or {"embeddings": [[3, 4]]},
    )

    result = service.embed(["texto"])

    assert result.ok and result.vectors == ((0.6, 0.8),)
    assert captured == {
        "url": "http://127.0.0.1:11434/api/embed",
        "payload": {"model": "embeddinggemma", "input": ["texto"], "truncate": True},
    }
    assert "/v1/embeddings" not in captured["url"]


def test_strips_v1_from_native_base(monkeypatch) -> None:
    service = LocalEmbeddingService(
        enabled=True, base_url="http://localhost:11434/v1", model="embed"
    )
    captured = {}
    monkeypatch.setattr(service, "_post_json", lambda url, _payload: captured.update(url=url) or {"embeddings": [[1.0]]})
    assert service.embed(["x"]).ok
    assert captured["url"] == "http://localhost:11434/api/embed"


@pytest.mark.parametrize("url", ["https://localhost:11434", "http://example.com", "file:///tmp/x"])
def test_rejects_non_local_http_urls(url, monkeypatch) -> None:
    service = LocalEmbeddingService(enabled=True, base_url=url, model="embed")
    monkeypatch.setattr(service, "_post_json", lambda *_: pytest.fail("network called"))
    assert service.embed(["x"]).ok is False


def test_configuration_and_input_validation(monkeypatch) -> None:
    monkeypatch.setattr(LocalEmbeddingService, "_post_json", lambda *_: pytest.fail("network called"))
    assert not _service(model="").embed(["x"]).ok
    assert not LocalEmbeddingService(enabled=False, model="x").embed(["x"]).ok
    assert not _service().embed([]).ok
    assert not _service().embed("texto").ok
    assert not _service().embed([" "]).ok
    assert not _service().embed(["x"] * (MAX_EMBEDDING_BATCH_SIZE + 1)).ok


def test_embedding_model_precedence_is_explicit_environment_saved_default(monkeypatch) -> None:
    monkeypatch.setenv("GESTION_IREKS_EMBEDDING_MODEL", "env-model")
    assert _service(settings_service=_Settings("saved-model")).model == "env-model"
    assert _service(model="explicit", settings_service=_Settings("saved-model")).model == "explicit"
    monkeypatch.delenv("GESTION_IREKS_EMBEDDING_MODEL")
    assert _service(settings_service=_Settings("saved-model")).model == "saved-model"
    assert _service(settings_service=_Settings()).model == DEFAULT_EMBEDDING_MODEL


@pytest.mark.parametrize(
    "response",
    [
        {"embeddings": []},
        {"embeddings": [[]]},
        {"embeddings": [[1, 2], [1]]},
        {"embeddings": [[0, 0]]},
        {"embeddings": [[math.inf]]},
        {"embeddings": [["bad"]]},
    ],
)
def test_rejects_partial_or_invalid_vectors(response, monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(service, "_post_json", lambda *_: response)
    inputs = ["a", "b"] if len(response.get("embeddings", [])) == 2 else ["a"]
    result = service.embed(inputs)
    assert result.ok is False
    assert result.vectors == () and result.dimension == 0


def test_reports_missing_model_without_downloading(monkeypatch) -> None:
    service = _service(model="missing-model")
    error = HTTPError("http://localhost/api/embed", 404, "not found", {}, None)
    monkeypatch.setattr(service, "_post_json", lambda *_: (_ for _ in ()).throw(error))
    result = service.embed(["x"])
    assert not result.ok
    assert "missing-model" in result.message
    assert "instalado" in result.message

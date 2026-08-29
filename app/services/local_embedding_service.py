from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from app.services.local_ai_settings_service import LocalAISettingsService


DEFAULT_EMBEDDING_MODEL = LocalAISettingsService.DEFAULT_EMBEDDING_MODEL
MAX_EMBEDDING_BATCH_SIZE = 16


@dataclass(frozen=True)
class LocalEmbeddingResult:
    ok: bool
    vectors: tuple[tuple[float, ...], ...] = ()
    model: str = ""
    dimension: int = 0
    message: str = ""


class LocalEmbeddingService:
    """Small, local-only client for Ollama's native embedding endpoint."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
        settings_service: LocalAISettingsService | None = None,
    ) -> None:
        settings = (settings_service or LocalAISettingsService()).load()
        self.enabled = bool(settings.get("enabled")) if enabled is None else bool(enabled)
        self.base_url = str(
            base_url or settings.get("base_url") or LocalAISettingsService.DEFAULT_BASE_URL
        ).rstrip("/")
        configured_model = os.getenv("GESTION_IREKS_EMBEDDING_MODEL")
        self.model = str(
            model
            if model is not None
            else configured_model
            or settings.get("embedding_model")
            or DEFAULT_EMBEDDING_MODEL
        ).strip()
        self.timeout = float(timeout)

    def embed(self, inputs: Iterable[str]) -> LocalEmbeddingResult:
        if isinstance(inputs, (str, bytes)):
            return self._error("La entrada debe ser un lote de textos.")
        try:
            texts = tuple(inputs)
        except TypeError:
            return self._error("La entrada de embeddings no es válida.")
        configuration_error = self._validate_configuration()
        if configuration_error:
            return self._error(configuration_error)
        if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
            return self._error("Se requiere al menos un texto no vacío.")
        if len(texts) > MAX_EMBEDDING_BATCH_SIZE:
            return self._error(
                f"El lote supera el máximo de {MAX_EMBEDDING_BATCH_SIZE} textos."
            )

        payload = {"model": self.model, "input": list(texts), "truncate": True}
        try:
            response = self._post_json(f"{self._native_base_url()}/api/embed", payload)
        except (HTTPError, URLError, OSError, ValueError) as exc:
            detail = str(exc)
            if isinstance(exc, HTTPError) and exc.code == 404 or "not found" in detail.casefold():
                return self._error(
                    f"El modelo local '{self.model}' no está instalado en Ollama."
                )
            return self._error("No se pudo obtener el embedding desde la IA local.")

        raw_vectors = response.get("embeddings")
        if not isinstance(raw_vectors, list) or len(raw_vectors) != len(texts):
            return self._error("Ollama devolvió una cantidad de vectores incorrecta.")
        normalized: list[tuple[float, ...]] = []
        dimension = 0
        for raw_vector in raw_vectors:
            if not isinstance(raw_vector, list) or not raw_vector:
                return self._error("Ollama devolvió un vector vacío o inválido.")
            try:
                vector = tuple(float(value) for value in raw_vector)
            except (TypeError, ValueError):
                return self._error("Ollama devolvió valores de vector inválidos.")
            if any(not math.isfinite(value) for value in vector):
                return self._error("Ollama devolvió valores de vector no finitos.")
            if dimension and len(vector) != dimension:
                return self._error("Ollama devolvió vectores con dimensiones distintas.")
            dimension = dimension or len(vector)
            norm = math.sqrt(sum(value * value for value in vector))
            if not math.isfinite(norm) or norm == 0.0:
                return self._error("Ollama devolvió un vector de norma cero.")
            normalized.append(tuple(value / norm for value in vector))
        return LocalEmbeddingResult(
            ok=True,
            vectors=tuple(normalized),
            model=self.model,
            dimension=dimension,
        )

    def _error(self, message: str) -> LocalEmbeddingResult:
        return LocalEmbeddingResult(ok=False, model=self.model, message=message)

    def _validate_configuration(self) -> str:
        if not self.enabled:
            return "El servicio de IA local está desactivado."
        parsed = urlsplit(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            return "La URL de embeddings debe usar HTTP local (127.0.0.1, localhost o ::1)."
        if not self.model:
            return "El modelo de embeddings no puede estar vacío."
        if self.timeout <= 0:
            return "El tiempo de espera debe ser mayor que cero."
        return ""

    def _native_base_url(self) -> str:
        base_url = self.base_url.rstrip("/")
        return base_url[:-3].rstrip("/") if base_url.casefold().endswith("/v1") else base_url

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        opener = build_opener(ProxyHandler({}))
        with opener.open(request, timeout=self.timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Respuesta JSON inválida.")
        return decoded

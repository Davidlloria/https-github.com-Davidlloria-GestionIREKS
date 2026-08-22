from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from app.services.local_ai_settings_service import LocalAISettingsService


@dataclass
class LocalAIResult:
    ok: bool
    text: str
    message: str = ""


class LocalAIService:
    """Small client for a loopback Ollama local model server."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        cfg = LocalAISettingsService().load()
        self.enabled = bool(cfg.get("enabled", False) if enabled is None else enabled)
        self.base_url = str(base_url or cfg.get("base_url") or LocalAISettingsService.DEFAULT_BASE_URL).rstrip("/")
        self.model = str(model or cfg.get("model") or LocalAISettingsService.DEFAULT_MODEL).strip()
        self.timeout = float(timeout)

    def generate_process(self, prompt: str) -> LocalAIResult:
        src = str(prompt or "").strip()
        if not src:
            return LocalAIResult(False, "", "Prompt vacío.")
        return self.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Eres el asistente local de GestionIREKS. Responde solo con los datos "
                        "aportados, no inventes información y no propongas escrituras en la base de datos."
                    ),
                },
                {"role": "user", "content": src},
            ],
            temperature=0.2,
            max_tokens=1200,
        )

    def generate_json(self, prompt: str, *, schema: dict[str, Any] | None = None) -> LocalAIResult:
        src = str(prompt or "").strip()
        if not src:
            return LocalAIResult(False, "", "Prompt vacío.")
        return self.chat(
            [{"role": "user", "content": src}],
            temperature=0.0,
            max_tokens=400,
            json_mode=True,
            json_schema=schema,
        )

    def test_connection(self) -> LocalAIResult:
        return self.chat(
            [{"role": "user", "content": "Responde únicamente con la palabra OK."}],
            temperature=0.0,
            max_tokens=8,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
        json_schema: dict[str, Any] | None = None,
    ) -> LocalAIResult:
        if not self.enabled:
            return LocalAIResult(False, "", "La IA local no está activada en Configuración > API.")
        validation_error = self._validate_configuration()
        if validation_error:
            return LocalAIResult(False, "", validation_error)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": float(temperature),
                "num_predict": int(max_tokens),
            },
        }
        if json_mode:
            payload["format"] = json_schema if json_schema is not None else "json"

        try:
            parsed = self._post_json(self._chat_url(), payload)
            message = parsed.get("message") or {}
            text = str((message or {}).get("content") or "").strip()
            if not text:
                return LocalAIResult(False, "", "La IA local no devolvió contenido.")
            return LocalAIResult(True, text, "Respuesta generada con IA local.")
        except Exception as exc:  # noqa: BLE001
            return LocalAIResult(False, "", f"No se pudo consultar la IA local.\n{exc}")

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=raw, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")
        opener = build_opener(ProxyHandler({}))
        with opener.open(request, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body or "{}")
        return parsed if isinstance(parsed, dict) else {}

    def _validate_configuration(self) -> str:
        parsed = urlsplit(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            return "La URL de IA local debe usar HTTP y apuntar a 127.0.0.1, localhost o ::1."
        if not self.model:
            return "Indica el nombre del modelo de IA local."
        return ""

    def _chat_url(self) -> str:
        return f"{self._native_base_url()}/api/chat"

    def _native_base_url(self) -> str:
        base_url = self.base_url.rstrip("/")
        return base_url[:-3].rstrip("/") if base_url.lower().endswith("/v1") else base_url


class OllamaModelLifecycle:
    """Keeps the configured local Ollama model warm while the desktop app is open."""

    def __init__(self, service: LocalAIService | None = None, *, timeout: float = 2.0) -> None:
        self.service = service or LocalAIService(timeout=timeout)
        self.timeout = float(timeout)
        self.service.timeout = min(float(self.service.timeout), self.timeout)
        self.status = ""
        self._closing = threading.Event()
        self._operation_lock = threading.Lock()

    def preload_async(self) -> None:
        if not self.service.enabled or self._closing.is_set():
            return
        threading.Thread(target=self._preload, name="ollama-model-preload", daemon=True).start()

    def _preload(self) -> None:
        if self._closing.is_set():
            return
        with self._operation_lock:
            if self._closing.is_set():
                return
            try:
                self._get_json(f"{self.service._native_base_url()}/api/tags")
                if self._closing.is_set():
                    return
                self.service._post_json(
                    self.service._chat_url(),
                    {"model": self.service.model, "messages": [], "stream": False, "think": False, "keep_alive": -1},
                )
                self.status = "Modelo local precargado."
            except Exception:  # noqa: BLE001
                self.status = "Ollama no está disponible en la URL configurada."

    def unload(self) -> None:
        self._closing.set()
        if not self.service.enabled or self.service._validate_configuration():
            return
        try:
            with self._operation_lock:
                self.service._post_json(
                    f"{self.service._native_base_url()}/api/generate",
                    {"model": self.service.model, "stream": False, "keep_alive": 0},
                )
        except Exception:  # noqa: BLE001
            self.status = "No se pudo descargar el modelo local."

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(url, method="GET")
        opener = build_opener(ProxyHandler({}))
        with opener.open(request, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body or "{}")
        return parsed if isinstance(parsed, dict) else {}

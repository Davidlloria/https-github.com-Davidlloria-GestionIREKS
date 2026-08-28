from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from app.services.local_ai_settings_service import LocalAISettingsService


@dataclass
class LocalAIResult:
    ok: bool
    text: str
    message: str = ""


class _OllamaExecutableNotFoundError(RuntimeError):
    pass


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

    def generate_json(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 400,
    ) -> LocalAIResult:
        src = str(prompt or "").strip()
        if not src:
            return LocalAIResult(False, "", "Prompt vacío.")
        return self.chat(
            [{"role": "user", "content": src}],
            temperature=0.0,
            max_tokens=max(1, int(max_tokens)),
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

    def __init__(
        self,
        service: LocalAIService | None = None,
        *,
        timeout: float = 2.0,
        startup_timeout: float = 15.0,
        poll_interval: float = 0.25,
        ollama_executable: str | Path | None = None,
        process_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.service = service or LocalAIService(timeout=180.0)
        self.timeout = float(timeout)
        self.startup_timeout = max(float(startup_timeout), 0.1)
        self.poll_interval = max(float(poll_interval), 0.01)
        self.ollama_executable = str(ollama_executable) if ollama_executable else ""
        self._process_factory = process_factory or subprocess.Popen
        self._server_process: Any | None = None
        self.status_code = "disabled" if not self.service.enabled else "checking"
        self.status = "IA local desactivada" if not self.service.enabled else "Comprobando IA local..."
        self._closing = threading.Event()
        self._operation_lock = threading.Lock()

    def preload_async(self) -> None:
        if not self.service.enabled:
            self._set_status("disabled", "IA local desactivada")
            return
        if self._closing.is_set():
            return
        self._set_status("checking", "Comprobando IA local...")
        threading.Thread(target=self._preload, name="ollama-model-preload", daemon=True).start()

    def _preload(self) -> None:
        if self._closing.is_set():
            return
        configuration_error = self.service._validate_configuration()
        if configuration_error:
            self._set_status("unavailable", configuration_error)
            return
        with self._operation_lock:
            if self._closing.is_set():
                return
            try:
                self._ensure_server()
                if self._closing.is_set():
                    return
                self._set_status("loading", "Cargando modelo local...")
                self.service._post_json(
                    self.service._chat_url(),
                    {"model": self.service.model, "messages": [], "stream": False, "think": False, "keep_alive": -1},
                )
                self._set_status("ready", "IA local disponible")
            except _OllamaExecutableNotFoundError:
                self._set_status("not_installed", "Ollama no está instalado")
            except Exception:  # noqa: BLE001
                self._stop_owned_server()
                self._set_status("unavailable", "IA local no disponible")

    def unload(self) -> None:
        self._closing.set()
        if not self.service.enabled or self.service._validate_configuration():
            self._stop_owned_server()
            return
        try:
            with self._operation_lock:
                self.service._post_json(
                    f"{self.service._native_base_url()}/api/generate",
                    {"model": self.service.model, "stream": False, "keep_alive": 0},
                )
        except Exception:  # noqa: BLE001
            self._set_status("unavailable", "No se pudo descargar el modelo local.")
        finally:
            self._stop_owned_server()

    def _ensure_server(self) -> None:
        tags_url = f"{self.service._native_base_url()}/api/tags"
        try:
            self._get_json(tags_url)
            return
        except Exception:  # noqa: BLE001
            pass

        executable = self._resolve_ollama_executable()
        if not executable:
            raise _OllamaExecutableNotFoundError

        self._set_status("starting", "Iniciando servidor Ollama...")
        self._server_process = self._start_server(executable)
        deadline = time.monotonic() + self.startup_timeout
        while not self._closing.is_set() and time.monotonic() < deadline:
            try:
                self._get_json(tags_url)
                return
            except Exception:  # noqa: BLE001
                if self._server_process.poll() is not None:
                    break
                self._closing.wait(self.poll_interval)
        raise RuntimeError("Ollama no quedó disponible dentro del tiempo esperado.")

    def _resolve_ollama_executable(self) -> str:
        if self.ollama_executable:
            return self.ollama_executable
        discovered = shutil.which("ollama")
        if discovered:
            return discovered
        local_app_data = str(os.environ.get("LOCALAPPDATA") or "").strip()
        if local_app_data:
            candidate = Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe"
            if candidate.is_file():
                return str(candidate)
        return ""

    def _start_server(self, executable: str):
        parsed = urlsplit(self.service._native_base_url())
        host = str(parsed.hostname or "127.0.0.1")
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        port = parsed.port or 11434
        environment = os.environ.copy()
        environment["OLLAMA_HOST"] = f"{host}:{port}"
        return self._process_factory(
            [executable, "serve"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _stop_owned_server(self) -> None:
        process = self._server_process
        self._server_process = None
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)
        except Exception:  # noqa: BLE001
            pass

    def _set_status(self, code: str, message: str) -> None:
        self.status_code = str(code or "unavailable")
        self.status = str(message or "IA local no disponible")

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(url, method="GET")
        opener = build_opener(ProxyHandler({}))
        with opener.open(request, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body or "{}")
        return parsed if isinstance(parsed, dict) else {}

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from app.services.openai_settings_service import OpenAISettingsService


@dataclass
class OpenAIProcessResult:
    ok: bool
    text: str
    message: str = ""


class OpenAIProcessService:
    BASE_URL = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: str | None = None, model: str = "gpt-4.1-mini", timeout: float = 30.0) -> None:
        cfg = OpenAISettingsService().load()
        self.api_key = str(api_key or cfg.get("api_key") or "").strip()
        self.model = str(model or "gpt-4.1-mini").strip()
        self.timeout = timeout

    def generate_process(self, prompt: str) -> OpenAIProcessResult:
        src = str(prompt or "").strip()
        if not src:
            return OpenAIProcessResult(False, "", "Prompt vacío.")
        if not self.api_key:
            return OpenAIProcessResult(False, "", "Falta API key de OpenAI en Configuración > API.")

        payload: dict[str, Any] = {
            "model": self.model,
            "input": [{"role": "user", "content": src}],
            "temperature": 0.2,
            "max_output_tokens": 1200,
        }
        try:
            raw = json.dumps(payload).encode("utf-8")
            req = Request(self.BASE_URL, data=raw, method="POST")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            with urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
            parsed = json.loads(body or "{}")
            text = self._extract_text(parsed).strip()
            if not text:
                return OpenAIProcessResult(False, "", "OpenAI no devolvió contenido.")
            return OpenAIProcessResult(True, text, "Proceso generado con OpenAI.")
        except Exception as exc:  # noqa: BLE001
            return OpenAIProcessResult(False, "", f"No se pudo consultar OpenAI.\n{exc}")

    def _extract_text(self, payload: dict[str, Any]) -> str:
        out = str(payload.get("output_text") or "").strip()
        if out:
            return out
        output = payload.get("output") or []
        for item in output:
            content = item.get("content") or []
            for block in content:
                txt = str(block.get("text") or "").strip()
                if txt:
                    return txt
        return ""


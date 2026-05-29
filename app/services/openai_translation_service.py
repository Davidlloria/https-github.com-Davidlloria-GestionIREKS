from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen


@dataclass
class TranslationResult:
    ok: bool
    text: str
    message: str = ""


class OpenAITranslationService:
    BASE_URL = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini", timeout: float = 15.0) -> None:
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "gpt-4.1-mini").strip()
        self.timeout = timeout

    def translate_es_to_en(self, text: str) -> TranslationResult:
        src = str(text or "").strip()
        if not src:
            return TranslationResult(False, "", "Texto vacio.")
        if not self.api_key:
            return TranslationResult(False, "", "Falta OPENAI_API_KEY.")

        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Translate Spanish food ingredient/product names into concise English search terms. "
                        "Return only the translated term, no quotes, no explanation."
                    ),
                },
                {"role": "user", "content": src},
            ],
            "max_output_tokens": 40,
            "temperature": 0,
        }
        try:
            raw = json.dumps(payload).encode("utf-8")
            req = Request(self.BASE_URL, data=raw, method="POST")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            req.add_header("Content-Type", "application/json")
            with urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
            data = json.loads(body or "{}")
            text_out = self._extract_text(data).strip()
            if not text_out:
                return TranslationResult(False, "", "OpenAI no devolvio traduccion.")
            return TranslationResult(True, text_out)
        except Exception as exc:  # noqa: BLE001
            return TranslationResult(False, "", f"Error OpenAI: {exc}")

    def translate_es_to_en_candidates(self, text: str, max_items: int = 6) -> list[str]:
        src = str(text or "").strip()
        if not src or not self.api_key:
            return []
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Return up to 6 English search terms for a Spanish food ingredient/product name. "
                        "Output only a plain list separated by '|'. No explanation."
                    ),
                },
                {"role": "user", "content": src},
            ],
            "max_output_tokens": 80,
            "temperature": 0.2,
        }
        try:
            raw = json.dumps(payload).encode("utf-8")
            req = Request(self.BASE_URL, data=raw, method="POST")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            req.add_header("Content-Type", "application/json")
            with urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
            data = json.loads(body or "{}")
            out = self._extract_text(data).strip()
            if not out:
                return []
            parts = [p.strip() for p in out.replace("\n", "|").split("|") if p.strip()]
            unique: list[str] = []
            seen: set[str] = set()
            for p in parts:
                k = p.lower()
                if k in seen:
                    continue
                seen.add(k)
                unique.append(p)
                if len(unique) >= max(1, max_items):
                    break
            return unique
        except Exception:
            return []

    def _extract_text(self, payload: dict[str, Any]) -> str:
        # Responses API preferred field.
        out = str(payload.get("output_text") or "").strip()
        if out:
            return out
        # Fallback for structured output blocks.
        output = payload.get("output") or []
        for item in output:
            content = item.get("content") or []
            for block in content:
                txt = str(block.get("text") or "").strip()
                if txt:
                    return txt
        return ""

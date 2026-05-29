from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from app.services.openai_settings_service import OpenAISettingsService


@dataclass
class OpenAINutritionResult:
    ok: bool
    message: str
    values: dict[str, float]


class OpenAINutritionService:
    BASE_URL = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: str | None = None, model: str = "gpt-4.1-mini", timeout: float = 20.0) -> None:
        cfg = OpenAISettingsService().load()
        self.api_key = str(api_key or cfg.get("api_key") or "").strip()
        self.model = str(model or "gpt-4.1-mini").strip()
        self.timeout = timeout

    def fetch_for_query(self, query: str) -> OpenAINutritionResult:
        q = str(query or "").strip()
        if not q:
            return OpenAINutritionResult(False, "Consulta vacía.", {})
        if not self.api_key:
            return OpenAINutritionResult(False, "Falta API key de OpenAI en Configuración > API.", {})

        schema_hint = {
            "energia_kj": 0.0,
            "energia_kcal": 0.0,
            "grasas_g": 0.0,
            "saturadas_g": 0.0,
            "hidratos_g": 0.0,
            "azucares_g": 0.0,
            "fibra_g": 0.0,
            "proteinas_g": 0.0,
            "sal_g": 0.0,
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Devuelve solo JSON válido con valores nutricionales por 100 g del alimento consultado. "
                        "Si no sabes un valor, usa 0. "
                        "No incluyas explicaciones, markdown ni texto extra."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Alimento: {q}\n"
                        f"Devuelve exactamente este objeto JSON con números: {json.dumps(schema_hint, ensure_ascii=False)}"
                    ),
                },
            ],
            "temperature": 0,
            "max_output_tokens": 300,
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
            text = self._extract_text(parsed)
            values = self._parse_values(text)
            if not values:
                return OpenAINutritionResult(False, "OpenAI no devolvió un JSON nutricional válido.", {})
            return OpenAINutritionResult(True, "Valores nutricionales cargados desde ChatGPT.", values)
        except Exception as exc:  # noqa: BLE001
            return OpenAINutritionResult(False, f"No se pudo consultar OpenAI.\n{exc}", {})

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

    def _parse_values(self, text: str) -> dict[str, float]:
        raw = str(text or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start < 0 or end <= start:
                return {}
            try:
                data = json.loads(raw[start : end + 1])
            except Exception:
                return {}
        keys = [
            "energia_kj",
            "energia_kcal",
            "grasas_g",
            "saturadas_g",
            "hidratos_g",
            "azucares_g",
            "fibra_g",
            "proteinas_g",
            "sal_g",
        ]
        out: dict[str, float] = {}
        for key in keys:
            out[key] = self._to_float(data.get(key))
        return out

    def _to_float(self, value: Any) -> float:
        if value is None:
            return 0.0
        try:
            return float(str(value).replace(",", ".").strip())
        except Exception:
            return 0.0


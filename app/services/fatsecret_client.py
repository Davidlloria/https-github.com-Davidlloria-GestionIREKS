from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any

import requests


class FatSecretApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _load_dotenv(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return data
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key:
                data[key] = value
    except Exception:
        return {}
    return data


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    raw = str(value).strip().replace(",", ".")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except Exception:
        return 0.0


def normalize_food_response(food: dict[str, Any]) -> dict[str, Any]:
    source = "fatsecret"
    food_id = str(food.get("food_id") or "").strip()
    food_name = str(food.get("food_name") or "").strip()
    brand_name = str(food.get("brand_name") or "").strip()
    food_type = str(food.get("food_type") or "").strip()

    servings_node = ((food.get("servings") or {}).get("serving")) if isinstance(food.get("servings"), dict) else []
    if isinstance(servings_node, dict):
        servings_raw = [servings_node]
    elif isinstance(servings_node, list):
        servings_raw = servings_node
    else:
        servings_raw = []

    servings: list[dict[str, Any]] = []
    for row in servings_raw:
        description = str(row.get("serving_description") or row.get("measurement_description") or "").strip()
        metric_amount = _to_float(row.get("metric_serving_amount"))
        metric_unit = str(row.get("metric_serving_unit") or "").strip() or "g"
        servings.append(
            {
                "serving_id": str(row.get("serving_id") or "").strip(),
                "description": description,
                "metric_amount": metric_amount,
                "metric_unit": metric_unit,
                "calories_kcal": _to_float(row.get("calories")),
                "carbohydrates_g": _to_float(row.get("carbohydrate")),
                "protein_g": _to_float(row.get("protein")),
                "fat_g": _to_float(row.get("fat")),
                "saturated_fat_g": _to_float(row.get("saturated_fat")),
                "sugars_g": _to_float(row.get("sugar")),
                "fiber_g": _to_float(row.get("fiber")),
                "sodium_mg": _to_float(row.get("sodium")),
            }
        )

    def _score_100g(item: dict[str, Any]) -> tuple[int, float]:
        unit = str(item.get("metric_unit") or "").strip().lower()
        amount = float(item.get("metric_amount") or 0.0)
        desc = str(item.get("description") or "").strip().lower()
        is_100g = (unit == "g" and abs(amount - 100.0) < 0.01) or ("100 g" in desc)
        # Prefer exact 100g, then smaller absolute delta to 100 if metric unit is grams.
        delta = abs(amount - 100.0) if unit == "g" and amount > 0 else 10_000.0
        return (0 if is_100g else 1, delta)

    servings = sorted(servings, key=_score_100g)
    return {
        "source": source,
        "food_id": food_id,
        "food_name": food_name,
        "brand_name": brand_name,
        "food_type": food_type,
        "servings": servings,
    }


class FatSecretClient:
    TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
    API_BASE = "https://platform.fatsecret.com/rest"
    TOKEN_REFRESH_MARGIN_SEC = 45
    ES_EN_HINTS = {
        "aceite": "oil",
        "aceite de oliva": "olive oil",
        "harina": "flour",
        "azucar": "sugar",
        "sal": "salt",
        "levadura": "yeast",
        "mantequilla": "butter",
        "leche": "milk",
        "huevo": "egg",
        "agua": "water",
        "cacao": "cocoa",
        "chocolate": "chocolate",
        "almendra": "almond",
        "avellana": "hazelnut",
        "nuez": "walnut",
        "maiz": "corn",
        "arroz": "rice",
        "trigo": "wheat",
        "pan": "bread",
    }

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        scope: str | None = None,
        timeout: float = 15.0,
        env_path: Path | None = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        dotenv = _load_dotenv(env_path or (base_dir / ".env"))
        settings_client_id = ""
        settings_client_secret = ""
        settings_scope = ""
        try:
            from app.services.fatsecret_settings_service import FatSecretSettingsService

            loaded = FatSecretSettingsService().load()
            settings_client_id = str(loaded.get("client_id") or "").strip()
            settings_client_secret = str(loaded.get("client_secret") or "").strip()
            settings_scope = str(loaded.get("scope") or "").strip()
        except Exception:
            settings_client_id = ""
            settings_client_secret = ""
            settings_scope = ""

        self.client_id = (
            client_id
            or os.getenv("FATSECRET_CLIENT_ID")
            or settings_client_id
            or dotenv.get("FATSECRET_CLIENT_ID")
            or ""
        ).strip()
        self.client_secret = (
            client_secret
            or os.getenv("FATSECRET_CLIENT_SECRET")
            or settings_client_secret
            or dotenv.get("FATSECRET_CLIENT_SECRET")
            or ""
        ).strip()
        self.scope = (
            scope
            or os.getenv("FATSECRET_SCOPE")
            or settings_scope
            or dotenv.get("FATSECRET_SCOPE")
            or "basic"
        ).strip()
        self.timeout = timeout

        self._access_token = ""
        self._token_expires_at = 0.0

    def get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < (self._token_expires_at - self.TOKEN_REFRESH_MARGIN_SEC):
            return self._access_token

        if not self.client_id or not self.client_secret:
            raise FatSecretApiError("Faltan FATSECRET_CLIENT_ID o FATSECRET_CLIENT_SECRET.")

        auth_raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        auth_b64 = base64.b64encode(auth_raw).decode("ascii")
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {"grant_type": "client_credentials", "scope": self.scope or "basic"}

        try:
            resp = requests.post(self.TOKEN_URL, data=data, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise FatSecretApiError(f"Error de red obteniendo token OAuth2: {exc}") from exc

        payload: dict[str, Any] = {}
        try:
            payload = resp.json() if resp.content else {}
        except Exception:
            payload = {}

        if resp.status_code >= 400:
            self._raise_api_error(
                status_code=resp.status_code,
                payload=payload,
                context="Error de autenticación OAuth2 en FatSecret.",
            )

        token = str(payload.get("access_token") or "").strip()
        expires_in = int(payload.get("expires_in") or 0)
        if not token:
            raise FatSecretApiError("Token OAuth2 inválido: access_token vacío.", status_code=resp.status_code, payload=payload)
        self._access_token = token
        self._token_expires_at = time.time() + max(expires_in, 60)
        return self._access_token

    def search_food(self, query: str, page: int = 0, max_results: int = 20, region: str = "ES") -> list[dict[str, Any]]:
        q = str(query or "").strip()
        if not q:
            return []
        for term in self._expand_search_queries(q):
            params = {
                "search_expression": term,
                "page_number": max(0, int(page)),
                "max_results": max(1, min(int(max_results), 50)),
                "format": "json",
            }
            if region:
                params["region"] = region
            payload = self._api_get("/foods/search/v3", params=params)
            foods_node = ((payload.get("foods") or {}).get("food")) if isinstance(payload.get("foods"), dict) else []
            if isinstance(foods_node, dict):
                rows = [foods_node]
            elif isinstance(foods_node, list):
                rows = foods_node
            else:
                rows = []
            out: list[dict[str, Any]] = []
            for row in rows:
                out.append(
                    {
                        "source": "fatsecret",
                        "food_id": str(row.get("food_id") or "").strip(),
                        "food_name": str(row.get("food_name") or "").strip(),
                        "brand_name": str(row.get("brand_name") or "").strip(),
                        "food_type": str(row.get("food_type") or "").strip(),
                        "food_description": str(row.get("food_description") or "").strip(),
                        "query_used": term,
                    }
                )
            if out:
                return out
        return []

    def get_food(self, food_id: str, region: str = "ES", language: str = "es") -> dict[str, Any]:
        fid = str(food_id or "").strip()
        if not fid:
            raise FatSecretApiError("food_id es obligatorio.")
        params = {"food_id": fid, "format": "json", "region": region, "language": language}
        payload = self._api_get("/food/v5", params=params)
        food = payload.get("food") if isinstance(payload.get("food"), dict) else {}
        if not food:
            return {
                "source": "fatsecret",
                "food_id": fid,
                "food_name": "",
                "brand_name": "",
                "food_type": "",
                "servings": [],
            }
        return normalize_food_response(food)

    def find_by_barcode(self, barcode: str, region: str = "ES") -> dict[str, Any]:
        code = str(barcode or "").strip()
        if not code:
            raise FatSecretApiError("barcode es obligatorio.")
        params = {"barcode": code, "format": "json", "region": region}
        payload = self._api_get("/food/barcode/find-by-id/v2", params=params)
        food = payload.get("food") if isinstance(payload.get("food"), dict) else {}
        if not food:
            return {
                "source": "fatsecret",
                "food_id": "",
                "food_name": "",
                "brand_name": "",
                "food_type": "",
                "servings": [],
            }
        return normalize_food_response(food)

    def _api_get(self, path: str, params: dict[str, Any], retry_on_401: bool = True) -> dict[str, Any]:
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        url = f"{self.API_BASE}{path}"
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise FatSecretApiError(f"Error de red llamando a FatSecret: {exc}") from exc

        if resp.status_code == 401 and retry_on_401:
            self._access_token = ""
            self._token_expires_at = 0.0
            return self._api_get(path, params, retry_on_401=False)

        payload: dict[str, Any] = {}
        try:
            payload = resp.json() if resp.content else {}
        except Exception:
            payload = {}

        if resp.status_code >= 400:
            self._raise_api_error(
                status_code=resp.status_code,
                payload=payload,
                context=f"Error API FatSecret en {path}.",
            )
        return payload

    def _raise_api_error(self, *, status_code: int, payload: dict[str, Any], context: str) -> None:
        message = context
        text_blob = str(payload).lower()
        if "invalid_client" in text_blob:
            message = (
                "invalid_client en FatSecret OAuth2. Revisa FATSECRET_CLIENT_ID/FATSECRET_CLIENT_SECRET "
                "y la IP whitelist en el panel de FatSecret."
            )
        elif status_code == 401:
            message = "401 en FatSecret. Token inválido/caducado; se intentó renovar automáticamente."
        elif status_code == 403:
            if "barcode" in text_blob or "scope" in text_blob:
                message = "403 en FatSecret: scope insuficiente (p.ej. barcode no habilitado en la cuenta)."
            else:
                message = "403 en FatSecret: acceso denegado por permisos o plan."
        elif status_code == 400:
            message = "400 en FatSecret: parámetros inválidos o petición mal formada."
        raise FatSecretApiError(message, status_code=status_code, payload=payload)

    def _expand_search_queries(self, query: str) -> list[str]:
        q = str(query or "").strip()
        if not q:
            return []
        out: list[str] = []
        lower = q.lower()
        words = [w for w in lower.replace("/", " ").replace("-", " ").split() if w]

        # 1) Traduccion IA opcional (prioridad alta).
        try:
            from app.services.openai_settings_service import OpenAISettingsService
            from app.services.openai_translation_service import OpenAITranslationService

            oa = OpenAISettingsService().load()
            api_key = str(oa.get("api_key") or "").strip()
            use_ai = bool(oa.get("use_ai_translation", False))
            if api_key and use_ai:
                translator = OpenAITranslationService(api_key=api_key)
                tr = translator.translate_es_to_en(q)
                if tr.ok and tr.text.strip():
                    out.append(tr.text.strip())
                for cand in translator.translate_es_to_en_candidates(q, max_items=6):
                    if cand.strip():
                        out.append(cand.strip())
        except Exception:
            pass

        # 2) Mapeos ES->EN (fallback).
        if lower in self.ES_EN_HINTS:
            out.append(self.ES_EN_HINTS[lower])
        for w in words:
            mapped = self.ES_EN_HINTS.get(w)
            if mapped:
                out.append(mapped)
        if words and words[0] in self.ES_EN_HINTS:
            out.append(self.ES_EN_HINTS[words[0]])

        # 3) Consulta original.
        out.append(q)

        seen: set[str] = set()
        unique: list[str] = []
        for t in out:
            key = t.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(t.strip())
        return unique

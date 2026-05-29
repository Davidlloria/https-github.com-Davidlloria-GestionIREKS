from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.services.fdc_settings_service import FdcSettingsService
from app.services.openai_settings_service import OpenAISettingsService
from app.services.openai_translation_service import OpenAITranslationService


@dataclass
class FdcNutritionResult:
    ok: bool
    message: str
    values: dict[str, float]


@dataclass
class FdcFoodCandidate:
    label: str
    values: dict[str, float]
    query_used: str = ""


class FdcNutritionService:
    BASE_URL = "https://api.nal.usda.gov/fdc/v1"
    # USDA nutrient IDs used for values per 100g.
    NUTRIENT_IDS = {
        "energia_kcal": 1008,
        "energia_kj": 1062,
        "proteinas_g": 1003,
        "grasas_g": 1004,
        "saturadas_g": 1258,
        "hidratos_g": 1005,
        "azucares_g": 2000,
        "fibra_g": 1079,
        "sal_g": 1093,  # sodium (mg), converted to salt g.
    }
    NUTRIENT_NUMBERS = {
        "energia_kcal": {"208"},
        "energia_kj": {"268"},
        "proteinas_g": {"203"},
        "grasas_g": {"204"},
        "saturadas_g": {"606"},
        "hidratos_g": {"205"},
        "azucares_g": {"269"},
        "fibra_g": {"291"},
        "sal_g": {"307"},  # sodium
    }
    DATA_TYPE_MAP = {
        "foundation": "Foundation",
        "branded": "Branded",
        "survey (fndds)": "Survey (FNDDS)",
        "survey": "Survey (FNDDS)",
        "sr legacy": "SR Legacy",
    }
    ES_EN_HINTS = {
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
    }
    EN_DESCRIPTOR_WORDS = {
        "fresh",
        "dry",
        "raw",
        "whole",
        "white",
        "yellow",
        "red",
        "green",
        "black",
        "powder",
        "powdered",
        "ground",
        "extra",
        "virgin",
        "sweet",
        "light",
        "low",
        "fat",
        "reduced",
    }

    def __init__(self, api_key: str | None = None, timeout: float = 12.0) -> None:
        cfg_key = ""
        cfg_data_type = "Foundation"
        try:
            cfg = FdcSettingsService().load()
            cfg_key = str(cfg.get("api_key") or "").strip()
            cfg_data_type = str(cfg.get("data_type") or "Foundation").strip() or "Foundation"
        except Exception:
            cfg_key = ""
            cfg_data_type = "Foundation"
        self.api_key = (api_key or os.getenv("FDC_API_KEY") or cfg_key or "").strip()
        self.timeout = timeout
        self.data_type = self._normalize_data_type(cfg_data_type)
        try:
            oa = OpenAISettingsService().load()
        except Exception:
            oa = {"api_key": "", "use_ai_translation": False}
        self.openai_api_key = str(oa.get("api_key") or "").strip()
        self.use_ai_translation = bool(oa.get("use_ai_translation", False))

    def fetch_for_query(self, query: str) -> FdcNutritionResult:
        q = str(query or "").strip()
        if not q:
            return FdcNutritionResult(False, "Consulta vacia para FoodData Central.", {})
        if not self.api_key:
            return FdcNutritionResult(False, "Falta FDC_API_KEY en variables de entorno.", {})

        candidates = self.fetch_candidates(q, limit=8)
        if not candidates:
            return FdcNutritionResult(False, f"Sin resultados FDC para: {q}", {})
        values = candidates[0].values
        if not values:
            return FdcNutritionResult(False, "La respuesta FDC no incluye nutrientes compatibles.", {})
        return FdcNutritionResult(True, "Valores nutricionales cargados desde FDC.", values)

    def fetch_candidates(self, query: str, limit: int = 8) -> list[FdcFoodCandidate]:
        q = str(query or "").strip()
        if not q or not self.api_key:
            return []
        seen: set[str] = set()
        out: list[FdcFoodCandidate] = []
        for term in self._expand_queries(q):
            payload = {"query": term, "pageSize": max(1, min(limit, 10)), "dataType": [self.data_type]}
            search = self._post_json("/foods/search", payload)
            foods = list((search or {}).get("foods") or [])
            for food in foods:
                desc = str(food.get("description") or "").strip()
                brand = str(food.get("brandName") or "").strip()
                key = f"{desc}|{brand}".lower()
                if not desc or key in seen:
                    continue
                seen.add(key)
                nutrients = list((food or {}).get("foodNutrients") or [])
                values = self._fill_energy_fallbacks(self._merge_label_nutrients(self._map_nutrients(nutrients), food))
                label = desc if not brand else f"{desc} ({brand})"
                out.append(FdcFoodCandidate(label=label, values=values, query_used=term))
                if len(out) >= limit:
                    return out
        return out

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        params = urlencode({"api_key": self.api_key})
        url = f"{self.BASE_URL}{path}?{params}"
        raw = json.dumps(body).encode("utf-8")
        req = Request(url=url, data=raw, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        with urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
            data = resp.read().decode("utf-8")
        return json.loads(data or "{}")

    def _map_nutrients(self, food_nutrients: list[dict[str, Any]]) -> dict[str, float]:
        by_id: dict[int, float] = {}
        by_number: dict[str, tuple[float, str]] = {}
        by_name: dict[str, tuple[float, str]] = {}
        for row in food_nutrients:
            try:
                nutrient = row.get("nutrient") or {}
                nid = int(nutrient.get("id") or row.get("nutrientId") or 0)
                amount = float(row.get("amount") or row.get("value") or 0.0)
                number = str(nutrient.get("number") or row.get("nutrientNumber") or "").strip()
                name = str(nutrient.get("name") or row.get("nutrientName") or "").strip().lower()
                unit = str(nutrient.get("unitName") or row.get("unitName") or "").strip().upper()
                if nid > 0:
                    by_id[nid] = amount
                if number:
                    by_number[number] = (amount, unit)
                if name:
                    by_name[name] = (amount, unit)
            except Exception:
                continue

        out: dict[str, float] = {}
        for field, nid in self.NUTRIENT_IDS.items():
            val: float | None = None
            unit = ""
            if nid in by_id:
                val = float(by_id[nid])
            if val is None:
                for num in self.NUTRIENT_NUMBERS.get(field, set()):
                    if num in by_number:
                        val, unit = by_number[num]
                        break
            if val is None:
                name_match = self._find_name_match(field, by_name)
                if name_match is not None:
                    val, unit = name_match
            if val is None:
                continue
            out[field] = self._normalize_value(field, float(val), unit)

        # Energy fallback conversions when one side is missing.
        if "energia_kj" not in out and "energia_kcal" in out:
            out["energia_kj"] = out["energia_kcal"] * 4.184
        if "energia_kcal" not in out and "energia_kj" in out:
            out["energia_kcal"] = out["energia_kj"] / 4.184
        return out

    def _normalize_data_type(self, raw: str) -> str:
        key = str(raw or "").strip().lower()
        return self.DATA_TYPE_MAP.get(key, "Foundation")

    def _normalize_value(self, field: str, value: float, unit: str) -> float:
        u = (unit or "").strip().upper()
        if field == "sal_g":
            # sodium -> salt
            if u == "MG":
                return (value / 1000.0) * 2.5
            return value * 2.5
        if field == "energia_kj" and u == "KCAL":
            return value * 4.184
        if field == "energia_kcal" and u == "KJ":
            return value / 4.184
        return value

    def _find_name_match(self, field: str, by_name: dict[str, tuple[float, str]]) -> tuple[float, str] | None:
        candidates: dict[str, tuple[str, ...]] = {
            "energia_kcal": ("energy", "energy (kcal)"),
            "energia_kj": ("energy (kj)",),
            "proteinas_g": ("protein",),
            "grasas_g": ("total lipid", "fat"),
            "saturadas_g": ("fatty acids, total saturated", "saturated"),
            "hidratos_g": ("carbohydrate, by difference", "carbohydrate"),
            "azucares_g": ("sugars, total", "total sugars", "sugar"),
            "fibra_g": ("fiber, total dietary", "dietary fiber", "fiber"),
            "sal_g": ("sodium",),
        }
        patterns = candidates.get(field, ())
        for name, pair in by_name.items():
            if any(p in name for p in patterns):
                return pair
        return None

    def _expand_queries(self, query: str) -> list[str]:
        q = str(query or "").strip()
        base = q.lower()
        terms: list[str] = []
        words = [w for w in base.replace("/", " ").replace("-", " ").split() if w]
        # Prioridad: primera palabra (normalmente el nombre principal), luego nombre completo.
        if words:
            terms.append(words[0])
            mapped_first = self.ES_EN_HINTS.get(words[0], "")
            if mapped_first:
                terms.append(mapped_first)
        translated_term = ""
        if self.use_ai_translation and self.openai_api_key:
            try:
                translator = OpenAITranslationService(api_key=self.openai_api_key)
                # 1) Traducir primera palabra del nombre original (prioridad absoluta).
                if words:
                    first_word_es = words[0]
                    first_word_en = self._translate_hint(translator, first_word_es)
                    if first_word_en:
                        terms.append(first_word_en)
                # 2) Traducir cada palabra por separado.
                for w in words[1:]:
                    mapped = self.ES_EN_HINTS.get(w, "")
                    if mapped:
                        terms.append(mapped)
                    token_en = self._translate_hint(translator, w)
                    if token_en:
                        terms.append(token_en)
                # 3) Traducir el nombre completo como fallback.
                translated = translator.translate_es_to_en(q)
                if translated.ok and translated.text.strip():
                    translated_term = translated.text.strip()
                    translated_words = [
                        w for w in translated_term.lower().replace("/", " ").replace("-", " ").split() if w
                    ]
                    if translated_words:
                        core_words = [w for w in translated_words if w not in self.EN_DESCRIPTOR_WORDS]
                        if core_words:
                            terms.append(core_words[-1])
                            terms.extend(core_words)
                        else:
                            terms.append(translated_words[-1])
                        terms.extend(translated_words)
                    terms.append(translated_term)
            except Exception:
                translated_term = ""
        terms.append(q)
        # Busqueda por cada palabra individual (ademas del nombre completo).
        terms.extend(words)
        for es, en in self.ES_EN_HINTS.items():
            if es in base:
                terms.append(base.replace(es, en))
        if base not in terms:
            terms.append(base)
        # preserve order unique
        seen: set[str] = set()
        unique: list[str] = []
        for t in terms:
            k = t.strip().lower()
            # Evitar consultas irrelevantes solo con adjetivos (fresh, raw, etc.).
            if k in self.EN_DESCRIPTOR_WORDS:
                continue
            if not k or k in seen:
                continue
            seen.add(k)
            unique.append(t.strip())
        return unique

    def _translate_hint(self, translator: OpenAITranslationService, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        try:
            res = translator.translate_es_to_en(raw)
            if not res.ok:
                return ""
            # keep only first token for single-word hint prioritization
            token = str(res.text or "").strip().lower().split()
            if not token:
                return ""
            first = token[0]
            if first in self.EN_DESCRIPTOR_WORDS:
                return ""
            return first
        except Exception:
            return ""

    def _merge_label_nutrients(self, values: dict[str, float], food: dict[str, Any]) -> dict[str, float]:
        out = dict(values)
        label = food.get("labelNutrients") or {}
        try:
            kcal = float(((label.get("calories") or {}).get("value")) or 0.0)
            if kcal > 0 and out.get("energia_kcal", 0.0) <= 0:
                out["energia_kcal"] = kcal
        except Exception:
            pass
        return out

    def _fill_energy_fallbacks(self, values: dict[str, float]) -> dict[str, float]:
        out = dict(values)
        kcal = float(out.get("energia_kcal", 0.0) or 0.0)
        kj = float(out.get("energia_kj", 0.0) or 0.0)
        if kcal <= 0 and kj > 0:
            kcal = kj / 4.184
            out["energia_kcal"] = kcal
        if kj <= 0 and kcal > 0:
            kj = kcal * 4.184
            out["energia_kj"] = kj
        # Last fallback: estimated kcal from macros.
        if kcal <= 0:
            prot = float(out.get("proteinas_g", 0.0) or 0.0)
            fat = float(out.get("grasas_g", 0.0) or 0.0)
            carb = float(out.get("hidratos_g", 0.0) or 0.0)
            est = (prot * 4.0) + (fat * 9.0) + (carb * 4.0)
            if est > 0:
                out["energia_kcal"] = est
                out["energia_kj"] = est * 4.184
        return out

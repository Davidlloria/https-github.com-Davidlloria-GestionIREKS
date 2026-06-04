from __future__ import annotations

from typing import Any, Callable

from app.services.fatsecret_client import FatSecretClient
from app.services.fdc_nutrition_service import FdcNutritionService
from app.services.openai_translation_service import OpenAITranslationService


class IngredientNutritionQueryService:
    def normalize_query(self, source_query: str) -> str:
        return str(source_query or "").strip()

    def dedupe_candidates(self, options: list[str]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for opt in options:
            text = str(opt or "").strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            unique.append(text)
        return unique

    def build_fdc_candidates(
        self,
        source_query: str,
        *,
        openai_api_key: str = "",
        use_ai_translation: bool = False,
        translator_factory: Callable[[str], Any] | None = None,
    ) -> list[str]:
        base = self.normalize_query(source_query)
        if not base:
            return []
        options: list[str] = [base]
        words = base.lower().replace("/", " ").replace("-", " ").split()
        if words:
            mapped = FdcNutritionService.ES_EN_HINTS.get(words[0], "")
            if mapped:
                options.append(mapped)
        if use_ai_translation and str(openai_api_key or "").strip():
            translator = self._build_translator(openai_api_key, translator_factory)
            if translator is not None:
                for cand in translator.translate_es_to_en_candidates(base, max_items=8):
                    if str(cand or "").strip():
                        options.append(str(cand).strip())
        return self.dedupe_candidates(options)

    def build_fatsecret_candidates(
        self,
        source_query: str,
        *,
        openai_api_key: str = "",
        use_ai_translation: bool = False,
        translator_factory: Callable[[str], Any] | None = None,
    ) -> list[str]:
        base = self.normalize_query(source_query)
        if not base:
            return []
        options: list[str] = []
        if use_ai_translation and str(openai_api_key or "").strip():
            translator = self._build_translator(openai_api_key, translator_factory)
            if translator is not None:
                translated_words: list[str] = []
                for cand in translator.translate_es_to_en_candidates(base, max_items=8):
                    if str(cand or "").strip():
                        options.append(str(cand).strip())
                words = [w for w in base.replace("/", " ").replace("-", " ").split() if w.strip()]
                for word in words:
                    translated = translator.translate_es_to_en(word)
                    if translated.ok and str(translated.text or "").strip():
                        translated_words.append(str(translated.text).strip())
                if translated_words:
                    options.append(" + ".join(translated_words))
                    options.extend(translated_words)
        lower = base.lower()
        if lower in FatSecretClient.ES_EN_HINTS:
            options.append(FatSecretClient.ES_EN_HINTS[lower])
        for word in lower.replace("/", " ").replace("-", " ").split():
            mapped = FatSecretClient.ES_EN_HINTS.get(word.strip())
            if mapped:
                options.append(mapped)
        options.append(base)
        return self.dedupe_candidates(options)

    def _build_translator(
        self,
        openai_api_key: str,
        translator_factory: Callable[[str], Any] | None,
    ) -> Any | None:
        key = str(openai_api_key or "").strip()
        if not key:
            return None
        factory = translator_factory or OpenAITranslationService
        try:
            return factory(key)
        except Exception:
            return None

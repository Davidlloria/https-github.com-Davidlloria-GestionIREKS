from __future__ import annotations

from app.services.ingredient_nutrition_query_service import IngredientNutritionQueryService


class _FakeTranslationResult:
    def __init__(self, *, ok: bool, text: str) -> None:
        self.ok = ok
        self.text = text


class _FakeTranslator:
    def __init__(self, phrase_candidates: list[str], word_map: dict[str, str]) -> None:
        self.phrase_candidates = phrase_candidates
        self.word_map = word_map

    def translate_es_to_en_candidates(self, text: str, max_items: int = 6) -> list[str]:  # noqa: ARG002
        _ = text
        return list(self.phrase_candidates)

    def translate_es_to_en(self, text: str) -> _FakeTranslationResult:
        return _FakeTranslationResult(ok=True, text=self.word_map.get(str(text or "").strip().lower(), ""))


def test_empty_query_returns_no_candidates() -> None:
    service = IngredientNutritionQueryService()

    assert service.normalize_query("   ") == ""
    assert service.build_fdc_candidates("   ") == []
    assert service.build_fatsecret_candidates("   ") == []


def test_fdc_preserves_base_and_local_translation() -> None:
    service = IngredientNutritionQueryService()

    candidates = service.build_fdc_candidates("harina pan")

    assert candidates == ["harina pan", "flour"]


def test_fdc_ai_candidates_are_added_and_deduped() -> None:
    service = IngredientNutritionQueryService()
    translator = _FakeTranslator(["flour", "bread", "flour"], {})

    candidates = service.build_fdc_candidates(
        "harina",
        openai_api_key="fake-key",
        use_ai_translation=True,
        translator_factory=lambda _key: translator,
    )

    assert candidates == ["harina", "flour", "bread"]


def test_fatsecret_preserves_order_and_es_en_mappings() -> None:
    service = IngredientNutritionQueryService()

    candidates = service.build_fatsecret_candidates("aceite pan")

    assert candidates == ["oil", "bread", "aceite pan"]


def test_fatsecret_ai_candidates_are_deduped_and_ordered() -> None:
    service = IngredientNutritionQueryService()
    translator = _FakeTranslator(["bread", "flour", "bread"], {"harina": "flour", "pan": "bread"})

    candidates = service.build_fatsecret_candidates(
        "harina pan",
        openai_api_key="fake-key",
        use_ai_translation=True,
        translator_factory=lambda _key: translator,
    )

    assert candidates == ["bread", "flour", "flour + bread", "harina pan"]


def test_dedupe_preserves_first_occurrence() -> None:
    service = IngredientNutritionQueryService()

    assert service.dedupe_candidates(["A", "a", "", "B", "a", "b", "C"]) == ["A", "B", "C"]

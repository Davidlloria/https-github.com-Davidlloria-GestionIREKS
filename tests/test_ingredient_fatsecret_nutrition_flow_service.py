from __future__ import annotations

from typing import Any

from app.services.fatsecret_client import FatSecretApiError
from app.services.ingredient_fatsecret_nutrition_flow_service import (
    IngredientFatSecretNutritionFlowResult,
    IngredientFatSecretNutritionFlowService,
)


class _FakeNutritionQueryService:
    def __init__(self) -> None:
        self.normalize_calls: list[str] = []
        self.candidate_calls: list[tuple[str, str, bool]] = []

    def normalize_query(self, text: str) -> str:
        self.normalize_calls.append(text)
        return str(text or "").strip()

    def build_fatsecret_candidates(
        self,
        base: str,
        *,
        openai_api_key: str = "",
        use_ai_translation: bool = False,
        translator_factory: Any | None = None,
    ) -> list[str]:
        self.candidate_calls.append((base, openai_api_key, use_ai_translation))
        _ = translator_factory
        return [base, f"{base} en ingles"]


class _FakeFatSecretClient:
    def __init__(self, *, search_rows: list[dict[str, Any]] | None = None, food_payload: dict[str, Any] | None = None) -> None:
        self.search_rows = list(search_rows or [])
        self.food_payload = dict(food_payload or {})
        self.barcode_payload = dict(food_payload or {})
        self.search_calls: list[tuple[str, int, int, str]] = []
        self.get_calls: list[tuple[str, str, str]] = []
        self.barcode_calls: list[tuple[str, str]] = []

    def search_food(self, query: str, page: int = 0, max_results: int = 20, region: str = "ES") -> list[dict[str, Any]]:
        self.search_calls.append((query, page, max_results, region))
        return list(self.search_rows)

    def get_food(self, food_id: str, region: str = "ES", language: str = "es") -> dict[str, Any]:
        self.get_calls.append((food_id, region, language))
        payload = dict(self.food_payload)
        payload.setdefault("food_id", food_id)
        return payload

    def find_by_barcode(self, barcode: str, region: str = "ES") -> dict[str, Any]:
        self.barcode_calls.append((barcode, region))
        payload = dict(self.barcode_payload)
        payload.setdefault("barcode", barcode)
        return payload


class _FakeErrorClient(_FakeFatSecretClient):
    def search_food(self, query: str, page: int = 0, max_results: int = 20, region: str = "ES") -> list[dict[str, Any]]:
        self.search_calls.append((query, page, max_results, region))
        raise FatSecretApiError("fallo search")


class _FakeBarcodeErrorClient(_FakeFatSecretClient):
    def find_by_barcode(self, barcode: str, region: str = "ES") -> dict[str, Any]:
        self.barcode_calls.append((barcode, region))
        raise FatSecretApiError("fallo barcode")


def test_build_query_options_uses_query_service_and_preserves_candidates() -> None:
    query_service = _FakeNutritionQueryService()
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=query_service,
        translation_settings_loader=lambda: {"api_key": "fake-key", "use_ai_translation": True},
    )

    result = service.build_query_options("  harina pan  ")

    assert result.status == "query_options"
    assert result.source_query == "harina pan"
    assert result.query_options == ["harina pan", "harina pan en ingles"]
    assert query_service.normalize_calls == ["  harina pan  "]
    assert query_service.candidate_calls == [("harina pan", "fake-key", True)]


def test_empty_query_returns_no_query() -> None:
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        translation_settings_loader=lambda: {"api_key": "", "use_ai_translation": False},
    )

    result = service.build_query_options("   ")

    assert result.status == "no_query"


def test_search_food_error_returns_search_error() -> None:
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: _FakeErrorClient(),
    )

    result = service.search_food("  yogurt  ")

    assert result.status == "search_error"
    assert result.source_query == "yogurt"
    assert result.message == "fallo search"


def test_search_food_without_results_returns_no_results() -> None:
    client = _FakeFatSecretClient(search_rows=[])
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: client,
    )

    result = service.search_food("pan")

    assert result.status == "no_results"
    assert result.message == "Sin resultados para: pan"
    assert client.search_calls == [("pan", 0, 20, "ES")]


def test_search_food_builds_labels_and_preserves_foods() -> None:
    rows = [
        {
            "food_id": "1",
            "food_name": "Pan",
            "brand_name": "Marca",
            "food_description": "integral",
            "query_used": "bread",
        },
        {
            "food_id": "2",
            "food_name": "Leche",
            "brand_name": "",
            "food_description": "desnatada",
            "query_used": "milk",
        },
    ]
    client = _FakeFatSecretClient(search_rows=rows)
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: client,
    )

    result = service.search_food(" pan ")

    assert result.status == "foods_available"
    assert result.foods == rows
    assert result.food_labels == [
        "Pan (Marca) - integral  [query: bread]",
        "Leche - desnatada  [query: milk]",
    ]
    assert client.search_calls == [("pan", 0, 20, "ES")]


def test_load_selected_food_by_label_preserves_selection() -> None:
    search_result = IngredientFatSecretNutritionFlowResult(
        status="foods_available",
        source_query="pan",
        foods=[
            {
                "food_id": "1",
                "food_name": "Pan",
                "brand_name": "Marca",
                "food_description": "integral",
                "query_used": "bread",
            }
        ],
        food_labels=["Pan (Marca) - integral  [query: bread]"],
    )
    client = _FakeFatSecretClient(
        food_payload={
            "food_id": "1",
            "food_name": "Pan",
            "servings": [{"description": "100 g", "metric_amount": 100, "metric_unit": "g"}],
        }
    )
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: client,
    )

    result = service.load_selected_food(search_result, "Pan (Marca) - integral  [query: bread]")

    assert result.status == "servings_available"
    assert result.selected_food_label == "Pan (Marca) - integral  [query: bread]"
    assert result.selected_food == client.food_payload
    assert result.servings == [{"description": "100 g", "metric_amount": 100, "metric_unit": "g"}]
    assert client.get_calls == [("1", "ES", "es")]


def test_load_selected_food_without_food_id_returns_no_food_id() -> None:
    search_result = IngredientFatSecretNutritionFlowResult(
        status="foods_available",
        source_query="pan",
        foods=[{"food_name": "Pan"}],
        food_labels=["Pan - integral  [query: pan]"],
    )
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: _FakeFatSecretClient(),
    )

    result = service.load_selected_food(search_result, "Pan - integral  [query: pan]")

    assert result.status == "no_food_id"
    assert result.message == "El resultado no incluye food_id."


def test_load_selected_food_without_servings_returns_no_servings() -> None:
    search_result = IngredientFatSecretNutritionFlowResult(
        status="foods_available",
        source_query="pan",
        foods=[{"food_id": "1", "food_name": "Pan"}],
        food_labels=["Pan - integral  [query: pan]"],
    )
    client = _FakeFatSecretClient(food_payload={"food_id": "1", "servings": []})
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: client,
    )

    result = service.load_selected_food(search_result, "Pan - integral  [query: pan]")

    assert result.status == "no_servings"
    assert result.message == "El alimento no tiene raciones con datos nutricionales."
    assert client.get_calls == [("1", "ES", "es")]


def test_serving_labels_and_selection_are_preserved() -> None:
    food_result = IngredientFatSecretNutritionFlowResult(
        status="servings_available",
        source_query="pan",
        foods=[{"food_id": "1", "food_name": "Pan"}],
        food_labels=["Pan - integral  [query: pan]"],
        selected_food_label="Pan - integral  [query: pan]",
        selected_food={"food_id": "1"},
        servings=[
            {
                "description": "100 g",
                "metric_amount": 100,
                "metric_unit": "g",
                "calories_kcal": 250,
                "fat_g": 10,
                "saturated_fat_g": 1,
                "carbohydrates_g": 30,
                "sugars_g": 3,
                "fiber_g": 4,
                "protein_g": 8,
                "sodium_mg": 800,
            },
            {
                "description": "1 rebanada",
                "metric_amount": 25,
                "metric_unit": "g",
                "calories_kcal": 62.5,
                "fat_g": 2.5,
                "saturated_fat_g": 0.25,
                "carbohydrates_g": 7.5,
                "sugars_g": 0.75,
                "fiber_g": 1,
                "protein_g": 2,
                "sodium_mg": 200,
            },
        ],
        serving_labels=["100 g [100 g]", "1 rebanada [25 g]"],
    )

    result = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: _FakeFatSecretClient(),
    ).resolve_selected_serving(food_result, "1 rebanada [25 g]")

    assert result.status == "ready_to_apply"
    assert result.selected_serving_label == "1 rebanada [25 g]"
    assert result.selected_serving == food_result.servings[1]
    assert result.values["energia_kcal"] == 62.5
    assert result.values["energia_kj"] == 62.5 * 4.184


def test_build_values_from_serving_keeps_existing_formula_and_keys() -> None:
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: _FakeFatSecretClient(),
    )

    values = service.build_values_from_serving(
        {
            "calories_kcal": 120,
            "fat_g": 4.5,
            "saturated_fat_g": 1.25,
            "carbohydrates_g": 18,
            "sugars_g": 6.2,
            "fiber_g": 2.1,
            "protein_g": 7.4,
            "sodium_mg": 640,
        }
    )

    assert values == {
        "energia_kcal": 120.0,
        "energia_kj": 120.0 * 4.184,
        "grasas_g": 4.5,
        "saturadas_g": 1.25,
        "hidratos_g": 18.0,
        "azucares_g": 6.2,
        "fibra_g": 2.1,
        "proteinas_g": 7.4,
        "sal_g": 1.6,
    }


def test_load_barcode_empty_returns_barcode_cancelled() -> None:
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: _FakeFatSecretClient(),
    )

    result = service.load_barcode("   ")

    assert result.status == "barcode_cancelled"


def test_load_barcode_error_returns_search_error() -> None:
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: _FakeBarcodeErrorClient(),
    )

    result = service.load_barcode("1234567890123")

    assert result.status == "search_error"
    assert result.message == "fallo barcode"


def test_load_barcode_without_servings_returns_no_servings() -> None:
    client = _FakeFatSecretClient(food_payload={"food_id": "barcode-1", "servings": []})
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: client,
    )

    result = service.load_barcode("1234567890123")

    assert result.status == "no_servings"
    assert result.message == "El alimento no tiene raciones con datos nutricionales."
    assert client.barcode_calls == [("1234567890123", "ES")]


def test_load_barcode_with_single_serving_returns_ready_to_apply() -> None:
    client = _FakeFatSecretClient(
        food_payload={
            "food_id": "barcode-1",
            "servings": [
                {
                    "description": "100 g",
                    "metric_amount": 100,
                    "metric_unit": "g",
                    "calories_kcal": 250,
                    "fat_g": 10,
                    "saturated_fat_g": 1,
                    "carbohydrates_g": 30,
                    "sugars_g": 3,
                    "fiber_g": 4,
                    "protein_g": 8,
                    "sodium_mg": 800,
                }
            ],
        }
    )
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: client,
    )

    result = service.load_barcode("1234567890123")

    assert result.status == "ready_to_apply"
    assert result.selected_serving_label == "100 g [100 g]"
    assert result.selected_serving is not None
    assert result.values["sal_g"] == 2.0
    assert client.barcode_calls == [("1234567890123", "ES")]


def test_load_barcode_with_multiple_servings_preserves_labels() -> None:
    client = _FakeFatSecretClient(
        food_payload={
            "food_id": "barcode-1",
            "servings": [
                {
                    "description": "100 g",
                    "metric_amount": 100,
                    "metric_unit": "g",
                    "calories_kcal": 250,
                    "fat_g": 10,
                    "saturated_fat_g": 1,
                    "carbohydrates_g": 30,
                    "sugars_g": 3,
                    "fiber_g": 4,
                    "protein_g": 8,
                    "sodium_mg": 800,
                },
                {
                    "description": "1 porcion",
                    "metric_amount": 50,
                    "metric_unit": "g",
                    "calories_kcal": 125,
                    "fat_g": 5,
                    "saturated_fat_g": 0.5,
                    "carbohydrates_g": 15,
                    "sugars_g": 1.5,
                    "fiber_g": 2,
                    "protein_g": 4,
                    "sodium_mg": 400,
                },
            ],
        }
    )
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: client,
    )

    result = service.load_barcode("1234567890123")

    assert result.status == "servings_available"
    assert result.serving_labels == ["100 g [100 g]", "1 porcion [50 g]"]
    assert client.barcode_calls == [("1234567890123", "ES")]


def test_barcode_selected_serving_resolves_to_ready_to_apply() -> None:
    barcode_result = IngredientFatSecretNutritionFlowResult(
        status="servings_available",
        barcode="1234567890123",
        servings=[
            {
                "description": "100 g",
                "metric_amount": 100,
                "metric_unit": "g",
                "calories_kcal": 250,
                "fat_g": 10,
                "saturated_fat_g": 1,
                "carbohydrates_g": 30,
                "sugars_g": 3,
                "fiber_g": 4,
                "protein_g": 8,
                "sodium_mg": 800,
            },
            {
                "description": "1 porcion",
                "metric_amount": 50,
                "metric_unit": "g",
                "calories_kcal": 125,
                "fat_g": 5,
                "saturated_fat_g": 0.5,
                "carbohydrates_g": 15,
                "sugars_g": 1.5,
                "fiber_g": 2,
                "protein_g": 4,
                "sodium_mg": 400,
            },
        ],
        serving_labels=["100 g [100 g]", "1 porcion [50 g]"],
    )
    service = IngredientFatSecretNutritionFlowService(
        nutrition_query_service=_FakeNutritionQueryService(),
        fatsecret_client_factory=lambda: _FakeFatSecretClient(),
    )

    result = service.resolve_selected_serving(barcode_result, "1 porcion [50 g]")

    assert result.status == "ready_to_apply"
    assert result.selected_serving_label == "1 porcion [50 g]"
    assert result.values["energia_kcal"] == 125.0
    assert result.values["sal_g"] == 1.0

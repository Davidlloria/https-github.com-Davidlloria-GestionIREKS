from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.fatsecret_client import FatSecretApiError, FatSecretClient
from app.services.ingredient_nutrition_query_service import IngredientNutritionQueryService
from app.services.openai_settings_service import OpenAISettingsService


@dataclass
class IngredientFatSecretNutritionFlowResult:
    status: str
    message: str = ""
    source_query: str = ""
    barcode: str = ""
    query_options: list[str] = field(default_factory=list)
    foods: list[dict[str, Any]] = field(default_factory=list)
    food_labels: list[str] = field(default_factory=list)
    selected_food_label: str = ""
    selected_food: dict[str, Any] | None = None
    servings: list[dict[str, Any]] = field(default_factory=list)
    serving_labels: list[str] = field(default_factory=list)
    selected_serving_label: str = ""
    selected_serving: dict[str, Any] | None = None
    values: dict[str, float] = field(default_factory=dict)


class IngredientFatSecretNutritionFlowService:
    def __init__(
        self,
        *,
        nutrition_query_service: IngredientNutritionQueryService | None = None,
        fatsecret_client_factory: Callable[[], FatSecretClient] | type[FatSecretClient] = FatSecretClient,
        translation_settings_loader: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.nutrition_query_service = nutrition_query_service or IngredientNutritionQueryService()
        self.fatsecret_client_factory = fatsecret_client_factory
        self.translation_settings_loader = translation_settings_loader or self._load_translation_settings

    def build_query_options(self, source_query: str) -> IngredientFatSecretNutritionFlowResult:
        base = self.nutrition_query_service.normalize_query(source_query)
        if not base:
            return IngredientFatSecretNutritionFlowResult(status="no_query")

        settings = self.translation_settings_loader()
        query_options = self.nutrition_query_service.build_fatsecret_candidates(
            base,
            openai_api_key=str(settings.get("api_key") or "").strip(),
            use_ai_translation=bool(settings.get("use_ai_translation", False)),
        )
        if not query_options:
            return IngredientFatSecretNutritionFlowResult(status="no_query", source_query=base)
        return IngredientFatSecretNutritionFlowResult(
            status="query_options",
            source_query=base,
            query_options=query_options,
        )

    def search_food(self, chosen_query: str, *, page: int = 0, max_results: int = 20, region: str = "ES") -> IngredientFatSecretNutritionFlowResult:
        clean_query = self.nutrition_query_service.normalize_query(chosen_query)
        if not clean_query:
            return IngredientFatSecretNutritionFlowResult(status="no_query")

        client = self._build_client()
        try:
            rows = client.search_food(clean_query, page=page, max_results=max_results, region=region)
        except FatSecretApiError as exc:
            return IngredientFatSecretNutritionFlowResult(
                status="search_error",
                source_query=clean_query,
                message=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            return IngredientFatSecretNutritionFlowResult(
                status="search_error",
                source_query=clean_query,
                message=f"No se pudo consultar FatSecret.\n{exc}",
            )

        if not rows:
            return IngredientFatSecretNutritionFlowResult(
                status="no_results",
                source_query=clean_query,
                message=f"Sin resultados para: {clean_query}",
            )

        labels = [self._food_label(row, clean_query) for row in rows]
        return IngredientFatSecretNutritionFlowResult(
            status="foods_available",
            source_query=clean_query,
            foods=list(rows),
            food_labels=labels,
        )

    def load_barcode(
        self,
        barcode: str,
        *,
        region: str = "ES",
    ) -> IngredientFatSecretNutritionFlowResult:
        clean_barcode = self.nutrition_query_service.normalize_query(barcode)
        if not clean_barcode:
            return IngredientFatSecretNutritionFlowResult(status="barcode_cancelled")

        client = self._build_client()
        try:
            normalized = client.find_by_barcode(clean_barcode, region=region)
        except FatSecretApiError as exc:
            return IngredientFatSecretNutritionFlowResult(
                status="search_error",
                barcode=clean_barcode,
                message=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            return IngredientFatSecretNutritionFlowResult(
                status="search_error",
                barcode=clean_barcode,
                message=f"No se pudo consultar FatSecret.\n{exc}",
            )

        servings = list(normalized.get("servings") or [])
        if not servings:
            return IngredientFatSecretNutritionFlowResult(
                status="no_servings",
                barcode=clean_barcode,
                selected_food=normalized,
                message="El alimento no tiene raciones con datos nutricionales.",
            )

        serving_labels = [self._serving_label(serving) for serving in servings]
        if len(servings) == 1:
            selected_serving = servings[0]
            return IngredientFatSecretNutritionFlowResult(
                status="ready_to_apply",
                barcode=clean_barcode,
                selected_food=normalized,
                servings=servings,
                serving_labels=serving_labels,
                selected_serving_label=serving_labels[0],
                selected_serving=selected_serving,
                values=self.build_values_from_serving(selected_serving),
            )

        return IngredientFatSecretNutritionFlowResult(
            status="servings_available",
            barcode=clean_barcode,
            selected_food=normalized,
            servings=servings,
            serving_labels=serving_labels,
        )

    def load_selected_food(
        self,
        result: IngredientFatSecretNutritionFlowResult,
        selected_label: str,
        *,
        region: str = "ES",
        language: str = "es",
    ) -> IngredientFatSecretNutritionFlowResult:
        if result.status != "foods_available" or not result.foods:
            return IngredientFatSecretNutritionFlowResult(
                status="no_query",
                source_query=result.source_query,
            )

        label = str(selected_label or "").strip()
        if not label:
            return IngredientFatSecretNutritionFlowResult(
                status="no_query",
                source_query=result.source_query,
                foods=list(result.foods),
                food_labels=list(result.food_labels),
            )

        selected_idx = result.food_labels.index(label) if label in result.food_labels else -1
        if selected_idx < 0:
            return IngredientFatSecretNutritionFlowResult(
                status="no_query",
                source_query=result.source_query,
                foods=list(result.foods),
                food_labels=list(result.food_labels),
            )

        selected_food = result.foods[selected_idx]
        food_id = str(selected_food.get("food_id") or "").strip()
        if not food_id:
            return IngredientFatSecretNutritionFlowResult(
                status="no_food_id",
                source_query=result.source_query,
                foods=list(result.foods),
                food_labels=list(result.food_labels),
                selected_food_label=label,
                selected_food=selected_food,
                message="El resultado no incluye food_id.",
            )

        client = self._build_client()
        try:
            normalized = client.get_food(food_id, region=region, language=language)
        except FatSecretApiError as exc:
            return IngredientFatSecretNutritionFlowResult(
                status="search_error",
                source_query=result.source_query,
                foods=list(result.foods),
                food_labels=list(result.food_labels),
                selected_food_label=label,
                selected_food=selected_food,
                message=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            return IngredientFatSecretNutritionFlowResult(
                status="search_error",
                source_query=result.source_query,
                foods=list(result.foods),
                food_labels=list(result.food_labels),
                selected_food_label=label,
                selected_food=selected_food,
                message=f"No se pudo consultar FatSecret.\n{exc}",
            )

        servings = list(normalized.get("servings") or [])
        if not servings:
            return IngredientFatSecretNutritionFlowResult(
                status="no_servings",
                source_query=result.source_query,
                foods=list(result.foods),
                food_labels=list(result.food_labels),
                selected_food_label=label,
                selected_food=normalized,
                message="El alimento no tiene raciones con datos nutricionales.",
            )

        serving_labels = [self._serving_label(serving) for serving in servings]
        return IngredientFatSecretNutritionFlowResult(
            status="servings_available",
            source_query=result.source_query,
            foods=list(result.foods),
            food_labels=list(result.food_labels),
            selected_food_label=label,
            selected_food=normalized,
            servings=servings,
            serving_labels=serving_labels,
        )

    def resolve_selected_serving(
        self,
        result: IngredientFatSecretNutritionFlowResult,
        selected_label: str,
    ) -> IngredientFatSecretNutritionFlowResult:
        if result.status != "servings_available" or not result.servings:
            return IngredientFatSecretNutritionFlowResult(
                status="no_query",
                source_query=result.source_query,
            )

        label = str(selected_label or "").strip()
        if not label:
            return IngredientFatSecretNutritionFlowResult(
                status="no_query",
                source_query=result.source_query,
                foods=list(result.foods),
                food_labels=list(result.food_labels),
                selected_food_label=result.selected_food_label,
                selected_food=result.selected_food,
                servings=list(result.servings),
                serving_labels=list(result.serving_labels),
            )

        selected_idx = result.serving_labels.index(label) if label in result.serving_labels else -1
        if selected_idx < 0:
            return IngredientFatSecretNutritionFlowResult(
                status="no_query",
                source_query=result.source_query,
                foods=list(result.foods),
                food_labels=list(result.food_labels),
                selected_food_label=result.selected_food_label,
                selected_food=result.selected_food,
                servings=list(result.servings),
                serving_labels=list(result.serving_labels),
            )

        selected_serving = result.servings[selected_idx]
        return IngredientFatSecretNutritionFlowResult(
            status="ready_to_apply",
            source_query=result.source_query,
            barcode=result.barcode,
            foods=list(result.foods),
            food_labels=list(result.food_labels),
            selected_food_label=result.selected_food_label,
            selected_food=result.selected_food,
            servings=list(result.servings),
            serving_labels=list(result.serving_labels),
            selected_serving_label=label,
            selected_serving=selected_serving,
            values=self.build_values_from_serving(selected_serving),
        )

    def build_values_from_serving(self, serving: dict[str, Any]) -> dict[str, float]:
        sodium_mg = float(serving.get("sodium_mg") or 0.0)
        return {
            "energia_kcal": float(serving.get("calories_kcal") or 0.0),
            "energia_kj": float(serving.get("calories_kcal") or 0.0) * 4.184,
            "grasas_g": float(serving.get("fat_g") or 0.0),
            "saturadas_g": float(serving.get("saturated_fat_g") or 0.0),
            "hidratos_g": float(serving.get("carbohydrates_g") or 0.0),
            "azucares_g": float(serving.get("sugars_g") or 0.0),
            "fibra_g": float(serving.get("fiber_g") or 0.0),
            "proteinas_g": float(serving.get("protein_g") or 0.0),
            "sal_g": (sodium_mg / 1000.0) * 2.5,
        }

    def build_barcode_servings(self, barcode_result: IngredientFatSecretNutritionFlowResult) -> IngredientFatSecretNutritionFlowResult:
        if barcode_result.status != "servings_available" or not barcode_result.servings:
            return IngredientFatSecretNutritionFlowResult(
                status="no_query",
                barcode=barcode_result.barcode,
            )
        return IngredientFatSecretNutritionFlowResult(
            status="servings_available",
            barcode=barcode_result.barcode,
            selected_food=barcode_result.selected_food,
            servings=list(barcode_result.servings),
            serving_labels=[self._serving_label(serving) for serving in barcode_result.servings],
        )

    def _build_client(self) -> FatSecretClient:
        return self.fatsecret_client_factory()

    def _load_translation_settings(self) -> dict[str, Any]:
        try:
            loaded = OpenAISettingsService().load()
        except Exception:
            loaded = {"api_key": "", "use_ai_translation": False}
        return {
            "api_key": str(loaded.get("api_key") or "").strip(),
            "use_ai_translation": bool(loaded.get("use_ai_translation", False)),
        }

    @staticmethod
    def _food_label(row: dict[str, Any], chosen_query: str) -> str:
        name = str(row.get("food_name") or "").strip()
        brand = str(row.get("brand_name") or "").strip()
        desc = str(row.get("food_description") or "").strip()
        q_used = str(row.get("query_used") or chosen_query).strip()
        return f"{name}{f' ({brand})' if brand else ''} - {desc}  [query: {q_used}]"

    @staticmethod
    def _serving_label(serving: dict[str, Any]) -> str:
        desc = str(serving.get("description") or "").strip()
        metric_amount = float(serving.get("metric_amount") or 0.0)
        metric_unit = str(serving.get("metric_unit") or "").strip()
        return f"{desc} [{metric_amount:g} {metric_unit}]"

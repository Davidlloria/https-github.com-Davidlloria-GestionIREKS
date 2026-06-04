from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.fdc_nutrition_service import FdcFoodCandidate, FdcNutritionService
from app.services.ingredient_nutrition_query_service import IngredientNutritionQueryService
from app.services.openai_settings_service import OpenAISettingsService


@dataclass
class IngredientFdcNutritionFlowResult:
    status: str
    message: str = ""
    source_query: str = ""
    query_options: list[str] = field(default_factory=list)
    candidates: list[FdcFoodCandidate] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    selected_label: str = ""
    selected_candidate: FdcFoodCandidate | None = None


class IngredientFdcNutritionFlowService:
    def __init__(
        self,
        *,
        nutrition_query_service: IngredientNutritionQueryService | None = None,
        fdc_service_factory: Callable[[], FdcNutritionService] | type[FdcNutritionService] = FdcNutritionService,
        translation_settings_loader: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.nutrition_query_service = nutrition_query_service or IngredientNutritionQueryService()
        self.fdc_service_factory = fdc_service_factory
        self.translation_settings_loader = translation_settings_loader or self._load_translation_settings

    def build_query_options(self, source_query: str) -> IngredientFdcNutritionFlowResult:
        base = self.nutrition_query_service.normalize_query(source_query)
        if not base:
            return IngredientFdcNutritionFlowResult(status="no_query")

        settings = self.translation_settings_loader()
        query_options = self.nutrition_query_service.build_fdc_candidates(
            base,
            openai_api_key=str(settings.get("api_key") or "").strip(),
            use_ai_translation=bool(settings.get("use_ai_translation", False)),
        )
        if not query_options:
            return IngredientFdcNutritionFlowResult(status="no_query", source_query=base)
        return IngredientFdcNutritionFlowResult(
            status="query_options",
            source_query=base,
            query_options=query_options,
        )

    def fetch_candidates(self, chosen_query: str, *, limit: int = 10) -> IngredientFdcNutritionFlowResult:
        clean_query = self.nutrition_query_service.normalize_query(chosen_query)
        if not clean_query:
            return IngredientFdcNutritionFlowResult(status="no_query")

        service = self._build_fdc_service()
        service.use_ai_translation = False
        try:
            candidates = service.fetch_candidates(clean_query, limit=limit)
        except Exception as exc:  # noqa: BLE001
            return IngredientFdcNutritionFlowResult(
                status="error",
                source_query=clean_query,
                message=f"No se pudo consultar FDC.\n{exc}",
            )

        if not candidates:
            return IngredientFdcNutritionFlowResult(
                status="no_results",
                source_query=clean_query,
                message=f"Sin resultados FDC para: {clean_query}",
            )

        labels = [self._candidate_label(candidate) for candidate in candidates]
        return IngredientFdcNutritionFlowResult(
            status="candidates",
            source_query=clean_query,
            candidates=list(candidates),
            labels=labels,
        )

    def resolve_selected_candidate(
        self,
        result: IngredientFdcNutritionFlowResult,
        selected_label: str,
    ) -> IngredientFdcNutritionFlowResult:
        if result.status != "candidates" or not result.candidates:
            return IngredientFdcNutritionFlowResult(
                status="no_query",
                source_query=result.source_query,
            )
        label = str(selected_label or "").strip()
        if not label:
            return IngredientFdcNutritionFlowResult(
                status="no_query",
                source_query=result.source_query,
                candidates=list(result.candidates),
                labels=list(result.labels),
            )
        selected_idx = result.labels.index(label) if label in result.labels else -1
        if selected_idx < 0:
            return IngredientFdcNutritionFlowResult(
                status="no_query",
                source_query=result.source_query,
                candidates=list(result.candidates),
                labels=list(result.labels),
            )
        selected_candidate = result.candidates[selected_idx]
        return IngredientFdcNutritionFlowResult(
            status="selected",
            source_query=result.source_query,
            candidates=list(result.candidates),
            labels=list(result.labels),
            selected_label=label,
            selected_candidate=selected_candidate,
        )

    def _build_fdc_service(self) -> FdcNutritionService:
        return self.fdc_service_factory()

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
    def _candidate_label(candidate: FdcFoodCandidate) -> str:
        return f"{candidate.label}  [query: {candidate.query_used}]"

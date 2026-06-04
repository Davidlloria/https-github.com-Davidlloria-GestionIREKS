from __future__ import annotations

from dataclasses import dataclass, field

from app.services.openai_nutrition_service import OpenAINutritionResult, OpenAINutritionService


@dataclass
class IngredientChatGPTNutritionFlowResult:
    status: str
    message: str = ""
    query: str = ""
    values: dict[str, float] = field(default_factory=dict)


class IngredientChatGPTNutritionFlowService:
    def __init__(self, *, openai_service: OpenAINutritionService | None = None) -> None:
        self.openai_service = openai_service or OpenAINutritionService()

    def load_nutrition(self, query: str) -> IngredientChatGPTNutritionFlowResult:
        q = str(query or "").strip()
        if not q:
            return IngredientChatGPTNutritionFlowResult(status="no_query", message="Consulta vacía.")
        try:
            result = self.openai_service.fetch_for_query(q)
        except Exception as exc:  # noqa: BLE001
            return IngredientChatGPTNutritionFlowResult(
                status="error",
                message=f"No se pudo consultar OpenAI.\n{exc}",
                query=q,
            )
        if not isinstance(result, OpenAINutritionResult):
            ok = bool(getattr(result, "ok", False))
            message = str(getattr(result, "message", "") or "")
            values = dict(getattr(result, "values", {}) or {})
        else:
            ok = bool(result.ok)
            message = str(result.message or "")
            values = dict(result.values or {})
        if not ok:
            return IngredientChatGPTNutritionFlowResult(
                status="service_error",
                message=message,
                query=q,
                values=values,
            )
        return IngredientChatGPTNutritionFlowResult(
            status="ready_to_apply",
            message=message or "Valores nutricionales cargados desde ChatGPT.",
            query=q,
            values=values,
        )

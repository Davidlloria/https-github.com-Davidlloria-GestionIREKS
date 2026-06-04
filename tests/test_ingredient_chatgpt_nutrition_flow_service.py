from __future__ import annotations

from app.services.ingredient_chatgpt_nutrition_flow_service import IngredientChatGPTNutritionFlowService
from app.services.openai_nutrition_service import OpenAINutritionResult


class _FakeOpenAINutritionService:
    def __init__(self, result: object | None = None, *, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[str] = []

    def fetch_for_query(self, query: str) -> object:
        self.calls.append(query)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return OpenAINutritionResult(True, "Valores nutricionales cargados desde ChatGPT.", {})


def test_empty_query_returns_no_query() -> None:
    fake = _FakeOpenAINutritionService()
    service = IngredientChatGPTNutritionFlowService(openai_service=fake)

    result = service.load_nutrition("")

    assert result.status == "no_query"
    assert result.message == "Consulta vacía."
    assert fake.calls == []


def test_service_exception_returns_error() -> None:
    fake = _FakeOpenAINutritionService(error=RuntimeError("boom"))
    service = IngredientChatGPTNutritionFlowService(openai_service=fake)

    result = service.load_nutrition("tomate")

    assert result.status == "error"
    assert "No se pudo consultar OpenAI." in result.message
    assert "boom" in result.message
    assert fake.calls == ["tomate"]


def test_service_ok_false_returns_service_error() -> None:
    fake = _FakeOpenAINutritionService(
        result=OpenAINutritionResult(False, "OpenAI no devolvió un JSON nutricional válido.", {"energia_kj": 0.0}),
    )
    service = IngredientChatGPTNutritionFlowService(openai_service=fake)

    result = service.load_nutrition("pollo")

    assert result.status == "service_error"
    assert result.message == "OpenAI no devolvió un JSON nutricional válido."
    assert result.values == {"energia_kj": 0.0}
    assert fake.calls == ["pollo"]


def test_service_ok_true_returns_ready_to_apply_and_preserves_values() -> None:
    values = {
        "energia_kj": 100.0,
        "energia_kcal": 24.0,
        "grasas_g": 1.2,
        "saturadas_g": 0.3,
        "hidratos_g": 2.4,
        "azucares_g": 1.1,
        "fibra_g": 0.8,
        "proteinas_g": 3.5,
        "sal_g": 0.2,
    }
    fake = _FakeOpenAINutritionService(
        result=OpenAINutritionResult(True, "Valores nutricionales cargados desde ChatGPT.", values),
    )
    service = IngredientChatGPTNutritionFlowService(openai_service=fake)

    result = service.load_nutrition("lentejas")

    assert result.status == "ready_to_apply"
    assert result.message == "Valores nutricionales cargados desde ChatGPT."
    assert result.query == "lentejas"
    assert result.values == values
    assert fake.calls == ["lentejas"]


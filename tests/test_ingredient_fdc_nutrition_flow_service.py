from __future__ import annotations

from app.services.fdc_nutrition_service import FdcFoodCandidate
from app.services.ingredient_fdc_nutrition_flow_service import (
    IngredientFdcNutritionFlowResult,
    IngredientFdcNutritionFlowService,
)
from app.services.ingredient_nutrition_query_service import IngredientNutritionQueryService


class _FakeFdcService:
    def __init__(self, *, candidates: list[FdcFoodCandidate] | None = None, exc: Exception | None = None) -> None:
        self.candidates = list(candidates or [])
        self.exc = exc
        self.calls: list[tuple[str, int, bool]] = []
        self.use_ai_translation = True

    def fetch_candidates(self, query: str, limit: int = 10) -> list[FdcFoodCandidate]:
        self.calls.append((query, limit, self.use_ai_translation))
        if self.exc is not None:
            raise self.exc
        return list(self.candidates)


def _candidate(label: str, query_used: str, energia_kcal: float) -> FdcFoodCandidate:
    return FdcFoodCandidate(
        label=label,
        query_used=query_used,
        values={"energia_kcal": energia_kcal},
    )


def test_build_query_options_returns_no_query_for_empty_input() -> None:
    service = IngredientFdcNutritionFlowService()

    result = service.build_query_options("   ")

    assert result.status == "no_query"
    assert result.query_options == []


def test_build_query_options_uses_query_service_and_translation_settings() -> None:
    def fake_loader() -> dict[str, object]:
        return {"api_key": "fake-key", "use_ai_translation": False}

    service = IngredientFdcNutritionFlowService(
        nutrition_query_service=IngredientNutritionQueryService(),
        translation_settings_loader=fake_loader,
    )

    result = service.build_query_options("harina pan")

    assert result.status == "query_options"
    assert result.query_options == ["harina pan", "flour"]


def test_fetch_candidates_returns_error_when_provider_raises() -> None:
    fake_fdc = _FakeFdcService(exc=RuntimeError("boom"))
    service = IngredientFdcNutritionFlowService(
        fdc_service_factory=lambda: fake_fdc,
        translation_settings_loader=lambda: {"api_key": "", "use_ai_translation": False},
    )

    result = service.fetch_candidates("harina pan", limit=10)

    assert result.status == "error"
    assert "No se pudo consultar FDC." in result.message
    assert "boom" in result.message
    assert fake_fdc.calls == [("harina pan", 10, False)]


def test_fetch_candidates_returns_no_results_when_provider_returns_empty() -> None:
    fake_fdc = _FakeFdcService(candidates=[])
    service = IngredientFdcNutritionFlowService(
        fdc_service_factory=lambda: fake_fdc,
        translation_settings_loader=lambda: {"api_key": "", "use_ai_translation": False},
    )

    result = service.fetch_candidates("harina pan", limit=10)

    assert result.status == "no_results"
    assert result.message == "Sin resultados FDC para: harina pan"
    assert fake_fdc.calls == [("harina pan", 10, False)]


def test_fetch_candidates_returns_labels_for_available_candidates() -> None:
    first = _candidate("Harina pan", "harina pan", 123.4)
    second = _candidate("Pan blanco", "bread", 200.0)
    fake_fdc = _FakeFdcService(candidates=[first, second])
    service = IngredientFdcNutritionFlowService(
        fdc_service_factory=lambda: fake_fdc,
        translation_settings_loader=lambda: {"api_key": "", "use_ai_translation": False},
    )

    result = service.fetch_candidates("harina pan", limit=10)

    assert result.status == "candidates"
    assert result.labels == [
        "Harina pan  [query: harina pan]",
        "Pan blanco  [query: bread]",
    ]
    assert result.candidates == [first, second]
    assert fake_fdc.calls == [("harina pan", 10, False)]


def test_resolve_selected_candidate_preserves_label_and_candidate() -> None:
    first = _candidate("Harina pan", "harina pan", 123.4)
    second = _candidate("Pan blanco", "bread", 200.0)
    result = IngredientFdcNutritionFlowResult(
        status="candidates",
        source_query="harina pan",
        candidates=[first, second],
        labels=[
            "Harina pan  [query: harina pan]",
            "Pan blanco  [query: bread]",
        ],
    )
    service = IngredientFdcNutritionFlowService()

    selected = service.resolve_selected_candidate(result, "Pan blanco  [query: bread]")

    assert selected.status == "selected"
    assert selected.selected_label == "Pan blanco  [query: bread]"
    assert selected.selected_candidate == second
    assert selected.candidates == [first, second]


def test_injected_dependencies_are_used_without_real_external_calls() -> None:
    fake_fdc = _FakeFdcService(candidates=[_candidate("Harina pan", "harina pan", 111.0)])
    loader_calls = {"count": 0}

    def fake_loader() -> dict[str, object]:
        loader_calls["count"] += 1
        return {"api_key": "fake-key", "use_ai_translation": True}

    service = IngredientFdcNutritionFlowService(
        fdc_service_factory=lambda: fake_fdc,
        translation_settings_loader=fake_loader,
    )

    query_result = service.build_query_options("harina pan")
    candidates_result = service.fetch_candidates(query_result.query_options[0], limit=10)
    selected = service.resolve_selected_candidate(candidates_result, candidates_result.labels[0])

    assert loader_calls["count"] == 1
    assert fake_fdc.calls == [("harina pan", 10, False)]
    assert selected.selected_candidate is not None

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.technical_consultant_acceptance_service import (
    TechnicalAcceptanceBaseline,
    TechnicalAcceptanceCase,
    TechnicalAcceptanceExpectedOutcome,
    TechnicalConsultantAcceptanceError,
    TechnicalConsultantAcceptanceService,
    load_technical_acceptance_baseline,
    parse_technical_acceptance_baseline,
)
from app.services.technical_product_comparison_service import (
    TechnicalProductProfile,
    TechnicalProductProfileSource,
)
from app.services.technical_product_decision_service import (
    TechnicalProductDecision,
    TechnicalProductDecisionOutcome,
    TechnicalRequirement,
)
from scripts.evaluate_technical_consultant_corpus import render_text_report


_HIGH_HYDRATION = TechnicalRequirement("high_hydration", "alta hidratación")
_FREEZING = TechnicalRequirement("freezing", "congelación")


def _profile(
    product_name: str,
    source_name: str,
) -> TechnicalProductProfile:
    source = TechnicalProductProfileSource(
        source_id="P1-S1",
        document_id=(product_name.encode().hex() + ("0" * 64))[:64],
        name=source_name,
        relative_path=f"CALIDAD/FICHAS TECNICAS/IREKS/{source_name}",
        page_number=1,
    )
    return TechnicalProductProfile(
        product_key=product_name.casefold(),
        product_name=product_name,
        application="Aplicación documentada",
        dosage=None,
        minimum_shelf_life=None,
        storage_conditions=None,
        ingredients=None,
        retrieval_score=0.01,
        semantic_similarity=0.8,
        methods=("semantic",),
        sources=(source,),
        missing_fields=(
            "dosage",
            "minimum_shelf_life",
            "storage_conditions",
            "ingredients",
        ),
    )


def _decision(
    product_name: str,
    status: str,
    source_name: str,
) -> TechnicalProductDecision:
    matched = (_HIGH_HYDRATION,) if status in {"recommended", "complementary"} else ()
    return TechnicalProductDecision(
        status=status,  # type: ignore[arg-type]
        profile=_profile(product_name, source_name),
        matched_requirements=matched,
        missing_requirements=(),
        reason="Decisión de evaluación.",
    )


def _outcome(
    *,
    requirements=(_HIGH_HYDRATION,),
    decisions=(),
    mode="hybrid",
    warnings=(),
) -> TechnicalProductDecisionOutcome:
    return TechnicalProductDecisionOutcome(
        query="consulta",
        requirements=tuple(requirements),
        decisions=tuple(decisions),
        message="Resultado.",
        used_lexical=mode in {"lexical", "hybrid"},
        used_semantic=mode in {"semantic", "hybrid"},
        warnings=tuple(warnings),
        mode=mode,
    )


class _FakeDecisionService:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = []

    def decide(self, query: str, *, limit: int = 6):
        self.calls.append({"query": query, "limit": limit})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _baseline(
    *,
    model: str = "embeddinggemma",
    outcomes: tuple[TechnicalAcceptanceExpectedOutcome, ...] | None = None,
) -> TechnicalAcceptanceBaseline:
    expected = outcomes or (
        TechnicalAcceptanceExpectedOutcome(
            "PRODUCTO A",
            "recommended",
            ("producto-a.pdf",),
        ),
    )
    return TechnicalAcceptanceBaseline(
        version=1,
        expected_embedding_model=model,
        cases=(
            TechnicalAcceptanceCase(
                case_id="case-a",
                query="pan de alta hidratación",
                expected_requirements=("high_hydration",),
                expected_mode="hybrid",
                expected_outcomes=expected,
                limit=4,
            ),
        ),
    )


def test_versioned_real_baseline_loads_with_unique_cases_and_sources() -> None:
    path = (
        Path(__file__).parents[1]
        / "evaluation"
        / "technical_consultant_real_corpus.json"
    )

    baseline = load_technical_acceptance_baseline(path)

    assert baseline.version == 1
    assert baseline.expected_embedding_model == "embeddinggemma"
    assert [case.case_id for case in baseline.cases] == [
        "high-hydration",
        "packaged-bread-mold",
        "precooked-frozen",
        "vegan-gluten-lactose-free",
    ]
    assert all(
        outcome.source_names
        for case in baseline.cases
        for outcome in case.expected_outcomes
    )


@pytest.mark.parametrize(
    "payload, message",
    [
        ([], "objeto JSON"),
        ({"version": 2}, "Versión"),
        (
            {
                "version": 1,
                "expected_embedding_model": "embeddinggemma",
                "cases": [],
            },
            "al menos un caso",
        ),
    ],
)
def test_invalid_baseline_shape_is_rejected(payload, message: str) -> None:
    with pytest.raises(TechnicalConsultantAcceptanceError, match=message):
        parse_technical_acceptance_baseline(payload)


def test_matching_real_outcome_passes_and_is_json_serializable() -> None:
    decision = _FakeDecisionService(
        _outcome(
            decisions=(
                _decision("PRODUCTO A", "recommended", "producto-a.pdf"),
            )
        )
    )
    service = TechnicalConsultantAcceptanceService(
        decision,  # type: ignore[arg-type]
        embedding_model="embeddinggemma",
        clock=lambda: datetime(2026, 8, 30, tzinfo=timezone.utc),
    )

    report = service.evaluate(_baseline())

    assert report.passed
    assert report.global_drifts == ()
    assert report.cases[0].passed
    assert report.cases[0].drifts == ()
    assert decision.calls == [{"query": "pan de alta hidratación", "limit": 4}]
    assert json.loads(json.dumps(report.to_dict()))["passed"] is True
    assert "PASS case-a" in render_text_report(report)


def test_drift_report_identifies_every_changed_contract_field() -> None:
    decision = _FakeDecisionService(
        _outcome(
            requirements=(_FREEZING,),
            decisions=(
                _decision("PRODUCTO A", "complementary", "producto-cambiado.pdf"),
                _decision("PRODUCTO B", "recommended", "producto-b.pdf"),
            ),
            mode="lexical",
            warnings=("fallback semántico",),
        )
    )
    service = TechnicalConsultantAcceptanceService(
        decision,  # type: ignore[arg-type]
        embedding_model="otro-modelo",
    )

    report = service.evaluate(_baseline())

    assert not report.passed
    assert report.global_drifts[0].field == "embedding_model"
    fields = {drift.field for drift in report.cases[0].drifts}
    assert fields == {
        "requirements",
        "retrieval_mode",
        "product_order",
        "unexpected_products",
        "status:PRODUCTO A",
        "sources:PRODUCTO A",
        "warnings",
    }
    assert "DRIFT case-a" in render_text_report(report)


def test_missing_product_and_unknown_case_selection_are_reported() -> None:
    service = TechnicalConsultantAcceptanceService(
        _FakeDecisionService(_outcome()),  # type: ignore[arg-type]
        embedding_model="embeddinggemma",
    )

    report = service.evaluate(_baseline())

    fields = {drift.field for drift in report.cases[0].drifts}
    assert "missing_products" in fields
    with pytest.raises(TechnicalConsultantAcceptanceError, match="desconocidos"):
        service.evaluate(_baseline(), case_ids=("no-existe",))


def test_execution_error_is_redacted_in_report() -> None:
    service = TechnicalConsultantAcceptanceService(
        _FakeDecisionService(RuntimeError("Fallo en C:/privado/index.bin")),  # type: ignore[arg-type]
        embedding_model="embeddinggemma",
    )

    report = service.evaluate(_baseline())

    assert not report.passed
    drift = report.cases[0].drifts[0]
    assert drift.field == "execution_error"
    assert "C:/privado" not in str(drift.actual)
    assert "[RUTA OMITIDA]" in str(drift.actual)

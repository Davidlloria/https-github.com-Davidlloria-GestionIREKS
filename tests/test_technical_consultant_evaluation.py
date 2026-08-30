from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.technical_product_comparison_service import (
    TechnicalProductComparisonOutcome,
    TechnicalProductProfile,
    TechnicalProductProfileSource,
)
from app.services.technical_product_decision_service import (
    TechnicalProductDecisionService,
)


_EVALUATION_PATH = (
    Path(__file__).parent / "fixtures" / "technical_consultant_evaluation.json"
)
_EVALUATION = json.loads(_EVALUATION_PATH.read_text(encoding="utf-8"))


class _EvaluationComparison:
    def __init__(self, profile: TechnicalProductProfile) -> None:
        self.profile = profile

    def compare(
        self,
        query: str,
        *,
        limit: int = 6,
    ) -> TechnicalProductComparisonOutcome:
        return TechnicalProductComparisonOutcome(
            query=query,
            profiles=(self.profile,),
            used_lexical=True,
            mode="lexical",
        )


def _profile(case: dict[str, object]) -> TechnicalProductProfile:
    case_id = str(case["id"])
    source = TechnicalProductProfileSource(
        source_id="P1-S1",
        document_id=(case_id.encode().hex() + ("0" * 64))[:64],
        name=f"{case_id}.pdf",
        relative_path=f"CALIDAD/FICHAS TECNICAS/IREKS/{case_id}.pdf",
        page_number=1,
    )
    return TechnicalProductProfile(
        product_key=case_id,
        product_name=case_id,
        application=str(case["application"]),
        dosage=None,
        minimum_shelf_life=None,
        storage_conditions=None,
        ingredients=None,
        retrieval_score=0.01,
        semantic_similarity=None,
        methods=("lexical",),
        sources=(source,),
        missing_fields=(
            "dosage",
            "minimum_shelf_life",
            "storage_conditions",
            "ingredients",
        ),
    )


@pytest.mark.parametrize(
    "case",
    _EVALUATION["requirement_cases"],
    ids=lambda case: case["id"],
)
def test_requirement_evaluation_case(case: dict[str, object]) -> None:
    requirements = TechnicalProductDecisionService.detect_requirements(
        str(case["query"])
    )

    assert [requirement.key for requirement in requirements] == case["expected"]


@pytest.mark.parametrize(
    "case",
    _EVALUATION["decision_cases"],
    ids=lambda case: case["id"],
)
def test_documented_application_evaluation_case(case: dict[str, object]) -> None:
    service = TechnicalProductDecisionService(
        _EvaluationComparison(_profile(case))
    )

    outcome = service.decide(str(case["query"]))

    assert len(outcome.decisions) == 1
    decision = outcome.decisions[0]
    assert decision.status == case["expected_status"]
    assert [
        requirement.key for requirement in decision.matched_requirements
    ] == case["expected_matched"]


def test_evaluation_set_has_stable_version_unique_ids_and_negative_cases() -> None:
    assert _EVALUATION["version"] == 1
    cases = (
        *_EVALUATION["requirement_cases"],
        *_EVALUATION["decision_cases"],
    )
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert len(_EVALUATION["requirement_cases"]) >= 25
    assert any(not case["expected"] for case in _EVALUATION["requirement_cases"])

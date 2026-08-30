from __future__ import annotations

import json

from app.services.local_ai_service import LocalAIResult
from app.services.technical_consultant_service import TechnicalConsultantService
from app.services.technical_product_comparison_service import (
    TechnicalProductProfile,
    TechnicalProductProfileSource,
)
from app.services.technical_product_decision_service import (
    TechnicalProductDecision,
    TechnicalProductDecisionOutcome,
    TechnicalRequirement,
)


_PRECOOKED = TechnicalRequirement("precooked", "precocción")
_FREEZING = TechnicalRequirement("freezing", "congelación")


def _profile(
    product_name: str,
    *,
    source_id: str,
    application: str,
    dosage: str | None = "10 g por kg de harina",
) -> TechnicalProductProfile:
    source = TechnicalProductProfileSource(
        source_id=source_id,
        document_id=(source_id.encode().hex() + ("0" * 64))[:64],
        name=f"{product_name}.pdf",
        relative_path=f"CALIDAD/FICHAS TECNICAS/IREKS/{product_name}.pdf",
        page_number=1,
    )
    return TechnicalProductProfile(
        product_key=product_name.casefold(),
        product_name=product_name,
        application=application,
        dosage=dosage,
        minimum_shelf_life="12 meses",
        storage_conditions="lugar fresco y seco",
        ingredients=None,
        retrieval_score=0.02,
        semantic_similarity=0.8,
        methods=("semantic",),
        sources=(source,),
        missing_fields=("ingredients",),
    )


def _decision(
    profile: TechnicalProductProfile,
    *,
    status: str,
    matched=(),
    missing=(),
    reason: str,
) -> TechnicalProductDecision:
    return TechnicalProductDecision(
        status=status,
        profile=profile,
        matched_requirements=tuple(matched),
        missing_requirements=tuple(missing),
        reason=reason,
    )


class _FakeDecisionService:
    def __init__(self, outcome: TechnicalProductDecisionOutcome):
        self.outcome = outcome
        self.calls = []

    def decide(self, question, *, limit=6):
        self.calls.append({"question": question, "limit": limit})
        return self.outcome


class _FakeAI:
    def __init__(self, result: LocalAIResult, *, enabled=True):
        self.result = result
        self.enabled = enabled
        self.calls = []

    def generate_json(self, prompt, *, schema=None, max_tokens=400):
        self.calls.append(
            {"prompt": prompt, "schema": schema, "max_tokens": max_tokens}
        )
        return self.result


def _outcome(
    decisions=(),
    *,
    requirements=(_PRECOOKED, _FREEZING),
    message="Conclusión determinista.",
    warnings=(),
    mode="hybrid",
) -> TechnicalProductDecisionOutcome:
    return TechnicalProductDecisionOutcome(
        query="consulta",
        requirements=tuple(requirements),
        decisions=tuple(decisions),
        message=message,
        used_lexical=mode in {"lexical", "hybrid"},
        used_semantic=mode in {"semantic", "hybrid"},
        warnings=tuple(warnings),
        mode=mode,
    )


def test_empty_question_calls_neither_decision_nor_ai() -> None:
    decision = _FakeDecisionService(_outcome())
    ai = _FakeAI(LocalAIResult(True, "{}"))
    service = TechnicalConsultantService(decision, ai)

    result = service.consult("  ")

    assert not result.ok
    assert decision.calls == []
    assert ai.calls == []


def test_unknown_requirements_return_clarification_without_ai() -> None:
    decision = _FakeDecisionService(
        _outcome(
            requirements=(),
            message="Faltan requisitos técnicos reconocibles.",
        )
    )
    ai = _FakeAI(LocalAIResult(True, "{}"))
    service = TechnicalConsultantService(decision, ai)

    result = service.consult("Quiero mejorar mi pan")

    assert result.ok and result.needs_clarification
    assert len(result.clarification_questions) == 3
    assert "proceso" in result.clarification_questions[0]
    assert not result.used_ai
    assert ai.calls == []


def test_no_relevant_products_returns_decision_message_without_ai() -> None:
    unrelated = _profile(
        "MAÍZ",
        source_id="P1-S1",
        application="Mix para pan de maíz",
    )
    rejected = _decision(
        unrelated,
        status="not_supported",
        missing=(_PRECOOKED, _FREEZING),
        reason="No confirma los requisitos.",
    )
    decision = _FakeDecisionService(
        _outcome([rejected], message="Ninguna ficha confirma los requisitos.")
    )
    ai = _FakeAI(LocalAIResult(True, "{}"))
    service = TechnicalConsultantService(decision, ai)

    result = service.consult("pan precocido congelado")

    assert result.ok
    assert result.answer == "Ninguna ficha confirma los requisitos."
    assert result.products == () and result.sources == ()
    assert ai.calls == []


def test_disabled_ai_returns_deterministic_products_and_sources() -> None:
    profile = _profile(
        "PREBACK",
        source_id="P1-S1",
        application="Mejorante para pan precocido",
        dosage="10 a 30 g por kg de harina",
    )
    complementary = _decision(
        profile,
        status="complementary",
        matched=(_PRECOOKED,),
        missing=(_FREEZING,),
        reason="Confirma precocción, pero no congelación.",
    )
    decision = _FakeDecisionService(_outcome([complementary]))
    ai = _FakeAI(LocalAIResult(False, ""), enabled=False)
    service = TechnicalConsultantService(decision, ai)

    result = service.consult("pan precocido congelado")

    assert result.ok and not result.used_ai
    assert result.products[0].dosage == "10 a 30 g por kg de harina"
    assert result.products[0].status == "complementary"
    assert result.sources[0].source_id == "P1-S1"
    assert "PREBACK" in result.answer
    assert ai.calls == []


def test_valid_ai_wording_uses_only_valid_cited_sources() -> None:
    profile = _profile(
        "PREBACK",
        source_id="P1-S1",
        application="Mejorante para pan precocido",
    )
    complementary = _decision(
        profile,
        status="complementary",
        matched=(_PRECOOKED,),
        missing=(_FREEZING,),
        reason="Confirma precocción, pero no congelación.",
    )
    decision = _FakeDecisionService(_outcome([complementary]))
    ai = _FakeAI(
        LocalAIResult(
            True,
            json.dumps(
                {
                    "answer": "PREBACK cubre la precocción, no toda la necesidad.",
                    "citations": ["P1-S1"],
                }
            ),
        )
    )
    service = TechnicalConsultantService(decision, ai)

    result = service.consult("pan precocido congelado", limit=4)

    assert result.ok and result.used_ai
    assert result.answer.startswith("PREBACK")
    assert [source.source_id for source in result.sources] == ["P1-S1"]
    assert decision.calls == [{"question": "pan precocido congelado", "limit": 4}]
    assert ai.calls[0]["max_tokens"] == 600
    assert ai.calls[0]["schema"]["properties"]["citations"]["items"]["enum"] == [
        "P1-S1"
    ]


def test_prompt_contains_verified_decisions_and_safety_limits() -> None:
    profile = _profile(
        "PREBACK",
        source_id="P1-S1",
        application="Mejorante para pan precocido",
        dosage="10 a 30 g por kg de harina",
    )
    complementary = _decision(
        profile,
        status="complementary",
        matched=(_PRECOOKED,),
        missing=(_FREEZING,),
        reason="Confirma precocción, pero no congelación.",
    )
    ai = _FakeAI(
        LocalAIResult(
            True,
            '{"answer":"Resumen","citations":["P1-S1"]}',
        )
    )
    service = TechnicalConsultantService(
        _FakeDecisionService(_outcome([complementary])),
        ai,
    )

    service.consult("pan precocido congelado")

    prompt = ai.calls[0]["prompt"]
    assert "Estado verificado: complementary" in prompt
    assert "10 a 30 g por kg de harina" in prompt
    assert "No infieras que varios productos pueden combinarse" in prompt
    assert "C:/secreto" not in prompt


def test_invalid_json_or_invalid_citation_uses_deterministic_fallback() -> None:
    profile = _profile(
        "PREBACK",
        source_id="P1-S1",
        application="Mejorante para pan precocido",
    )
    complementary = _decision(
        profile,
        status="complementary",
        matched=(_PRECOOKED,),
        missing=(_FREEZING,),
        reason="Confirma precocción, pero no congelación.",
    )
    decision = _FakeDecisionService(_outcome([complementary]))

    for text in (
        "no es json",
        '{"answer":"Inventado","citations":["S999"]}',
        '{"answer":"Sin fuentes","citations":[]}',
    ):
        ai = _FakeAI(LocalAIResult(True, text))
        result = TechnicalConsultantService(decision, ai).consult(
            "pan precocido congelado"
        )
        assert result.ok and not result.used_ai
        assert "PREBACK" in result.answer
        assert result.sources[0].source_id == "P1-S1"
        assert "no válidas" in result.warnings[-1]


def test_ai_error_uses_safe_fallback_and_preserves_retrieval_context() -> None:
    profile = _profile(
        "IDEAL FROST",
        source_id="P2-S1",
        application="Mejorante para larga congelación",
    )
    complementary = _decision(
        profile,
        status="complementary",
        matched=(_FREEZING,),
        missing=(_PRECOOKED,),
        reason="Confirma congelación, pero no precocción.",
    )
    decision = _FakeDecisionService(
        _outcome(
            [complementary],
            warnings=("fallback léxico",),
            mode="semantic",
        )
    )
    ai = _FakeAI(
        LocalAIResult(False, "", "Fallo en C:/secreto/modelo"),
    )
    service = TechnicalConsultantService(decision, ai)

    result = service.consult("pan precocido congelado")

    assert result.ok and not result.used_ai
    assert result.retrieval_mode == "semantic"
    assert result.warnings[0] == "fallback léxico"
    assert "C:/secreto" not in repr(result.warnings)


def test_not_supported_products_are_excluded_from_ai_context() -> None:
    relevant_profile = _profile(
        "PREBACK",
        source_id="P1-S1",
        application="Mejorante para pan precocido",
    )
    unrelated_profile = _profile(
        "MAÍZ",
        source_id="P2-S1",
        application="Mix para pan de maíz",
    )
    relevant = _decision(
        relevant_profile,
        status="complementary",
        matched=(_PRECOOKED,),
        missing=(_FREEZING,),
        reason="Confirma precocción, pero no congelación.",
    )
    unrelated = _decision(
        unrelated_profile,
        status="not_supported",
        missing=(_PRECOOKED, _FREEZING),
        reason="No confirma los requisitos.",
    )
    ai = _FakeAI(
        LocalAIResult(
            True,
            '{"answer":"Resumen","citations":["P1-S1"]}',
        )
    )
    service = TechnicalConsultantService(
        _FakeDecisionService(_outcome([relevant, unrelated])),
        ai,
    )

    result = service.consult("pan precocido congelado")

    assert [product.product_name for product in result.products] == ["PREBACK"]
    assert "MAÍZ" not in ai.calls[0]["prompt"]

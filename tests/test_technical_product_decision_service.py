from __future__ import annotations

from app.services.technical_product_comparison_service import (
    TechnicalProductComparisonOutcome,
    TechnicalProductProfile,
    TechnicalProductProfileSource,
)
from app.services.technical_product_decision_service import (
    TechnicalProductDecisionService,
)


def _profile(
    product_name: str,
    application: str | None,
    *,
    score: float = 0.02,
    similarity: float | None = 0.8,
) -> TechnicalProductProfile:
    source = TechnicalProductProfileSource(
        source_id=f"{product_name}-S1",
        document_id=(product_name.casefold().encode().hex() + ("0" * 64))[:64],
        name=f"{product_name}.pdf",
        relative_path=f"CALIDAD/FICHAS TECNICAS/IREKS/{product_name}.pdf",
        page_number=1,
    )
    return TechnicalProductProfile(
        product_key=product_name.casefold(),
        product_name=product_name,
        application=application,
        dosage="10 g por kg de harina" if application else None,
        minimum_shelf_life="12 meses" if application else None,
        storage_conditions="lugar fresco y seco" if application else None,
        ingredients=None,
        retrieval_score=score,
        semantic_similarity=similarity,
        methods=("semantic",),
        sources=(source,) if application else (),
        missing_fields=("ingredients",) if application else (
            "application",
            "dosage",
            "minimum_shelf_life",
            "storage_conditions",
            "ingredients",
        ),
    )


class _FakeComparison:
    def __init__(self, profiles=(), *, warnings=(), mode="hybrid"):
        self.profiles = tuple(profiles)
        self.warnings = tuple(warnings)
        self.mode = mode
        self.calls = []

    def compare(self, query, *, limit=6):
        self.calls.append({"query": query, "limit": limit})
        return TechnicalProductComparisonOutcome(
            query=query,
            profiles=self.profiles,
            used_lexical=self.mode in {"lexical", "hybrid"},
            used_semantic=self.mode in {"semantic", "hybrid"},
            warnings=self.warnings,
            mode=self.mode,
        )


def test_empty_query_does_not_call_comparison() -> None:
    comparison = _FakeComparison()
    service = TechnicalProductDecisionService(comparison)

    assert service.decide("  ").decisions == ()
    assert service.decide("consulta", limit=0).decisions == ()
    assert comparison.calls == []


def test_precooked_and_frozen_query_classifies_documented_coverage() -> None:
    comparison = _FakeComparison(
        [
            _profile(
                "FRISCH UND FROSTIG",
                "Mejorante para pan especial y bollería de larga congelación",
                similarity=0.90,
            ),
            _profile(
                "PREBACK",
                "Mejorante para la elaboración de pan especial precocido y bollería",
                similarity=0.88,
            ),
            _profile(
                "IREKS MAÍZ CL",
                "Mix para la elaboración de pan especial de trigo y maíz",
                similarity=0.86,
            ),
            _profile(
                "IDEAL FROST",
                "Mejorante para pan especial y bollería de larga congelación",
                similarity=0.84,
            ),
        ]
    )
    service = TechnicalProductDecisionService(comparison)

    outcome = service.decide(
        "Necesito elaborar pan precocinado y luego congelado",
        limit=4,
    )

    assert [requirement.key for requirement in outcome.requirements] == [
        "precooked",
        "freezing",
    ]
    assert [
        (decision.profile.product_name, decision.status)
        for decision in outcome.decisions
    ] == [
        ("FRISCH UND FROSTIG", "complementary"),
        ("PREBACK", "complementary"),
        ("IDEAL FROST", "complementary"),
        ("IREKS MAÍZ CL", "not_supported"),
    ]
    assert outcome.recommended == ()
    assert "no se infiere que puedan combinarse" in outcome.message


def test_product_covering_every_requirement_is_recommended() -> None:
    profile = _profile(
        "PRODUCTO COMPLETO",
        "Mejorante para pan precocido destinado a congelación",
    )
    service = TechnicalProductDecisionService(_FakeComparison([profile]))

    decision = service.decide("pan precocido y congelado").decisions[0]

    assert decision.status == "recommended"
    assert [item.key for item in decision.matched_requirements] == [
        "precooked",
        "freezing",
    ]
    assert decision.missing_requirements == ()
    assert "todos los requisitos" in decision.reason


def test_partial_candidate_lists_confirmed_and_missing_requirements() -> None:
    profile = _profile("PREBACK", "Mejorante para pan especial precocido")
    service = TechnicalProductDecisionService(_FakeComparison([profile]))

    decision = service.decide("pan precocido y congelado").decisions[0]

    assert decision.status == "complementary"
    assert [item.label for item in decision.matched_requirements] == ["precocción"]
    assert [item.label for item in decision.missing_requirements] == ["congelación"]
    assert "no confirma congelación" in decision.reason


def test_unrelated_candidate_is_not_reported_as_unsuitable() -> None:
    profile = _profile("MAÍZ", "Mix para pan especial de trigo y maíz")
    service = TechnicalProductDecisionService(_FakeComparison([profile]))

    decision = service.decide("pan precocido").decisions[0]

    assert decision.status == "not_supported"
    assert "no confirma" in decision.reason
    assert "no apto" not in decision.reason


def test_missing_application_is_insufficient_evidence_not_rejection() -> None:
    profile = _profile("SIN DATOS", None)
    service = TechnicalProductDecisionService(_FakeComparison([profile]))

    decision = service.decide("pan congelado").decisions[0]

    assert decision.status == "insufficient_evidence"
    assert decision.matched_requirements == ()
    assert [item.key for item in decision.missing_requirements] == ["freezing"]
    assert "no contiene" in decision.reason


def test_unknown_requirement_requests_more_detail_without_recommending() -> None:
    profile = _profile("PRODUCTO", "Mejorante para pan especial")
    comparison = _FakeComparison([profile])
    service = TechnicalProductDecisionService(comparison)

    outcome = service.decide("Quiero mejorar mi producto")

    assert outcome.requirements == ()
    assert outcome.decisions == ()
    assert outcome.recommended == ()
    assert "Concreta el proceso" in outcome.message
    assert outcome.mode == "none"
    assert comparison.calls == []


def test_detection_is_accent_insensitive_and_supports_controlled_terms() -> None:
    requirements = TechnicalProductDecisionService.detect_requirements(
        "Fermentación retardada, larga fermentación y producto SIN GLUTEN"
    )

    assert [requirement.key for requirement in requirements] == [
        "controlled_fermentation",
        "long_fermentation",
        "gluten_free",
    ]


def test_ranking_prefers_status_then_similarity_and_preserves_sources() -> None:
    lower = _profile(
        "MENOR",
        "Mejorante para congelación",
        score=0.01,
        similarity=0.70,
    )
    higher = _profile(
        "MAYOR",
        "Mejorante para congelación",
        score=0.02,
        similarity=0.90,
    )
    rejected = _profile(
        "NO RESPALDADO",
        "Mix para pan de maíz",
        similarity=0.99,
    )
    service = TechnicalProductDecisionService(
        _FakeComparison([lower, rejected, higher])
    )

    outcome = service.decide("producto para congelación")

    assert [decision.profile.product_name for decision in outcome.decisions] == [
        "MAYOR",
        "MENOR",
        "NO RESPALDADO",
    ]
    assert outcome.decisions[0].profile.sources == higher.sources


def test_comparison_context_and_warnings_are_preserved() -> None:
    profile = _profile("PRODUCTO", "Mejorante para congelación")
    comparison = _FakeComparison(
        [profile],
        warnings=("fallback controlado",),
        mode="semantic",
    )
    service = TechnicalProductDecisionService(comparison)

    outcome = service.decide("producto congelado", limit=3)

    assert comparison.calls == [{"query": "producto congelado", "limit": 3}]
    assert outcome.mode == "semantic"
    assert outcome.used_semantic and not outcome.used_lexical
    assert outcome.warnings == ("fallback controlado",)

from __future__ import annotations

from app.services.technical_product_comparison_service import (
    PROFILE_PAGE_NUMBER,
    PROFILE_TEXT_MAX_CHARS,
    TechnicalProductComparisonService,
)
from app.services.technical_product_retrieval_service import (
    TechnicalProductCandidate,
    TechnicalProductEvidence,
    TechnicalProductRetrievalOutcome,
)


def _evidence(
    number: int,
    name: str,
    *,
    page: int = 1,
) -> TechnicalProductEvidence:
    return TechnicalProductEvidence(
        document_id=f"{number:064x}",
        name=name,
        relative_path=f"CALIDAD/FICHAS TECNICAS/IREKS/{name}",
        area="CALIDAD",
        category="FICHAS TECNICAS/IREKS",
        page_number=page,
        fragment="fragmento",
        combined_score=0.02,
        lexical_rank=None,
        semantic_rank=number,
        semantic_similarity=0.8,
        methods=("semantic",),
    )


def _candidate(
    number: int,
    product_name: str,
    *,
    page: int = 1,
) -> TechnicalProductCandidate:
    name = f"{number:06}E_es_{product_name}_Qualitätszertifikat.pdf"
    return TechnicalProductCandidate(
        product_key=product_name.casefold(),
        product_name=product_name,
        combined_score=0.03 - (number / 1_000_000),
        semantic_similarity=0.8 - (number / 1_000_000),
        methods=("semantic",),
        evidence=(_evidence(number, name, page=page),),
    )


class _FakeRetrieval:
    def __init__(self, candidates=(), *, warnings=(), mode="hybrid"):
        self.candidates = tuple(candidates)
        self.warnings = tuple(warnings)
        self.mode = mode
        self.calls = []

    def search(self, query, *, limit=6):
        self.calls.append({"query": query, "limit": limit})
        return TechnicalProductRetrievalOutcome(
            candidates=self.candidates,
            used_lexical=self.mode in {"lexical", "hybrid"},
            used_semantic=self.mode in {"semantic", "hybrid"},
            warnings=self.warnings,
            mode=self.mode,
        )


class _FakeContentIndex:
    def __init__(self, pages=None):
        self.pages = dict(pages or {})
        self.calls = []

    def get_page_text(self, document_id, page_number, *, max_chars=4000):
        self.calls.append(
            {
                "document_id": document_id,
                "page_number": page_number,
                "max_chars": max_chars,
            }
        )
        return self.pages.get((document_id, page_number))


_COMPLETE_SHEET = """
CERTIFICADO DE CALIDAD
Descripción:
Mejorante para la elaboración de pan especial y bollería de larga
congelación
Dosis:
de 30 a 40 g por kg de harina, dependiendo del tiempo de congelación
Tiempo de conservación
mínimo:
12 meses
Condiciones de
almacenaje:
conservar en un lugar fresco y seco en el envase original cerrado
Aspecto:
polvo beige
Lista de ingredientes
Ingredientes:
(en orden
descendiente)
Dextrosa, harina pregelatinizada de trigo, emulgentes: E 472e
Información QUID:
19 % harina pregelatinizada de trigo
"""


def test_empty_query_calls_neither_retrieval_nor_content() -> None:
    retrieval = _FakeRetrieval()
    content = _FakeContentIndex()
    service = TechnicalProductComparisonService(retrieval, content)

    assert service.compare("  ").profiles == ()
    assert service.compare("consulta", limit=0).profiles == ()
    assert retrieval.calls == []
    assert content.calls == []


def test_complete_sheet_is_extracted_without_rephrasing_values() -> None:
    candidate = _candidate(1, "FRISCH UND FROSTIG")
    document_id = candidate.evidence[0].document_id
    retrieval = _FakeRetrieval([candidate])
    content = _FakeContentIndex({(document_id, 1): _COMPLETE_SHEET})
    service = TechnicalProductComparisonService(retrieval, content)

    profile = service.compare("larga congelación").profiles[0]

    assert profile.application == (
        "Mejorante para la elaboración de pan especial y bollería de larga congelación"
    )
    assert profile.dosage == (
        "de 30 a 40 g por kg de harina, dependiendo del tiempo de congelación"
    )
    assert profile.minimum_shelf_life == "12 meses"
    assert profile.storage_conditions == (
        "conservar en un lugar fresco y seco en el envase original cerrado"
    )
    assert profile.ingredients == (
        "Dextrosa, harina pregelatinizada de trigo, emulgentes: E 472e"
    )
    assert profile.missing_fields == ()


def test_profiles_preserve_retrieval_order_scores_methods_and_mode() -> None:
    first = _candidate(1, "PRODUCTO A")
    second = _candidate(2, "PRODUCTO B")
    pages = {
        (first.evidence[0].document_id, 1): _COMPLETE_SHEET,
        (second.evidence[0].document_id, 1): _COMPLETE_SHEET,
    }
    retrieval = _FakeRetrieval(
        [first, second],
        warnings=("fallback controlado",),
        mode="semantic",
    )
    service = TechnicalProductComparisonService(
        retrieval,
        _FakeContentIndex(pages),
    )

    outcome = service.compare("consulta", limit=2)

    assert [profile.product_name for profile in outcome.profiles] == [
        "PRODUCTO A",
        "PRODUCTO B",
    ]
    assert outcome.profiles[0].retrieval_score == first.combined_score
    assert outcome.profiles[0].methods == ("semantic",)
    assert outcome.mode == "semantic"
    assert outcome.used_semantic and not outcome.used_lexical
    assert outcome.warnings == ("fallback controlado",)
    assert retrieval.calls == [{"query": "consulta", "limit": 2}]


def test_page_one_is_loaded_even_when_search_matched_another_page() -> None:
    candidate = _candidate(7, "PRODUCTO", page=3)
    document_id = candidate.evidence[0].document_id
    content = _FakeContentIndex({(document_id, 1): _COMPLETE_SHEET})
    service = TechnicalProductComparisonService(
        _FakeRetrieval([candidate]),
        content,
    )

    source = service.compare("consulta").profiles[0].sources[0]

    assert source.page_number == PROFILE_PAGE_NUMBER
    assert content.calls == [
        {
            "document_id": document_id,
            "page_number": 1,
            "max_chars": PROFILE_TEXT_MAX_CHARS,
        }
    ]


def test_matched_page_is_fallback_when_page_one_has_no_text() -> None:
    candidate = _candidate(8, "PRODUCTO", page=3)
    document_id = candidate.evidence[0].document_id
    content = _FakeContentIndex({(document_id, 3): _COMPLETE_SHEET})
    service = TechnicalProductComparisonService(
        _FakeRetrieval([candidate]),
        content,
    )

    source = service.compare("consulta").profiles[0].sources[0]

    assert source.page_number == 3
    assert [call["page_number"] for call in content.calls] == [1, 3]


def test_missing_fields_are_explicit_and_are_not_invented() -> None:
    candidate = _candidate(9, "PRODUCTO")
    document_id = candidate.evidence[0].document_id
    content = _FakeContentIndex(
        {
            (document_id, 1): """
            Descripción: Mejorante para pan precocido
            Dosis: 10 g por kg de harina
            Tiempo de conservación
            """
        }
    )
    service = TechnicalProductComparisonService(
        _FakeRetrieval([candidate]),
        content,
    )

    profile = service.compare("consulta").profiles[0]

    assert profile.application == "Mejorante para pan precocido"
    assert profile.dosage == "10 g por kg de harina"
    assert profile.minimum_shelf_life is None
    assert profile.storage_conditions is None
    assert profile.ingredients is None
    assert profile.missing_fields == (
        "minimum_shelf_life",
        "storage_conditions",
        "ingredients",
    )


def test_candidate_without_evidence_returns_empty_grounded_profile() -> None:
    candidate = TechnicalProductCandidate(
        product_key="producto",
        product_name="PRODUCTO",
        combined_score=0.01,
        semantic_similarity=None,
        methods=("lexical",),
        evidence=(),
    )
    service = TechnicalProductComparisonService(
        _FakeRetrieval([candidate]),
        _FakeContentIndex(),
    )

    outcome = service.compare("consulta")

    assert outcome.profiles[0].sources == ()
    assert outcome.profiles[0].missing_fields == service.PROFILE_FIELDS
    assert outcome.warnings == (
        "No se pudieron extraer datos comparables de PRODUCTO.",
    )


def test_unreadable_page_returns_no_values_and_controlled_warning() -> None:
    candidate = _candidate(10, "PRODUCTO")
    service = TechnicalProductComparisonService(
        _FakeRetrieval([candidate]),
        _FakeContentIndex(),
    )

    outcome = service.compare("consulta")
    profile = outcome.profiles[0]

    assert profile.application is None
    assert profile.dosage is None
    assert profile.sources == ()
    assert outcome.warnings == (
        "No se pudieron extraer datos comparables de PRODUCTO.",
    )

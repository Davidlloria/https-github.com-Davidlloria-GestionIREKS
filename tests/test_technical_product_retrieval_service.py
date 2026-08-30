from __future__ import annotations

import pytest

from app.services.document_hybrid_retrieval_service import (
    DocumentHybridRetrievalOutcome,
    DocumentHybridSearchResult,
)
from app.services.technical_product_retrieval_service import (
    DEFAULT_TECHNICAL_AREA,
    DEFAULT_TECHNICAL_CATEGORY,
    MAX_EVIDENCE_PER_PRODUCT,
    MAX_TECHNICAL_PRODUCTS,
    TechnicalProductRetrievalService,
)


def _result(
    number: int,
    name: str,
    *,
    page: int = 1,
    score: float = 0.02,
    similarity: float | None = 0.8,
    methods: tuple[str, ...] = ("semantic",),
) -> DocumentHybridSearchResult:
    return DocumentHybridSearchResult(
        document_id=f"{number:064x}",
        name=name,
        relative_path=f"CALIDAD/FICHAS TECNICAS/IREKS/{name}",
        area=DEFAULT_TECHNICAL_AREA,
        category=DEFAULT_TECHNICAL_CATEGORY,
        page_number=page,
        fragment=f"Evidencia {number}",
        combined_score=score,
        semantic_rank=number if similarity is not None else None,
        semantic_similarity=similarity,
        methods=methods,
    )


class _FakeHybridRetrieval:
    def __init__(self, results=(), *, warnings=(), mode="hybrid"):
        self.results = tuple(results)
        self.warnings = tuple(warnings)
        self.mode = mode
        self.calls = []

    def search(self, query, *, area=None, category=None, limit=18):
        self.calls.append(
            {
                "query": query,
                "area": area,
                "category": category,
                "limit": limit,
            }
        )
        return DocumentHybridRetrievalOutcome(
            results=self.results,
            used_lexical=self.mode in {"lexical", "hybrid"},
            used_semantic=self.mode in {"semantic", "hybrid"},
            warnings=self.warnings,
            mode=self.mode,
        )


def test_empty_query_does_not_call_hybrid_retrieval() -> None:
    retrieval = _FakeHybridRetrieval()
    service = TechnicalProductRetrievalService(retrieval)

    assert service.search("  ").candidates == ()
    assert service.search("consulta", limit=0).candidates == ()
    assert retrieval.calls == []


def test_search_is_restricted_to_ireks_technical_sheets() -> None:
    retrieval = _FakeHybridRetrieval()
    service = TechnicalProductRetrievalService(retrieval)

    service.search("pan precocido congelado", limit=6)

    assert retrieval.calls == [
        {
            "query": "pan precocido congelado",
            "area": "CALIDAD",
            "category": "FICHAS TECNICAS/IREKS",
            "limit": 24,
        }
    ]


def test_custom_taxonomy_can_be_used_without_changing_grouping() -> None:
    retrieval = _FakeHybridRetrieval()
    service = TechnicalProductRetrievalService(
        retrieval,
        technical_area="OTRA",
        technical_category="FICHAS/PRODUCTOS",
    )

    service.search("consulta", limit=2)

    assert retrieval.calls[0]["area"] == "OTRA"
    assert retrieval.calls[0]["category"] == "FICHAS/PRODUCTOS"


@pytest.mark.parametrize(
    ("area", "category"),
    [("", "FICHAS"), ("CALIDAD", ""), (" ", "FICHAS"), ("CALIDAD", " ")],
)
def test_taxonomy_requires_area_and_category(area: str, category: str) -> None:
    with pytest.raises(ValueError, match="obligatorias"):
        TechnicalProductRetrievalService(
            _FakeHybridRetrieval(),
            technical_area=area,
            technical_category=category,
        )


def test_equivalent_documents_are_grouped_as_one_product() -> None:
    retrieval = _FakeHybridRetrieval(
        [
            _result(
                1,
                "127502E_es_IREKS SOFTY PLUS_Qualitätszertifikat.pdf",
                score=0.03,
            ),
            _result(
                2,
                "127553E_es_IREKS SOFTY PLUS_Qualitätszertifikat.pdf",
                score=0.02,
            ),
            _result(
                3,
                "100622E_es_IDEAL FROST_Qualitätszertifikat.pdf",
                score=0.01,
            ),
        ]
    )
    service = TechnicalProductRetrievalService(retrieval)

    candidates = service.search("congelación").candidates

    assert [candidate.product_name for candidate in candidates] == [
        "IREKS SOFTY PLUS",
        "IDEAL FROST",
    ]
    assert len(candidates[0].evidence) == 2
    assert candidates[0].combined_score == 0.03


def test_evidence_is_limited_per_product_and_preserves_source_fields() -> None:
    results = [
        _result(
            number,
            "100622E_es_IDEAL FROST_Qualitätszertifikat.pdf",
            page=number,
        )
        for number in range(1, MAX_EVIDENCE_PER_PRODUCT + 3)
    ]
    service = TechnicalProductRetrievalService(_FakeHybridRetrieval(results))

    candidate = service.search(
        "congelación",
        evidence_per_product=999,
    ).candidates[0]

    assert len(candidate.evidence) == MAX_EVIDENCE_PER_PRODUCT
    assert candidate.evidence[0].document_id == f"{1:064x}"
    assert candidate.evidence[0].page_number == 1
    assert candidate.evidence[0].relative_path.startswith("CALIDAD/")


def test_product_limit_is_capped_and_internal_limit_is_bounded() -> None:
    results = [
        _result(number, f"{number:06}E_es_PRODUCTO {number}_Qualitätszertifikat.pdf")
        for number in range(1, MAX_TECHNICAL_PRODUCTS + 10)
    ]
    retrieval = _FakeHybridRetrieval(results)
    service = TechnicalProductRetrievalService(retrieval)

    outcome = service.search("consulta", limit=999)

    assert len(outcome.candidates) == MAX_TECHNICAL_PRODUCTS
    assert retrieval.calls[0]["limit"] == 50


def test_mode_warnings_and_used_indexes_are_preserved() -> None:
    retrieval = _FakeHybridRetrieval(
        [_result(1, "100622E_es_IDEAL FROST_Qualitätszertifikat.pdf")],
        warnings=("fallback controlado",),
        mode="semantic",
    )
    service = TechnicalProductRetrievalService(retrieval)

    outcome = service.search("congelación")

    assert outcome.mode == "semantic"
    assert outcome.used_semantic and not outcome.used_lexical
    assert outcome.warnings == ("fallback controlado",)


@pytest.mark.parametrize(
    ("document_name", "product_name", "product_key"),
    [
        (
            "100622E_es_IDEAL FROST_Qualitätszertifikat.pdf",
            "IDEAL FROST",
            "ideal frost",
        ),
        (
            "132310e.CASTANOCE - Produktzertifikat.pdf",
            "CASTANOCE",
            "castanoce",
        ),
        (
            "123456E_es_MASA MADRE LÍQUIDA_Certificado de calidad.pdf",
            "MASA MADRE LÍQUIDA",
            "masa madre liquida",
        ),
    ],
)
def test_product_identity_is_derived_from_certificate_filename(
    document_name: str,
    product_name: str,
    product_key: str,
) -> None:
    assert (
        TechnicalProductRetrievalService.product_name_from_document(document_name)
        == product_name
    )
    assert TechnicalProductRetrievalService.product_key(product_name) == product_key

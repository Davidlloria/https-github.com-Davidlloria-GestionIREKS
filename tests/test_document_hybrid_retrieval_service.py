from __future__ import annotations

from dataclasses import fields

import pytest

from app.services.document_content_index_service import DocumentContentSearchResult
from app.services.document_hybrid_retrieval_service import (
    MAX_HYBRID_RESULTS,
    RRF_K,
    DocumentHybridRetrievalError,
    DocumentHybridRetrievalService,
)
from app.services.document_semantic_index_service import (
    DocumentSemanticIndexError,
    DocumentSemanticModelMismatchError,
    DocumentSemanticSearchResult,
)


def _lexical(number: int, *, page: int = 1, fragment: str = "léxico"):
    return DocumentContentSearchResult(
        document_id=f"{number:064x}",
        name=f"Doc {number}.pdf",
        relative_path=f"Area/Categoria/doc-{number}.pdf",
        area="Area",
        category="Categoria",
        page_number=page,
        fragment=fragment,
        score=-1.0,
    )


def _semantic(
    number: int,
    *,
    page: int = 1,
    chunk: int = 0,
    similarity: float = 0.8,
    fragment: str = "semántico",
):
    return DocumentSemanticSearchResult(
        document_id=f"{number:064x}",
        name=f"Doc {number}.pdf",
        relative_path=f"Area/Categoria/doc-{number}.pdf",
        area="Area",
        category="Categoria",
        page_number=page,
        chunk_index=chunk,
        fragment=fragment,
        similarity=similarity,
    )


class _FakeSearch:
    def __init__(self, results=(), *, error=None, available=True):
        self.results = list(results)
        self.error = error
        self.available = available
        self.calls = []

    def is_search_available(self):
        return self.available

    def search(self, query, *, area=None, category=None, limit=20):
        self.calls.append(
            {"query": query, "area": area, "category": category, "limit": limit}
        )
        if self.error:
            raise self.error
        return list(self.results)


def _service(lexical=(), semantic=(), **kwargs):
    lexical_search = _FakeSearch(lexical)
    semantic_search = _FakeSearch(semantic)
    service = DocumentHybridRetrievalService(
        lexical_search, semantic_search, **kwargs
    )
    return service, lexical_search, semantic_search


def test_empty_query_calls_neither_search() -> None:
    service, lexical, semantic = _service()
    outcome = service.search("  ")
    assert outcome.mode == "none" and outcome.results == ()
    assert lexical.calls == semantic.calls == []


def test_lexical_only_result_and_semantic_only_result() -> None:
    service, _, _ = _service([_lexical(1)], [])
    lexical = service.search("consulta")
    assert lexical.results[0].methods == ("lexical",)
    service, _, _ = _service([], [_semantic(2)])
    semantic = service.search("consulta")
    assert semantic.results[0].methods == ("semantic",)


def test_same_page_is_fused_and_prefers_lexical_fragment() -> None:
    service, _, _ = _service(
        [_lexical(1, page=3, fragment="coincidencia [útil]")],
        [_semantic(1, page=3, similarity=0.9, fragment="otro fragmento")],
    )
    result = service.search("consulta").results[0]
    assert result.methods == ("lexical", "semantic")
    assert result.fragment == "coincidencia [útil]"
    assert result.lexical_rank == result.semantic_rank == 1


def test_duplicate_lexical_page_and_semantic_chunks_yield_one_page() -> None:
    service, _, _ = _service(
        [_lexical(1), _lexical(1)],
        [
            _semantic(1, chunk=4, similarity=0.7, fragment="inferior"),
            _semantic(1, chunk=2, similarity=0.9, fragment="mejor"),
            _semantic(1, chunk=1, similarity=0.9, fragment="desempate"),
        ],
    )
    result = service.search("consulta").results
    assert len(result) == 1
    assert result[0].semantic_similarity == 0.9
    assert result[0].semantic_rank == 3


def test_semantic_fragment_is_used_when_lexical_fragment_is_empty() -> None:
    service, _, _ = _service(
        [_lexical(1, fragment="")], [_semantic(1, fragment="fragmento semántico")]
    )
    assert service.search("consulta").results[0].fragment == "fragmento semántico"


def test_rrf_is_one_based_and_applies_configured_weights() -> None:
    service, _, _ = _service(
        [_lexical(1)],
        [_semantic(1)],
        lexical_weight=2.0,
        semantic_weight=3.0,
    )
    result = service.search("consulta").results[0]
    assert result.combined_score == pytest.approx(5.0 / (RRF_K + 1))


def test_final_order_is_deterministic() -> None:
    service, _, _ = _service(
        [_lexical(2), _lexical(1)],
        [_semantic(1), _semantic(2)],
    )
    first = service.search("consulta").results
    second = service.search("consulta").results
    assert first == second
    assert [item.document_id for item in first] == [f"{1:064x}", f"{2:064x}"]


def test_filters_and_larger_internal_limit_are_forwarded() -> None:
    service, lexical, semantic = _service()
    service.search("consulta", area="Calidad", category="Fichas", limit=10)
    for search in (lexical, semantic):
        assert search.calls == [{
            "query": "consulta", "area": "Calidad", "category": "Fichas", "limit": 30
        }]


def test_public_limit_is_capped() -> None:
    docs = [_lexical(number) for number in range(1, MAX_HYBRID_RESULTS + 10)]
    service, lexical, _ = _service(docs, [])
    outcome = service.search("consulta", limit=999)
    assert len(outcome.results) == MAX_HYBRID_RESULTS
    assert lexical.calls[0]["limit"] == 150


def test_semantic_threshold_and_lexical_exception_to_threshold() -> None:
    service, _, _ = _service(
        [_lexical(1)],
        [_semantic(1, similarity=0.1), _semantic(2, similarity=0.39)],
        semantic_threshold=0.4,
    )
    results = service.search("consulta").results
    assert [result.document_id for result in results] == [f"{1:064x}"]
    assert results[0].methods == ("lexical", "semantic")


@pytest.mark.parametrize("threshold", [-1.01, 1.01])
def test_semantic_threshold_is_validated(threshold) -> None:
    with pytest.raises(ValueError):
        _service(semantic_threshold=threshold)


def test_missing_semantic_index_uses_lexical_without_warning() -> None:
    service, _, semantic = _service([_lexical(1)], [])
    semantic.available = False
    outcome = service.search("consulta")
    assert outcome.mode == "lexical"
    assert outcome.used_lexical and not outcome.used_semantic
    assert outcome.warnings == () and semantic.calls == []


def test_model_mismatch_falls_back_to_lexical() -> None:
    service, _, semantic = _service([_lexical(1)], [])
    semantic.error = DocumentSemanticModelMismatchError("ruta secreta")
    outcome = service.search("consulta")
    assert outcome.mode == "lexical" and outcome.results
    assert outcome.warnings == (
        "El índice semántico necesita actualizarse para el modelo configurado.",
    )


@pytest.mark.parametrize(
    ("message", "warning"),
    [
        ("Servicio desactivado", "La búsqueda semántica está desactivada."),
        ("modelo x no instalado", "El modelo de embeddings configurado no está disponible."),
        ("C:/secreto/error", "No se pudo consultar el índice semántico."),
    ],
)
def test_semantic_errors_fall_back_with_safe_warning(message, warning) -> None:
    service, _, semantic = _service([_lexical(1)], [])
    semantic.error = DocumentSemanticIndexError(message)
    outcome = service.search("consulta")
    assert outcome.results and outcome.warnings == (warning,)
    assert "C:/" not in repr(outcome.warnings)


def test_lexical_error_allows_semantic_mode() -> None:
    service, lexical, _ = _service([], [_semantic(1)])
    lexical.error = RuntimeError("fallo")
    outcome = service.search("consulta")
    assert outcome.mode == "semantic" and outcome.results
    assert outcome.warnings == ("No se pudo consultar el índice léxico.",)


def test_both_searches_failed_raise_controlled_error() -> None:
    service, lexical, semantic = _service()
    lexical.error = RuntimeError("lexical")
    semantic.error = RuntimeError("semantic")
    with pytest.raises(DocumentHybridRetrievalError, match="índice documental"):
        service.search("consulta")


def test_results_expose_neither_vectors_nor_absolute_paths() -> None:
    unsafe = _semantic(1)
    unsafe = DocumentSemanticSearchResult(
        **{
            **unsafe.__dict__,
            "relative_path": "C:/secret/doc.pdf",
            "fragment": "Consultar C:/secret/interno.txt",
        }
    )
    service, _, _ = _service([], [unsafe, _semantic(2)])
    outcome = service.search("consulta")
    assert len(outcome.results) == 2
    assert not any(field.name == "vector" for field in fields(outcome.results[0]))
    assert "C:/secret" not in repr(outcome)

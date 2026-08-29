from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath

from app.services.document_content_index_service import DocumentContentIndexService
from app.services.document_semantic_index_service import (
    DocumentSemanticIndexError,
    DocumentSemanticIndexService,
    DocumentSemanticModelMismatchError,
)


RRF_K = 60
LEXICAL_WEIGHT = 1.0
SEMANTIC_WEIGHT = 1.0
# Conservative starting point; adjust only after evaluation with the real corpus.
DEFAULT_SEMANTIC_THRESHOLD = 0.35
MAX_HYBRID_RESULTS = 50
MAX_INTERNAL_CANDIDATES = 150
INTERNAL_CANDIDATE_MULTIPLIER = 3
_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?i)(?<![\w])(?:[a-z]:[\\/]|\\\\)[^\s]+|(?<![\w])/(?:[^/\s]+/)+[^\s]+"
)


class DocumentHybridRetrievalError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentHybridSearchResult:
    document_id: str
    name: str
    relative_path: str
    area: str
    category: str
    page_number: int
    fragment: str
    combined_score: float
    lexical_rank: int | None = None
    semantic_rank: int | None = None
    semantic_similarity: float | None = None
    methods: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentHybridRetrievalOutcome:
    results: tuple[DocumentHybridSearchResult, ...] = ()
    used_lexical: bool = False
    used_semantic: bool = False
    warnings: tuple[str, ...] = ()
    mode: str = "none"


@dataclass
class _MergedPage:
    document_id: str
    name: str
    relative_path: str
    area: str
    category: str
    page_number: int
    fragment: str
    lexical_rank: int | None = None
    semantic_rank: int | None = None
    semantic_similarity: float | None = None


class DocumentHybridRetrievalService:
    """Fuse lexical and local-semantic document retrieval deterministically."""

    def __init__(
        self,
        content_index_service: DocumentContentIndexService,
        semantic_index_service: DocumentSemanticIndexService,
        *,
        semantic_threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
        lexical_weight: float = LEXICAL_WEIGHT,
        semantic_weight: float = SEMANTIC_WEIGHT,
    ) -> None:
        if not -1.0 <= float(semantic_threshold) <= 1.0:
            raise ValueError("El umbral semántico debe estar entre -1 y 1.")
        if float(lexical_weight) < 0 or float(semantic_weight) < 0:
            raise ValueError("Los pesos de recuperación no pueden ser negativos.")
        if float(lexical_weight) == 0 and float(semantic_weight) == 0:
            raise ValueError("Al menos un peso de recuperación debe ser positivo.")
        self.content_index_service = content_index_service
        self.semantic_index_service = semantic_index_service
        self.semantic_threshold = float(semantic_threshold)
        self.lexical_weight = float(lexical_weight)
        self.semantic_weight = float(semantic_weight)

    def search(
        self,
        query: str,
        *,
        area: str | None = None,
        category: str | None = None,
        limit: int = 18,
    ) -> DocumentHybridRetrievalOutcome:
        clean_query = str(query or "").strip()
        if not clean_query or limit <= 0:
            return DocumentHybridRetrievalOutcome()
        safe_limit = min(int(limit), MAX_HYBRID_RESULTS)
        candidate_limit = min(
            MAX_INTERNAL_CANDIDATES,
            max(safe_limit, safe_limit * INTERNAL_CANDIDATE_MULTIPLIER),
        )
        lexical_results = []
        semantic_results = []
        warnings: list[str] = []
        used_lexical = used_semantic = False
        lexical_failed = semantic_failed = False

        try:
            lexical_results = self.content_index_service.search(
                clean_query,
                area=area,
                category=category,
                limit=candidate_limit,
            )
            used_lexical = True
        except Exception:  # noqa: BLE001
            lexical_failed = True
            warnings.append("No se pudo consultar el índice léxico.")

        semantic_available = self._semantic_index_available()
        if semantic_available:
            try:
                semantic_results = self.semantic_index_service.search(
                    clean_query,
                    area=area,
                    category=category,
                    limit=candidate_limit,
                )
                used_semantic = True
            except DocumentSemanticModelMismatchError:
                semantic_failed = True
                warnings.append(
                    "El índice semántico necesita actualizarse para el modelo configurado."
                )
            except DocumentSemanticIndexError as exc:
                semantic_failed = True
                warnings.append(self._semantic_warning(str(exc)))
            except Exception:  # noqa: BLE001
                semantic_failed = True
                warnings.append("No se pudo consultar el índice semántico.")

        if lexical_failed and (semantic_failed or not semantic_available):
            raise DocumentHybridRetrievalError(
                "No se pudo consultar el índice documental."
            )

        merged: dict[tuple[str, int], _MergedPage] = {}
        for rank, result in enumerate(lexical_results, start=1):
            safe_path = self._safe_relative_path(result.relative_path)
            if safe_path is None:
                continue
            key = (str(result.document_id), int(result.page_number))
            if key in merged:
                continue
            merged[key] = _MergedPage(
                document_id=key[0],
                name=self._safe_name(result.name),
                relative_path=safe_path,
                area=self._single_line(result.area),
                category=self._single_line(result.category),
                page_number=key[1],
                fragment=self._single_line(result.fragment),
                lexical_rank=rank,
            )

        best_semantic: dict[tuple[str, int], tuple[int, object]] = {}
        for rank, result in enumerate(semantic_results, start=1):
            key = (str(result.document_id), int(result.page_number))
            current = best_semantic.get(key)
            if current is None or (
                float(result.similarity), -int(result.chunk_index)
            ) > (
                float(current[1].similarity), -int(current[1].chunk_index)
            ):
                best_semantic[key] = (rank, result)

        for key, (rank, result) in best_semantic.items():
            similarity = float(result.similarity)
            if similarity < self.semantic_threshold and key not in merged:
                continue
            safe_path = self._safe_relative_path(result.relative_path)
            if safe_path is None:
                continue
            existing = merged.get(key)
            if existing is None:
                merged[key] = _MergedPage(
                    document_id=key[0],
                    name=self._safe_name(result.name),
                    relative_path=safe_path,
                    area=self._single_line(result.area),
                    category=self._single_line(result.category),
                    page_number=key[1],
                    fragment=self._single_line(result.fragment),
                    semantic_rank=rank,
                    semantic_similarity=similarity,
                )
            else:
                existing.semantic_rank = rank
                existing.semantic_similarity = similarity
                if not existing.fragment:
                    existing.fragment = self._single_line(result.fragment)

        results = [self._to_result(page) for page in merged.values()]
        results.sort(
            key=lambda result: (
                -result.combined_score,
                -(len(result.methods) == 2),
                min(
                    rank
                    for rank in (result.lexical_rank, result.semantic_rank)
                    if rank is not None
                ),
                result.relative_path.casefold(),
                result.page_number,
            )
        )
        return DocumentHybridRetrievalOutcome(
            results=tuple(results[:safe_limit]),
            used_lexical=used_lexical,
            used_semantic=used_semantic,
            warnings=tuple(warnings),
            mode=self._mode(used_lexical, used_semantic),
        )

    def _semantic_index_available(self) -> bool:
        checker = getattr(self.semantic_index_service, "is_search_available", None)
        if checker is None:
            return True
        try:
            return bool(checker())
        except Exception:  # noqa: BLE001
            return True

    def _to_result(self, page: _MergedPage) -> DocumentHybridSearchResult:
        score = 0.0
        methods: list[str] = []
        if page.lexical_rank is not None:
            score += self.lexical_weight / (RRF_K + page.lexical_rank)
            methods.append("lexical")
        if page.semantic_rank is not None:
            score += self.semantic_weight / (RRF_K + page.semantic_rank)
            methods.append("semantic")
        return DocumentHybridSearchResult(
            document_id=page.document_id,
            name=page.name,
            relative_path=page.relative_path,
            area=page.area,
            category=page.category,
            page_number=page.page_number,
            fragment=page.fragment,
            combined_score=score,
            lexical_rank=page.lexical_rank,
            semantic_rank=page.semantic_rank,
            semantic_similarity=page.semantic_similarity,
            methods=tuple(methods),
        )

    @staticmethod
    def _mode(used_lexical: bool, used_semantic: bool) -> str:
        if used_lexical and used_semantic:
            return "hybrid"
        if used_lexical:
            return "lexical"
        if used_semantic:
            return "semantic"
        return "none"

    @staticmethod
    def _semantic_warning(message: str) -> str:
        folded = str(message or "").casefold()
        if "desactiv" in folded:
            return "La búsqueda semántica está desactivada."
        if "modelo" in folded and ("instal" in folded or "dispon" in folded):
            return "El modelo de embeddings configurado no está disponible."
        return "No se pudo consultar el índice semántico."

    @staticmethod
    def _safe_relative_path(value: str) -> str | None:
        candidate = str(value or "").strip().replace("\\", "/")
        if not candidate:
            return None
        if (
            PurePosixPath(candidate).is_absolute()
            or PureWindowsPath(candidate).is_absolute()
            or ".." in PurePosixPath(candidate).parts
        ):
            candidate = PurePosixPath(candidate).name
            if not candidate:
                return None
        return DocumentHybridRetrievalService._single_line(candidate)

    @staticmethod
    def _safe_name(value: str) -> str:
        candidate = str(value or "").strip().replace("\\", "/")
        return DocumentHybridRetrievalService._redact_absolute_paths(
            DocumentHybridRetrievalService._single_line(
                PurePosixPath(candidate).name
            )
        )

    @staticmethod
    def _single_line(value: str) -> str:
        return DocumentHybridRetrievalService._redact_absolute_paths(
            " ".join(str(value or "").split())
        )

    @staticmethod
    def _redact_absolute_paths(value: str) -> str:
        return _ABSOLUTE_PATH_PATTERN.sub("[RUTA OMITIDA]", str(value or ""))

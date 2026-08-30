from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.services.document_hybrid_retrieval_service import (
    MAX_HYBRID_RESULTS,
    DocumentHybridRetrievalOutcome,
    DocumentHybridRetrievalService,
    DocumentHybridSearchResult,
)


DEFAULT_TECHNICAL_AREA = "CALIDAD"
DEFAULT_TECHNICAL_CATEGORY = "FICHAS TECNICAS/IREKS"
DEFAULT_EVIDENCE_PER_PRODUCT = 2
MAX_EVIDENCE_PER_PRODUCT = 5
MAX_TECHNICAL_PRODUCTS = 20
INTERNAL_PRODUCT_MULTIPLIER = 4
_LEADING_PRODUCT_CODE_PATTERN = re.compile(
    r"(?i)^\s*\d+[a-z]?(?:[._\s-]+[a-z]{2})?[._\s-]+"
)
_CERTIFICATE_SUFFIX_PATTERN = re.compile(
    r"(?i)(?:[_\s-]+)(?:qualit\S*zertifikat|produktzertifikat|"
    r"certificado(?:\s+de)?\s+calidad).*$"
)
_PRODUCT_KEY_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class TechnicalProductEvidence:
    document_id: str
    name: str
    relative_path: str
    area: str
    category: str
    page_number: int
    fragment: str
    combined_score: float
    lexical_rank: int | None
    semantic_rank: int | None
    semantic_similarity: float | None
    methods: tuple[str, ...]


@dataclass(frozen=True)
class TechnicalProductCandidate:
    product_key: str
    product_name: str
    combined_score: float
    semantic_similarity: float | None
    methods: tuple[str, ...]
    evidence: tuple[TechnicalProductEvidence, ...]


@dataclass(frozen=True)
class TechnicalProductRetrievalOutcome:
    candidates: tuple[TechnicalProductCandidate, ...] = ()
    used_lexical: bool = False
    used_semantic: bool = False
    warnings: tuple[str, ...] = ()
    mode: str = "none"


class TechnicalProductRetrievalService:
    """Retrieve diverse product candidates from the technical-sheet taxonomy."""

    def __init__(
        self,
        retrieval_service: DocumentHybridRetrievalService,
        *,
        technical_area: str = DEFAULT_TECHNICAL_AREA,
        technical_category: str = DEFAULT_TECHNICAL_CATEGORY,
    ) -> None:
        clean_area = str(technical_area or "").strip()
        clean_category = str(technical_category or "").strip()
        if not clean_area or not clean_category:
            raise ValueError("El área y la categoría técnicas son obligatorias.")
        self.retrieval_service = retrieval_service
        self.technical_area = clean_area
        self.technical_category = clean_category

    def search(
        self,
        query: str,
        *,
        limit: int = 6,
        evidence_per_product: int = DEFAULT_EVIDENCE_PER_PRODUCT,
    ) -> TechnicalProductRetrievalOutcome:
        clean_query = str(query or "").strip()
        if not clean_query or limit <= 0:
            return TechnicalProductRetrievalOutcome()
        safe_limit = min(int(limit), MAX_TECHNICAL_PRODUCTS)
        safe_evidence_limit = max(
            1,
            min(int(evidence_per_product), MAX_EVIDENCE_PER_PRODUCT),
        )
        internal_limit = min(
            MAX_HYBRID_RESULTS,
            max(safe_limit, safe_limit * INTERNAL_PRODUCT_MULTIPLIER),
        )
        outcome = self.retrieval_service.search(
            clean_query,
            area=self.technical_area,
            category=self.technical_category,
            limit=internal_limit,
        )
        candidates = self._group_candidates(
            outcome,
            limit=safe_limit,
            evidence_per_product=safe_evidence_limit,
        )
        return TechnicalProductRetrievalOutcome(
            candidates=candidates,
            used_lexical=outcome.used_lexical,
            used_semantic=outcome.used_semantic,
            warnings=outcome.warnings,
            mode=outcome.mode,
        )

    @classmethod
    def _group_candidates(
        cls,
        outcome: DocumentHybridRetrievalOutcome,
        *,
        limit: int,
        evidence_per_product: int,
    ) -> tuple[TechnicalProductCandidate, ...]:
        grouped: dict[str, tuple[str, list[DocumentHybridSearchResult]]] = {}
        for result in outcome.results:
            product_name = cls.product_name_from_document(result.name)
            product_key = cls.product_key(product_name)
            if not product_key:
                continue
            current = grouped.get(product_key)
            if current is None:
                grouped[product_key] = (product_name, [result])
            elif len(current[1]) < evidence_per_product:
                current[1].append(result)

        candidates = [
            cls._build_candidate(product_key, product_name, evidence)
            for product_key, (product_name, evidence) in grouped.items()
        ]
        return tuple(candidates[:limit])

    @classmethod
    def _build_candidate(
        cls,
        product_key: str,
        product_name: str,
        results: list[DocumentHybridSearchResult],
    ) -> TechnicalProductCandidate:
        semantic_similarities = [
            result.semantic_similarity
            for result in results
            if result.semantic_similarity is not None
        ]
        methods: list[str] = []
        for result in results:
            for method in result.methods:
                if method not in methods:
                    methods.append(method)
        return TechnicalProductCandidate(
            product_key=product_key,
            product_name=product_name,
            combined_score=max(result.combined_score for result in results),
            semantic_similarity=(
                max(semantic_similarities) if semantic_similarities else None
            ),
            methods=tuple(methods),
            evidence=tuple(cls._to_evidence(result) for result in results),
        )

    @staticmethod
    def _to_evidence(
        result: DocumentHybridSearchResult,
    ) -> TechnicalProductEvidence:
        return TechnicalProductEvidence(
            document_id=result.document_id,
            name=result.name,
            relative_path=result.relative_path,
            area=result.area,
            category=result.category,
            page_number=result.page_number,
            fragment=result.fragment,
            combined_score=result.combined_score,
            lexical_rank=result.lexical_rank,
            semantic_rank=result.semantic_rank,
            semantic_similarity=result.semantic_similarity,
            methods=result.methods,
        )

    @staticmethod
    def product_name_from_document(name: str) -> str:
        safe_name = PurePosixPath(str(name or "").replace("\\", "/")).name
        stem = PurePosixPath(safe_name).stem
        without_code = _LEADING_PRODUCT_CODE_PATTERN.sub("", stem)
        without_suffix = _CERTIFICATE_SUFFIX_PATTERN.sub("", without_code)
        product_name = " ".join(without_suffix.replace("_", " ").split()).strip(" -.")
        return product_name or " ".join(stem.replace("_", " ").split()).strip(" -.")

    @staticmethod
    def product_key(product_name: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(product_name or ""))
        ascii_name = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        return _PRODUCT_KEY_SEPARATOR_PATTERN.sub(
            " ",
            ascii_name.casefold(),
        ).strip()

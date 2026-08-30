from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.document_content_index_service import DocumentContentIndexService
from app.services.technical_product_retrieval_service import (
    TechnicalProductCandidate,
    TechnicalProductRetrievalOutcome,
    TechnicalProductRetrievalService,
)


PROFILE_PAGE_NUMBER = 1
PROFILE_TEXT_MAX_CHARS = 12_000
_FIELD_PATTERNS = {
    "application": (
        r"Descripción\s*:",
        (r"Dosis\s*:",),
    ),
    "dosage": (
        r"Dosis\s*:",
        (r"Tiempo\s+de\s+conservación",),
    ),
    "minimum_shelf_life": (
        r"Tiempo\s+de\s+conservación\s+mínimo\s*:",
        (r"Condiciones\s+de\s+almacenaje\s*:",),
    ),
    "storage_conditions": (
        r"Condiciones\s+de\s+almacenaje\s*:",
        (r"Aspecto\s*:",),
    ),
    "ingredients": (
        r"Ingredientes\s*:\s*(?:\(\s*en\s+orden\s+descendiente\s*\))?",
        (r"Información\s+QUID\s*:", r"Datos\s+analíticos"),
    ),
}
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class TechnicalProductProfileSource:
    source_id: str
    document_id: str
    name: str
    relative_path: str
    page_number: int


@dataclass(frozen=True)
class TechnicalProductProfile:
    product_key: str
    product_name: str
    application: str | None
    dosage: str | None
    minimum_shelf_life: str | None
    storage_conditions: str | None
    ingredients: str | None
    retrieval_score: float
    semantic_similarity: float | None
    methods: tuple[str, ...]
    sources: tuple[TechnicalProductProfileSource, ...]
    missing_fields: tuple[str, ...]


@dataclass(frozen=True)
class TechnicalProductComparisonOutcome:
    query: str = ""
    profiles: tuple[TechnicalProductProfile, ...] = ()
    used_lexical: bool = False
    used_semantic: bool = False
    warnings: tuple[str, ...] = ()
    mode: str = "none"


class TechnicalProductComparisonService:
    """Build comparable, source-backed profiles from retrieved product sheets."""

    PROFILE_FIELDS = tuple(_FIELD_PATTERNS)

    def __init__(
        self,
        retrieval_service: TechnicalProductRetrievalService,
        content_index_service: DocumentContentIndexService,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.content_index_service = content_index_service

    def compare(
        self,
        query: str,
        *,
        limit: int = 6,
    ) -> TechnicalProductComparisonOutcome:
        clean_query = str(query or "").strip()
        if not clean_query or limit <= 0:
            return TechnicalProductComparisonOutcome()
        retrieval = self.retrieval_service.search(clean_query, limit=limit)
        profiles: list[TechnicalProductProfile] = []
        warnings = list(retrieval.warnings)
        for position, candidate in enumerate(retrieval.candidates, start=1):
            profile = self._build_profile(candidate, position)
            profiles.append(profile)
            if len(profile.missing_fields) == len(self.PROFILE_FIELDS):
                warnings.append(
                    f"No se pudieron extraer datos comparables de {candidate.product_name}."
                )
        return TechnicalProductComparisonOutcome(
            query=clean_query,
            profiles=tuple(profiles),
            used_lexical=retrieval.used_lexical,
            used_semantic=retrieval.used_semantic,
            warnings=tuple(warnings),
            mode=retrieval.mode,
        )

    def _build_profile(
        self,
        candidate: TechnicalProductCandidate,
        position: int,
    ) -> TechnicalProductProfile:
        source, text = self._load_profile_page(candidate, position)
        fields = {
            field: self._extract_field(text, *patterns)
            for field, patterns in _FIELD_PATTERNS.items()
        }
        missing_fields = tuple(
            field for field in self.PROFILE_FIELDS if fields[field] is None
        )
        return TechnicalProductProfile(
            product_key=candidate.product_key,
            product_name=candidate.product_name,
            application=fields["application"],
            dosage=fields["dosage"],
            minimum_shelf_life=fields["minimum_shelf_life"],
            storage_conditions=fields["storage_conditions"],
            ingredients=fields["ingredients"],
            retrieval_score=candidate.combined_score,
            semantic_similarity=candidate.semantic_similarity,
            methods=candidate.methods,
            sources=(source,) if source is not None else (),
            missing_fields=missing_fields,
        )

    def _load_profile_page(
        self,
        candidate: TechnicalProductCandidate,
        position: int,
    ) -> tuple[TechnicalProductProfileSource | None, str]:
        if not candidate.evidence:
            return None, ""
        primary = candidate.evidence[0]
        text = self.content_index_service.get_page_text(
            primary.document_id,
            PROFILE_PAGE_NUMBER,
            max_chars=PROFILE_TEXT_MAX_CHARS,
        )
        page_number = PROFILE_PAGE_NUMBER
        if not text and primary.page_number != PROFILE_PAGE_NUMBER:
            text = self.content_index_service.get_page_text(
                primary.document_id,
                primary.page_number,
                max_chars=PROFILE_TEXT_MAX_CHARS,
            )
            page_number = primary.page_number
        if not text:
            return None, ""
        return (
            TechnicalProductProfileSource(
                source_id=f"P{position}-S1",
                document_id=primary.document_id,
                name=primary.name,
                relative_path=primary.relative_path,
                page_number=page_number,
            ),
            str(text),
        )

    @staticmethod
    def _extract_field(
        text: str,
        start_pattern: str,
        end_patterns: tuple[str, ...],
    ) -> str | None:
        if not text:
            return None
        end_pattern = "|".join(f"(?:{pattern})" for pattern in end_patterns)
        match = re.search(
            rf"(?:{start_pattern})\s*(.*?)\s*(?={end_pattern})",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match is None:
            return None
        value = _WHITESPACE_PATTERN.sub(" ", match.group(1)).strip(" .;")
        return value or None

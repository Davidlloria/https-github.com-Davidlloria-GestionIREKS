from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from app.services.technical_product_comparison_service import (
    TechnicalProductComparisonOutcome,
    TechnicalProductComparisonService,
    TechnicalProductProfile,
)


DecisionStatus = Literal[
    "recommended",
    "complementary",
    "not_supported",
    "insufficient_evidence",
]
_NORMALIZED_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class TechnicalRequirement:
    key: str
    label: str


@dataclass(frozen=True)
class _RequirementRule:
    requirement: TechnicalRequirement
    query_terms: tuple[str, ...]
    application_terms: tuple[str, ...]


_REQUIREMENT_RULES = (
    _RequirementRule(
        TechnicalRequirement("precooked", "precocción"),
        ("precoc", "prehorne"),
        ("precoc", "prehorne"),
    ),
    _RequirementRule(
        TechnicalRequirement("freezing", "congelación"),
        ("congel", "ultracongel"),
        ("congel", "ultracongel"),
    ),
    _RequirementRule(
        TechnicalRequirement("controlled_fermentation", "fermentación controlada"),
        ("fermentacion control", "fermentacion retard"),
        ("fermentacion control", "fermentacion retard"),
    ),
    _RequirementRule(
        TechnicalRequirement("long_fermentation", "fermentación prolongada"),
        ("larga fermentacion", "fermentacion prolong"),
        ("larga fermentacion", "fermentacion prolong"),
    ),
    _RequirementRule(
        TechnicalRequirement("gluten_free", "producto sin gluten"),
        ("sin gluten", "gluten free"),
        ("sin gluten", "gluten free"),
    ),
    _RequirementRule(
        TechnicalRequirement("softness", "frescura o ternura prolongada"),
        ("frescura", "ternura", "mantener tierno"),
        ("frescura", "ternura", "mantener tierno"),
    ),
)
_STATUS_ORDER: dict[DecisionStatus, int] = {
    "recommended": 0,
    "complementary": 1,
    "not_supported": 2,
    "insufficient_evidence": 3,
}


@dataclass(frozen=True)
class TechnicalProductDecision:
    status: DecisionStatus
    profile: TechnicalProductProfile
    matched_requirements: tuple[TechnicalRequirement, ...]
    missing_requirements: tuple[TechnicalRequirement, ...]
    reason: str


@dataclass(frozen=True)
class TechnicalProductDecisionOutcome:
    query: str = ""
    requirements: tuple[TechnicalRequirement, ...] = ()
    decisions: tuple[TechnicalProductDecision, ...] = ()
    message: str = ""
    used_lexical: bool = False
    used_semantic: bool = False
    warnings: tuple[str, ...] = ()
    mode: str = "none"

    @property
    def recommended(self) -> tuple[TechnicalProductDecision, ...]:
        return tuple(
            decision
            for decision in self.decisions
            if decision.status == "recommended"
        )

    @property
    def complementary(self) -> tuple[TechnicalProductDecision, ...]:
        return tuple(
            decision
            for decision in self.decisions
            if decision.status == "complementary"
        )


class TechnicalProductDecisionService:
    """Classify compared products using only documented application evidence."""

    def __init__(
        self,
        comparison_service: TechnicalProductComparisonService,
    ) -> None:
        self.comparison_service = comparison_service

    def decide(
        self,
        query: str,
        *,
        limit: int = 6,
    ) -> TechnicalProductDecisionOutcome:
        clean_query = str(query or "").strip()
        if not clean_query or limit <= 0:
            return TechnicalProductDecisionOutcome()
        requirements = self.detect_requirements(clean_query)
        if not requirements:
            return TechnicalProductDecisionOutcome(
                query=clean_query,
                message=self._outcome_message((), ()),
            )
        comparison = self.comparison_service.compare(clean_query, limit=limit)
        decisions = tuple(
            self._classify(profile, requirements)
            for profile in comparison.profiles
        )
        ranked_decisions = tuple(sorted(decisions, key=self._decision_sort_key))
        return TechnicalProductDecisionOutcome(
            query=clean_query,
            requirements=requirements,
            decisions=ranked_decisions,
            message=self._outcome_message(requirements, ranked_decisions),
            used_lexical=comparison.used_lexical,
            used_semantic=comparison.used_semantic,
            warnings=comparison.warnings,
            mode=comparison.mode,
        )

    @classmethod
    def detect_requirements(
        cls,
        query: str,
    ) -> tuple[TechnicalRequirement, ...]:
        normalized_query = cls._normalize(query)
        return tuple(
            rule.requirement
            for rule in _REQUIREMENT_RULES
            if any(term in normalized_query for term in rule.query_terms)
        )

    @classmethod
    def _classify(
        cls,
        profile: TechnicalProductProfile,
        requirements: tuple[TechnicalRequirement, ...],
    ) -> TechnicalProductDecision:
        if not requirements:
            return TechnicalProductDecision(
                status="insufficient_evidence",
                profile=profile,
                matched_requirements=(),
                missing_requirements=(),
                reason=(
                    "La consulta no contiene requisitos técnicos reconocibles "
                    "para comparar la aplicación documentada."
                ),
            )
        if not profile.application:
            return TechnicalProductDecision(
                status="insufficient_evidence",
                profile=profile,
                matched_requirements=(),
                missing_requirements=requirements,
                reason="La ficha no contiene una aplicación técnica utilizable.",
            )
        normalized_application = cls._normalize(profile.application)
        matched = tuple(
            requirement
            for requirement in requirements
            if cls._application_matches(requirement.key, normalized_application)
        )
        missing = tuple(
            requirement
            for requirement in requirements
            if requirement not in matched
        )
        if matched and not missing:
            status: DecisionStatus = "recommended"
            reason = (
                "La aplicación documentada confirma todos los requisitos: "
                f"{cls._labels(matched)}."
            )
        elif matched:
            status = "complementary"
            reason = (
                f"La aplicación documentada confirma {cls._labels(matched)}, "
                f"pero no confirma {cls._labels(missing)}."
            )
        else:
            status = "not_supported"
            reason = (
                "La aplicación documentada no confirma los requisitos detectados: "
                f"{cls._labels(requirements)}."
            )
        return TechnicalProductDecision(
            status=status,
            profile=profile,
            matched_requirements=matched,
            missing_requirements=missing,
            reason=reason,
        )

    @staticmethod
    def _application_matches(requirement_key: str, application: str) -> bool:
        for rule in _REQUIREMENT_RULES:
            if rule.requirement.key == requirement_key:
                return any(term in application for term in rule.application_terms)
        return False

    @staticmethod
    def _decision_sort_key(
        decision: TechnicalProductDecision,
    ) -> tuple[int, int, float, float, str]:
        semantic_similarity = decision.profile.semantic_similarity
        return (
            _STATUS_ORDER[decision.status],
            -len(decision.matched_requirements),
            -(semantic_similarity if semantic_similarity is not None else -1.0),
            -decision.profile.retrieval_score,
            decision.profile.product_name.casefold(),
        )

    @staticmethod
    def _outcome_message(
        requirements: tuple[TechnicalRequirement, ...],
        decisions: tuple[TechnicalProductDecision, ...],
    ) -> str:
        if not requirements:
            return (
                "Faltan requisitos técnicos reconocibles. Concreta el proceso "
                "antes de solicitar una recomendación."
            )
        recommended = [
            decision for decision in decisions if decision.status == "recommended"
        ]
        complementary = [
            decision for decision in decisions if decision.status == "complementary"
        ]
        if recommended:
            count = len(recommended)
            return (
                f"{count} producto cumple todos los requisitos documentados."
                if count == 1
                else f"{count} productos cumplen todos los requisitos documentados."
            )
        if complementary:
            return (
                "Ninguna ficha confirma por sí sola todos los requisitos. "
                "Los candidatos parciales requieren validación técnica y no se "
                "infiere que puedan combinarse."
            )
        return "Ninguna ficha recuperada confirma los requisitos técnicos indicados."

    @staticmethod
    def _labels(requirements: tuple[TechnicalRequirement, ...]) -> str:
        return ", ".join(requirement.label for requirement in requirements)

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        without_marks = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        return _NORMALIZED_SEPARATOR_PATTERN.sub(
            " ",
            without_marks.casefold(),
        ).strip()

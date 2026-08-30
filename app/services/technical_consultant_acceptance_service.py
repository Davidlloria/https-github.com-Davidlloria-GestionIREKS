from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.services.technical_product_decision_service import (
    TechnicalProductDecisionOutcome,
    TechnicalProductDecisionService,
)


ACCEPTANCE_BASELINE_VERSION = 1
_RELEVANT_STATUSES = frozenset({"recommended", "complementary"})
_RETRIEVAL_MODES = frozenset({"hybrid", "lexical", "semantic"})
_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?i)(?<![\w])(?:[a-z]:[\\/]|\\\\)[^\s]+|(?<![\w])/(?:[^/\s]+/)+[^\s]+"
)


class TechnicalConsultantAcceptanceError(ValueError):
    pass


@dataclass(frozen=True)
class TechnicalAcceptanceExpectedOutcome:
    product_name: str
    status: str
    source_names: tuple[str, ...]


@dataclass(frozen=True)
class TechnicalAcceptanceCase:
    case_id: str
    query: str
    expected_requirements: tuple[str, ...]
    expected_mode: str
    expected_outcomes: tuple[TechnicalAcceptanceExpectedOutcome, ...]
    allow_warnings: bool = False
    limit: int = 6


@dataclass(frozen=True)
class TechnicalAcceptanceBaseline:
    version: int
    expected_embedding_model: str
    cases: tuple[TechnicalAcceptanceCase, ...]


@dataclass(frozen=True)
class TechnicalAcceptanceActualOutcome:
    product_name: str
    status: str
    source_names: tuple[str, ...]


@dataclass(frozen=True)
class TechnicalAcceptanceDrift:
    field: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class TechnicalAcceptanceCaseResult:
    case_id: str
    query: str
    passed: bool
    requirements: tuple[str, ...]
    retrieval_mode: str
    outcomes: tuple[TechnicalAcceptanceActualOutcome, ...]
    warnings: tuple[str, ...]
    duration_seconds: float
    drifts: tuple[TechnicalAcceptanceDrift, ...]


@dataclass(frozen=True)
class TechnicalAcceptanceReport:
    baseline_version: int
    expected_embedding_model: str
    actual_embedding_model: str
    evaluated_at: str
    passed: bool
    global_drifts: tuple[TechnicalAcceptanceDrift, ...]
    cases: tuple[TechnicalAcceptanceCaseResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_technical_acceptance_baseline(
    path: str | Path,
) -> TechnicalAcceptanceBaseline:
    baseline_path = Path(path)
    try:
        payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TechnicalConsultantAcceptanceError(
            f"No se pudo leer la línea base: {_safe_message(str(exc))}"
        ) from exc
    return parse_technical_acceptance_baseline(payload)


def parse_technical_acceptance_baseline(
    payload: object,
) -> TechnicalAcceptanceBaseline:
    if not isinstance(payload, dict):
        raise TechnicalConsultantAcceptanceError(
            "La línea base debe ser un objeto JSON."
        )
    version = payload.get("version")
    if version != ACCEPTANCE_BASELINE_VERSION:
        raise TechnicalConsultantAcceptanceError(
            f"Versión de línea base no soportada: {version!r}."
        )
    expected_embedding_model = _required_text(
        payload.get("expected_embedding_model"),
        "expected_embedding_model",
    )
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise TechnicalConsultantAcceptanceError(
            "La línea base debe contener al menos un caso."
        )
    cases = tuple(_parse_case(item, position) for position, item in enumerate(raw_cases))
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise TechnicalConsultantAcceptanceError(
            "Los identificadores de caso deben ser únicos."
        )
    return TechnicalAcceptanceBaseline(
        version=version,
        expected_embedding_model=expected_embedding_model,
        cases=cases,
    )


def _parse_case(payload: object, position: int) -> TechnicalAcceptanceCase:
    prefix = f"cases[{position}]"
    if not isinstance(payload, dict):
        raise TechnicalConsultantAcceptanceError(f"{prefix} debe ser un objeto.")
    case_id = _required_text(payload.get("id"), f"{prefix}.id")
    query = _required_text(payload.get("query"), f"{prefix}.query")
    expected_requirements = _text_list(
        payload.get("expected_requirements"),
        f"{prefix}.expected_requirements",
    )
    expected_mode = _required_text(
        payload.get("expected_mode"),
        f"{prefix}.expected_mode",
    )
    if expected_mode not in _RETRIEVAL_MODES:
        raise TechnicalConsultantAcceptanceError(
            f"{prefix}.expected_mode no es válido."
        )
    raw_outcomes = payload.get("expected_outcomes")
    if not isinstance(raw_outcomes, list):
        raise TechnicalConsultantAcceptanceError(
            f"{prefix}.expected_outcomes debe ser una lista."
        )
    expected_outcomes = tuple(
        _parse_expected_outcome(item, f"{prefix}.expected_outcomes[{index}]")
        for index, item in enumerate(raw_outcomes)
    )
    product_keys = [item.product_name.casefold() for item in expected_outcomes]
    if len(product_keys) != len(set(product_keys)):
        raise TechnicalConsultantAcceptanceError(
            f"{prefix}.expected_outcomes contiene productos duplicados."
        )
    allow_warnings = payload.get("allow_warnings", False)
    if not isinstance(allow_warnings, bool):
        raise TechnicalConsultantAcceptanceError(
            f"{prefix}.allow_warnings debe ser booleano."
        )
    limit = payload.get("limit", 6)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise TechnicalConsultantAcceptanceError(
            f"{prefix}.limit debe estar entre 1 y 20."
        )
    return TechnicalAcceptanceCase(
        case_id=case_id,
        query=query,
        expected_requirements=expected_requirements,
        expected_mode=expected_mode,
        expected_outcomes=expected_outcomes,
        allow_warnings=allow_warnings,
        limit=limit,
    )


def _parse_expected_outcome(
    payload: object,
    prefix: str,
) -> TechnicalAcceptanceExpectedOutcome:
    if not isinstance(payload, dict):
        raise TechnicalConsultantAcceptanceError(f"{prefix} debe ser un objeto.")
    product_name = _required_text(payload.get("product_name"), f"{prefix}.product_name")
    status = _required_text(payload.get("status"), f"{prefix}.status")
    if status not in _RELEVANT_STATUSES:
        raise TechnicalConsultantAcceptanceError(f"{prefix}.status no es válido.")
    source_names = _text_list(payload.get("source_names"), f"{prefix}.source_names")
    if not source_names:
        raise TechnicalConsultantAcceptanceError(
            f"{prefix}.source_names no puede estar vacío."
        )
    return TechnicalAcceptanceExpectedOutcome(
        product_name=product_name,
        status=status,
        source_names=source_names,
    )


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TechnicalConsultantAcceptanceError(f"{field} es obligatorio.")
    return value.strip()


def _text_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise TechnicalConsultantAcceptanceError(
            f"{field} debe ser una lista de textos."
        )
    cleaned = tuple(item.strip() for item in value)
    if len(cleaned) != len(set(cleaned)):
        raise TechnicalConsultantAcceptanceError(
            f"{field} no puede contener duplicados."
        )
    return cleaned


class TechnicalConsultantAcceptanceService:
    def __init__(
        self,
        decision_service: TechnicalProductDecisionService,
        *,
        embedding_model: str,
        clock: Callable[[], datetime] | None = None,
        timer: Callable[[], float] | None = None,
    ) -> None:
        self.decision_service = decision_service
        self.embedding_model = str(embedding_model or "").strip()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timer = timer or time.perf_counter

    def evaluate(
        self,
        baseline: TechnicalAcceptanceBaseline,
        *,
        case_ids: tuple[str, ...] = (),
    ) -> TechnicalAcceptanceReport:
        selected_cases = self._select_cases(baseline, case_ids)
        global_drifts: list[TechnicalAcceptanceDrift] = []
        if self.embedding_model != baseline.expected_embedding_model:
            global_drifts.append(
                TechnicalAcceptanceDrift(
                    "embedding_model",
                    baseline.expected_embedding_model,
                    self.embedding_model,
                )
            )
        results = tuple(self._evaluate_case(case) for case in selected_cases)
        passed = not global_drifts and all(result.passed for result in results)
        return TechnicalAcceptanceReport(
            baseline_version=baseline.version,
            expected_embedding_model=baseline.expected_embedding_model,
            actual_embedding_model=self.embedding_model,
            evaluated_at=self._clock().astimezone(timezone.utc).isoformat(),
            passed=passed,
            global_drifts=tuple(global_drifts),
            cases=results,
        )

    @staticmethod
    def _select_cases(
        baseline: TechnicalAcceptanceBaseline,
        case_ids: tuple[str, ...],
    ) -> tuple[TechnicalAcceptanceCase, ...]:
        if not case_ids:
            return baseline.cases
        requested = set(case_ids)
        available = {case.case_id for case in baseline.cases}
        unknown = sorted(requested - available)
        if unknown:
            raise TechnicalConsultantAcceptanceError(
                "Casos desconocidos: " + ", ".join(unknown)
            )
        return tuple(case for case in baseline.cases if case.case_id in requested)

    def _evaluate_case(
        self,
        case: TechnicalAcceptanceCase,
    ) -> TechnicalAcceptanceCaseResult:
        started = self._timer()
        try:
            outcome = self.decision_service.decide(case.query, limit=case.limit)
        except Exception as exc:  # noqa: BLE001
            duration = max(0.0, self._timer() - started)
            message = _safe_message(str(exc) or "Error desconocido.")
            drift = TechnicalAcceptanceDrift("execution_error", None, message)
            return TechnicalAcceptanceCaseResult(
                case_id=case.case_id,
                query=case.query,
                passed=False,
                requirements=(),
                retrieval_mode="none",
                outcomes=(),
                warnings=(),
                duration_seconds=round(duration, 3),
                drifts=(drift,),
            )
        duration = max(0.0, self._timer() - started)
        actual_outcomes = self._actual_outcomes(outcome)
        warnings = tuple(_safe_message(item) for item in outcome.warnings)
        drifts = self._compare(case, outcome, actual_outcomes, warnings)
        return TechnicalAcceptanceCaseResult(
            case_id=case.case_id,
            query=case.query,
            passed=not drifts,
            requirements=tuple(item.key for item in outcome.requirements),
            retrieval_mode=outcome.mode,
            outcomes=actual_outcomes,
            warnings=warnings,
            duration_seconds=round(duration, 3),
            drifts=drifts,
        )

    @staticmethod
    def _actual_outcomes(
        outcome: TechnicalProductDecisionOutcome,
    ) -> tuple[TechnicalAcceptanceActualOutcome, ...]:
        return tuple(
            TechnicalAcceptanceActualOutcome(
                product_name=item.profile.product_name,
                status=item.status,
                source_names=tuple(source.name for source in item.profile.sources),
            )
            for item in outcome.decisions
            if item.status in _RELEVANT_STATUSES
        )

    @staticmethod
    def _compare(
        case: TechnicalAcceptanceCase,
        outcome: TechnicalProductDecisionOutcome,
        actual_outcomes: tuple[TechnicalAcceptanceActualOutcome, ...],
        warnings: tuple[str, ...],
    ) -> tuple[TechnicalAcceptanceDrift, ...]:
        drifts: list[TechnicalAcceptanceDrift] = []
        requirements = tuple(item.key for item in outcome.requirements)
        if requirements != case.expected_requirements:
            drifts.append(
                TechnicalAcceptanceDrift(
                    "requirements",
                    case.expected_requirements,
                    requirements,
                )
            )
        if outcome.mode != case.expected_mode:
            drifts.append(
                TechnicalAcceptanceDrift(
                    "retrieval_mode",
                    case.expected_mode,
                    outcome.mode,
                )
            )
        expected_names = tuple(item.product_name for item in case.expected_outcomes)
        actual_names = tuple(item.product_name for item in actual_outcomes)
        if expected_names != actual_names:
            drifts.append(
                TechnicalAcceptanceDrift(
                    "product_order",
                    expected_names,
                    actual_names,
                )
            )
        expected_by_name = {
            item.product_name.casefold(): item for item in case.expected_outcomes
        }
        actual_by_name = {
            item.product_name.casefold(): item for item in actual_outcomes
        }
        missing = tuple(
            item.product_name
            for item in case.expected_outcomes
            if item.product_name.casefold() not in actual_by_name
        )
        unexpected = tuple(
            item.product_name
            for item in actual_outcomes
            if item.product_name.casefold() not in expected_by_name
        )
        if missing:
            drifts.append(TechnicalAcceptanceDrift("missing_products", missing, ()))
        if unexpected:
            drifts.append(
                TechnicalAcceptanceDrift("unexpected_products", (), unexpected)
            )
        for expected in case.expected_outcomes:
            key = expected.product_name.casefold()
            if key not in actual_by_name:
                continue
            actual = actual_by_name[key]
            if expected.status != actual.status:
                drifts.append(
                    TechnicalAcceptanceDrift(
                        f"status:{expected.product_name}",
                        expected.status,
                        actual.status,
                    )
                )
            if expected.source_names != actual.source_names:
                drifts.append(
                    TechnicalAcceptanceDrift(
                        f"sources:{expected.product_name}",
                        expected.source_names,
                        actual.source_names,
                    )
                )
        if warnings and not case.allow_warnings:
            drifts.append(TechnicalAcceptanceDrift("warnings", (), warnings))
        return tuple(drifts)


def _safe_message(message: str) -> str:
    return _ABSOLUTE_PATH_PATTERN.sub("[RUTA OMITIDA]", str(message or ""))

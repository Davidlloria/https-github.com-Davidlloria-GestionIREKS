from __future__ import annotations

import re
import unicodedata
from typing import Any


QUERY_NORMALIZATION_RULES: tuple[tuple[str, str], ...] = (
    (r"\baculmulado\b", "acumulado"),
    (r"\baculmulada\b", "acumulada"),
    (r"\baculmulados\b", "acumulados"),
    (r"\baculmuladas\b", "acumuladas"),
    (r"\bdiferencias negativas\b", "diferenciales negativos"),
    (r"\bdiferencia negativa\b", "diferencial negativo"),
    (r"\bdiferencias negativas en kg\b", "diferenciales negativos en kg"),
    (r"\bmayor a menos\b", "mayor a menor"),
    (r"\bordenados de mayor a menos\b", "ordenados de mayor a menor"),
    (r"\bordenado de mayor a menos\b", "ordenado de mayor a menor"),
)


def normalize_search_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    normalized = unicodedata.normalize("NFD", text)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", normalized)


def normalize_query_text(value: Any) -> str:
    normalized = normalize_search_text(value)
    for pattern, replacement in QUERY_NORMALIZATION_RULES:
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


def mentions_acumulado(value: Any) -> bool:
    normalized = normalize_search_text(value)
    if not normalized:
        return False
    if any(token in normalized for token in ("acumulado", "acumular", "acumulada")):
        return True
    words = normalized.split()
    if any(word in {"acumulado", "acumulada", "acumulados", "acumuladas"} for word in words):
        return True
    return any(
        re.fullmatch(pattern, word or "") is not None
        for word in words
        for pattern in (
            r"acu.?mulad[oa]s?",
            r"aculmulad[oa]s?",
            r"acumlad[oa]s?",
        )
    )

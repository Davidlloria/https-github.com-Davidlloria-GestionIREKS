from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar


DEFAULT_PAGE_LIMIT = 1000
MAX_PAGE_LIMIT = 1000
MAX_PAGE_OFFSET = 100_000

T = TypeVar("T")


def page_items(rows: Sequence[T], *, offset: int = 0, limit: int = DEFAULT_PAGE_LIMIT) -> list[T]:
    start = max(int(offset or 0), 0)
    stop = start + max(int(limit or 0), 0)
    return list(rows[start:stop])

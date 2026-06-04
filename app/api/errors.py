from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError


def _detail(value: Exception | str) -> str:
    return str(value).strip() or "Error de API."


def bad_request(value: Exception | str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_detail(value))


def not_found(value: Exception | str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_detail(value))


def conflict(value: Exception | str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_detail(value))


def integrity_is_foreign_key(exc: IntegrityError) -> bool:
    text = str(getattr(exc, "orig", exc) or "").lower()
    return "foreign key" in text

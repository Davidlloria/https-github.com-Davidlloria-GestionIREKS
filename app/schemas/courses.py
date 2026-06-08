from __future__ import annotations

from datetime import date

from sqlmodel import Field

from .base import AppSchema, PaginatedResponse


class CourseListItem(AppSchema):
    curso_id: str
    curso_nombre: str = ""
    curso_fecha: date | None = None


class CourseDetail(CourseListItem):
    pass


class CourseAttendeeItem(AppSchema):
    id: str
    nombre: str = ""
    empresa: str = ""
    confirmado: bool = False
    observaciones: str = ""


class CourseAttendeeListResponse(PaginatedResponse):
    items: list[CourseAttendeeItem] = Field(default_factory=list)


class CourseListResponse(PaginatedResponse):
    items: list[CourseListItem] = Field(default_factory=list)


__all__ = [
    "CourseAttendeeItem",
    "CourseAttendeeListResponse",
    "CourseDetail",
    "CourseListItem",
    "CourseListResponse",
]

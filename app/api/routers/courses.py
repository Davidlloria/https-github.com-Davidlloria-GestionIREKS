from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_course_service
from app.api.errors import not_found
from app.schemas.courses import (
    CourseAttendeeItem,
    CourseAttendeeListResponse,
    CourseDetail,
    CourseListItem,
    CourseListResponse,
)
from app.services.course_service import CourseService


router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=CourseListResponse)
def list_courses(
    q: Annotated[str, Query(max_length=120)] = "",
    year: Annotated[int | None, Query(ge=1, le=9999)] = None,
    month_start: Annotated[int | None, Query(ge=1, le=12)] = None,
    month_end: Annotated[int | None, Query(ge=1, le=12)] = None,
    service: CourseService = Depends(get_course_service),
) -> CourseListResponse:
    rows = service.list_courses(term=q, year=year, month_start=month_start, month_end=month_end)
    items = CourseListItem.list_from_entities(rows)
    return CourseListResponse(total=len(items), limit=len(items), offset=0, items=items)


@router.get("/{course_id}", response_model=CourseDetail)
def get_course(
    course_id: str,
    service: CourseService = Depends(get_course_service),
) -> CourseDetail:
    course = service.get_course(course_id)
    if course is None:
        raise not_found("Curso no encontrado.")
    return CourseDetail.from_entity(course)


@router.get("/{course_id}/attendees", response_model=CourseAttendeeListResponse)
def list_course_attendees(
    course_id: str,
    service: CourseService = Depends(get_course_service),
) -> CourseAttendeeListResponse:
    if service.get_course(course_id) is None:
        raise not_found("Curso no encontrado.")
    rows = service.list_attendees(course_id)
    items = [
        CourseAttendeeItem(
            id=str(row.contacto_id),
            nombre=str(getattr(row, "asistente", "") or ""),
            empresa=str(getattr(row, "empresa", "") or ""),
            confirmado=bool(getattr(row, "status_confirmacion", False)),
            observaciones=str(getattr(row, "observaciones", "") or ""),
        )
        for row in rows
    ]
    return CourseAttendeeListResponse(total=len(items), limit=len(items), offset=0, items=items)

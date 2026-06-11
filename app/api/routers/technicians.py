from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_technician_service
from app.api.errors import not_found
from app.api.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, MAX_PAGE_OFFSET
from app.schemas.technicians import TechnicianDetail, TechnicianListResponse
from app.services.technician_service import TechnicianService


router = APIRouter(prefix="/technicians", tags=["technicians"])


@router.get("", response_model=TechnicianListResponse)
def list_technicians(
    q: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
    service: TechnicianService = Depends(get_technician_service),
) -> TechnicianListResponse:
    return service.list_payload(q, limit=limit, offset=offset)


@router.get("/{technician_id}", response_model=TechnicianDetail)
def get_technician(
    technician_id: str,
    service: TechnicianService = Depends(get_technician_service),
) -> TechnicianDetail:
    payload = service.detail_payload(technician_id)
    if payload is None:
        raise not_found("Tecnico no encontrado.")
    return payload

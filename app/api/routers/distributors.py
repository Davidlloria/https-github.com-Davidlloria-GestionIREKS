from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_distributor_service
from app.api.errors import not_found
from app.api.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, MAX_PAGE_OFFSET
from app.schemas.distributors import DistributorDetail, DistributorListResponse
from app.services.distributor_service import DistributorService


router = APIRouter(prefix="/distributors", tags=["distributors"])


@router.get("", response_model=DistributorListResponse)
def list_distributors(
    q: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
    service: DistributorService = Depends(get_distributor_service),
) -> DistributorListResponse:
    return service.list_payload(q, limit=limit, offset=offset)


@router.get("/{distributor_id}", response_model=DistributorDetail)
def get_distributor(
    distributor_id: str,
    service: DistributorService = Depends(get_distributor_service),
) -> DistributorDetail:
    payload = service.detail_payload(distributor_id)
    if payload is None:
        raise not_found("Distribuidor no encontrado.")
    return payload

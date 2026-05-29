from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_contact_service
from app.api.errors import bad_request, conflict, not_found
from app.api.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, MAX_PAGE_OFFSET
from app.schemas.contacts import (
    ContactCompanyOption,
    ContactCreate,
    ContactDetail,
    ContactListItem,
    ContactUpdate,
)
from app.services.contact_service import ContactService


router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactListItem])
def list_contacts(
    q: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
    service: ContactService = Depends(get_contact_service),
) -> list[ContactListItem]:
    return service.list_payload(q, limit=limit, offset=offset)


@router.get("/companies", response_model=list[ContactCompanyOption])
def list_contact_companies(
    service: ContactService = Depends(get_contact_service),
) -> list[ContactCompanyOption]:
    return service.company_options_payload()


@router.get("/{contact_id}", response_model=ContactDetail)
def get_contact(
    contact_id: str,
    service: ContactService = Depends(get_contact_service),
) -> ContactDetail:
    payload = service.detail_payload(contact_id)
    if payload is None:
        raise not_found("Contacto no encontrado.")
    return payload


@router.post("", response_model=ContactDetail, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    service: ContactService = Depends(get_contact_service),
) -> ContactDetail:
    try:
        return service.create_from_payload(payload)
    except ValueError as exc:
        raise bad_request(exc) from exc


@router.patch("/{contact_id}", response_model=ContactDetail)
def update_contact(
    contact_id: str,
    payload: ContactUpdate,
    service: ContactService = Depends(get_contact_service),
) -> ContactDetail:
    try:
        return service.update_from_payload(contact_id, payload)
    except ValueError as exc:
        raise not_found(exc) from exc


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: str,
    service: ContactService = Depends(get_contact_service),
) -> Response:
    blockers = service.delete_blockers(contact_id)
    if blockers:
        raise conflict(f"No se puede eliminar el contacto porque tiene dependencias: {', '.join(blockers)}.")
    try:
        deleted = service.delete(contact_id)
    except IntegrityError as exc:
        raise conflict("No se puede eliminar el contacto porque tiene dependencias.") from exc
    if not deleted:
        raise not_found("Contacto no encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

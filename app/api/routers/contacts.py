from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_contact_service
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
    q: str = "",
    service: ContactService = Depends(get_contact_service),
) -> list[ContactListItem]:
    return service.list_payload(q)


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado.")
    return payload


@router.post("", response_model=ContactDetail, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    service: ContactService = Depends(get_contact_service),
) -> ContactDetail:
    try:
        return service.create_from_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{contact_id}", response_model=ContactDetail)
def update_contact(
    contact_id: str,
    payload: ContactUpdate,
    service: ContactService = Depends(get_contact_service),
) -> ContactDetail:
    try:
        return service.update_from_payload(contact_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: str,
    service: ContactService = Depends(get_contact_service),
) -> Response:
    if not service.delete(contact_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

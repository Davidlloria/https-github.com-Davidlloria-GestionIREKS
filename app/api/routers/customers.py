from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_customer_service
from app.api.errors import bad_request, not_found
from app.schemas.customers import (
    CustomerCreate,
    CustomerDetail,
    CustomerListItem,
    CustomerUpdate,
)
from app.services.customer_service import CustomerService


router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerListItem])
def list_customers(
    q: str = "",
    service: CustomerService = Depends(get_customer_service),
) -> list[CustomerListItem]:
    return service.list_payload(q)


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(
    customer_id: str,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerDetail:
    payload = service.detail_payload(customer_id)
    if payload is None:
        raise not_found("Cliente no encontrado.")
    return payload


@router.post("", response_model=CustomerDetail, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerDetail:
    try:
        return service.create_from_payload(payload)
    except ValueError as exc:
        raise bad_request(exc) from exc


@router.patch("/{customer_id}", response_model=CustomerDetail)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerDetail:
    try:
        return service.update_from_payload(customer_id, payload)
    except ValueError as exc:
        raise not_found(exc) from exc


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: str,
    service: CustomerService = Depends(get_customer_service),
) -> Response:
    if not service.delete(customer_id):
        raise not_found("Cliente no encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

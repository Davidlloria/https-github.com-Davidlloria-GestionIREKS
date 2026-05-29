from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_ingredient_ireks_service, get_ingredient_std_service
from app.schemas.ingredients import (
    IngredientActiveUpdate,
    IngredientIreksCreate,
    IngredientIreksListPayload,
    IngredientIreksRead,
    IngredientIreksUpdate,
    IngredientStdCreate,
    IngredientStdRead,
    IngredientStdUpdate,
    MateriaPrimaPrecioRead,
    NutritionValues,
    TarifaPrecioIreksCreate,
    TarifaPrecioIreksRead,
    TarifaPrecioIreksUpdate,
)
from app.services.ingredient_ireks_service import IngredientIreksService
from app.services.ingredient_std_service import IngredientStdService


router = APIRouter(prefix="/ingredients", tags=["ingredients"])
ActivityFilter = Literal["all", "active", "inactive"]


@router.get("/ireks", response_model=IngredientIreksListPayload)
def list_ireks_ingredients(
    q: Annotated[str, Query(max_length=120)] = "",
    familia_id: Annotated[str, Query(max_length=120)] = "",
    subfamilia_id: Annotated[str, Query(max_length=120)] = "",
    fabricante_id: Annotated[str, Query(max_length=120)] = "",
    activity_filter: Annotated[ActivityFilter, Query()] = "all",
    distributor_filter_id: Annotated[str, Query(max_length=120)] = "",
    service: IngredientIreksService = Depends(get_ingredient_ireks_service),
) -> IngredientIreksListPayload:
    return service.api_list_payload(
        search=q,
        familia_id=familia_id,
        subfamilia_id=subfamilia_id,
        fabricante_id=fabricante_id,
        activity_filter=activity_filter,
        distributor_filter_id=distributor_filter_id,
    )


@router.post("/ireks", response_model=IngredientIreksRead, status_code=status.HTTP_201_CREATED)
def create_ireks_ingredient(
    payload: IngredientIreksCreate,
    service: IngredientIreksService = Depends(get_ingredient_ireks_service),
) -> IngredientIreksRead:
    try:
        return service.create_from_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/ireks/{row_id}", response_model=IngredientIreksRead)
def get_ireks_ingredient(
    row_id: int,
    service: IngredientIreksService = Depends(get_ingredient_ireks_service),
) -> IngredientIreksRead:
    payload = service.api_detail_payload(row_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente IREKS no encontrado.")
    return payload


@router.patch("/ireks/{row_id}", response_model=IngredientIreksRead)
def update_ireks_ingredient(
    row_id: int,
    payload: IngredientIreksUpdate,
    service: IngredientIreksService = Depends(get_ingredient_ireks_service),
) -> IngredientIreksRead:
    result = service.update_from_payload(row_id, payload)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente IREKS no encontrado.")
    return result


@router.delete("/ireks/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ireks_ingredient(
    row_id: int,
    service: IngredientIreksService = Depends(get_ingredient_ireks_service),
) -> Response:
    if not service.delete_if_exists(row_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente IREKS no encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/ireks/{articulo_id}/nutrition", response_model=NutritionValues | None)
def get_ireks_nutrition(
    articulo_id: str,
    service: IngredientIreksService = Depends(get_ingredient_ireks_service),
) -> NutritionValues | None:
    return service.nutrition_payload(articulo_id)


@router.get("/ireks/{articulo_id}/tarifas", response_model=list[TarifaPrecioIreksRead])
def list_ireks_tarifas(
    articulo_id: str,
    service: IngredientIreksService = Depends(get_ingredient_ireks_service),
) -> list[TarifaPrecioIreksRead]:
    return service.tarifas_payload(articulo_id)


@router.post("/ireks/tarifas", response_model=TarifaPrecioIreksRead, status_code=status.HTTP_201_CREATED)
def upsert_ireks_tarifa(
    payload: TarifaPrecioIreksCreate,
    service: IngredientIreksService = Depends(get_ingredient_ireks_service),
) -> TarifaPrecioIreksRead:
    try:
        return service.upsert_tarifa_from_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/ireks/tarifas/{tarifa_id}", response_model=TarifaPrecioIreksRead)
def update_ireks_tarifa(
    tarifa_id: int,
    payload: TarifaPrecioIreksUpdate,
    service: IngredientIreksService = Depends(get_ingredient_ireks_service),
) -> TarifaPrecioIreksRead:
    result = service.update_tarifa_from_payload(tarifa_id, payload)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarifa no encontrada.")
    return result


@router.delete("/ireks/tarifas/{tarifa_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ireks_tarifa(
    tarifa_id: int,
    service: IngredientIreksService = Depends(get_ingredient_ireks_service),
) -> Response:
    if not service.delete_tarifa_if_exists(tarifa_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarifa no encontrada.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/std", response_model=list[IngredientStdRead])
def list_std_ingredients(
    q: Annotated[str, Query(max_length=120)] = "",
    familia_id: Annotated[str, Query(max_length=120)] = "",
    subfamilia_id: Annotated[str, Query(max_length=120)] = "",
    activity_filter: Annotated[ActivityFilter, Query()] = "all",
    service: IngredientStdService = Depends(get_ingredient_std_service),
) -> list[IngredientStdRead]:
    return service.api_list_payload(
        search=q,
        familia_id=familia_id,
        subfamilia_id=subfamilia_id,
        activity_filter=activity_filter,
    )


@router.post("/std", response_model=IngredientStdRead, status_code=status.HTTP_201_CREATED)
def create_std_ingredient(
    payload: IngredientStdCreate,
    service: IngredientStdService = Depends(get_ingredient_std_service),
) -> IngredientStdRead:
    try:
        return service.create_from_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/std/{articulo_id}", response_model=IngredientStdRead)
def get_std_ingredient(
    articulo_id: str,
    service: IngredientStdService = Depends(get_ingredient_std_service),
) -> IngredientStdRead:
    payload = service.api_detail_payload(articulo_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Materia prima no encontrada.")
    return payload


@router.patch("/std/{articulo_id}", response_model=IngredientStdRead)
def update_std_ingredient(
    articulo_id: str,
    payload: IngredientStdUpdate,
    service: IngredientStdService = Depends(get_ingredient_std_service),
) -> IngredientStdRead:
    result = service.update_from_payload(articulo_id, payload)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Materia prima no encontrada.")
    return result


@router.delete("/std/{articulo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_std_ingredient(
    articulo_id: str,
    service: IngredientStdService = Depends(get_ingredient_std_service),
) -> Response:
    if not service.delete_if_exists(articulo_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Materia prima no encontrada.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/std/{articulo_id}/active", response_model=IngredientStdRead)
def update_std_active(
    articulo_id: str,
    payload: IngredientActiveUpdate,
    service: IngredientStdService = Depends(get_ingredient_std_service),
) -> IngredientStdRead:
    result = service.update_active_from_payload(articulo_id, payload)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Materia prima no encontrada.")
    return result


@router.get("/std/{articulo_id}/nutrition", response_model=NutritionValues | None)
def get_std_nutrition(
    articulo_id: str,
    service: IngredientStdService = Depends(get_ingredient_std_service),
) -> NutritionValues | None:
    return service.nutrition_payload(articulo_id)


@router.get("/std/{articulo_id}/prices", response_model=list[MateriaPrimaPrecioRead])
def list_std_prices(
    articulo_id: str,
    service: IngredientStdService = Depends(get_ingredient_std_service),
) -> list[MateriaPrimaPrecioRead]:
    return service.price_history_payload(articulo_id)

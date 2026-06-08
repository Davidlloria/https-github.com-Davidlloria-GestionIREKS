from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_recipe_service
from app.api.errors import not_found
from app.api.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, MAX_PAGE_OFFSET
from app.core.pagination import page_items
from app.schemas.recipes import RecipeDetail, RecipeItem, RecipeItemListResponse, RecipeListItem, RecipeListResponse
from app.services.recipe_service import RecipeService


router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", response_model=RecipeListResponse)
def list_recipes(
    q: Annotated[str, Query(max_length=120)] = "",
    cliente_id: Annotated[str, Query(max_length=64)] = "",
    es_base: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0, le=MAX_PAGE_OFFSET)] = 0,
    service: RecipeService = Depends(get_recipe_service),
) -> RecipeListResponse:
    rows = service.list_recipes(term=q, cliente_id=cliente_id or None, es_base=es_base)
    items = RecipeListItem.list_from_entities(rows)
    paged = page_items(items, limit=limit, offset=offset)
    return RecipeListResponse(total=len(items), limit=limit, offset=offset, items=paged)


@router.get("/{recipe_id}", response_model=RecipeDetail)
def get_recipe(
    recipe_id: int,
    service: RecipeService = Depends(get_recipe_service),
) -> RecipeDetail:
    aggregate = service.get_recipe(recipe_id)
    if aggregate is None:
        raise not_found("Receta no encontrada.")
    return RecipeDetail.from_entity(aggregate.receta)


@router.get("/{recipe_id}/items", response_model=RecipeItemListResponse)
def list_recipe_items(
    recipe_id: int,
    service: RecipeService = Depends(get_recipe_service),
) -> RecipeItemListResponse:
    aggregate = service.get_recipe(recipe_id)
    if aggregate is None:
        raise not_found("Receta no encontrada.")
    items = RecipeItem.list_from_entities(aggregate.lineas)
    return RecipeItemListResponse(total=len(items), items=items)

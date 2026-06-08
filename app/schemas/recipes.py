from __future__ import annotations

from datetime import datetime

from sqlmodel import Field

from .base import AppSchema, PaginatedResponse


class RecipeLineBase(AppSchema):
    orden: int = 0
    tipo_origen: str = "std"
    ingrediente_id: int | None = None
    nombre_mostrado: str = ""
    codigo_ingrediente: str = ""
    familia: str = ""
    subfamilia: str = ""
    es_harina: bool = False
    es_liquido: bool = False
    cantidad_base_g: float = 0.0
    porcentaje_panadero: float = 0.0
    cantidad_calculada_g: float = 0.0
    precio_kg_snapshot: float = 0.0
    coste_linea: float = 0.0
    tipo_linea: str = "ingrediente"
    proceso_nombre: str = "Masa final"
    proceso_origen_nombre: str = ""
    cantidad_origen_g: float = 0.0
    es_subreceta: bool = False
    subreceta_id: int | None = None
    notas: str = ""


class RecipeLineRead(RecipeLineBase):
    id: int | None = None
    receta_id: int


class RecipeLineCreate(RecipeLineBase):
    id: int | None = None
    receta_id: int | None = None


class RecipeBase(AppSchema):
    cliente_id: str
    nombre: str
    codigo_receta: str
    version: str = "1.0"
    es_base: bool = False
    receta_base_id: int | None = None
    masa_final_deseada_g: float = 0.0
    peso_pieza_g: float = 0.0
    numero_piezas: int = 1
    total_harinas_g: float = 0.0
    total_liquidos_g: float = 0.0
    hidratacion_pct: float = 0.0
    total_porcentaje_panadero: float = 0.0
    masa_total_g: float = 0.0
    coste_total: float = 0.0
    coste_kg: float = 0.0
    coste_pieza: float = 0.0
    merma_pct: float = 0.0
    observaciones: str = ""
    proceso: str = ""
    escandallo_detalle_json: str = ""
    parametros_elaboracion_json: str = ""
    estado: str = "borrador"


class RecipeListItem(AppSchema):
    id: int | None = None
    cliente_id: str = ""
    nombre: str = ""
    codigo_receta: str = ""
    version: str = "1.0"
    es_base: bool = False
    receta_base_id: int | None = None
    masa_final_deseada_g: float = 0.0
    peso_pieza_g: float = 0.0
    numero_piezas: int = 1
    observaciones: str = ""
    proceso: str = ""
    estado: str = "borrador"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecipeDetail(RecipeListItem):
    pass


class RecipeItem(AppSchema):
    id: int | None = None
    ingrediente_id: int | None = None
    nombre_mostrado: str = ""
    codigo_ingrediente: str = ""
    tipo_origen: str = "std"
    cantidad_base_g: float = 0.0
    cantidad_calculada_g: float = 0.0
    orden: int = 0
    notas: str = ""


class RecipeItemListResponse(AppSchema):
    total: int = 0
    items: list[RecipeItem] = Field(default_factory=list)


class RecipeListResponse(PaginatedResponse):
    items: list[RecipeListItem] = Field(default_factory=list)


class RecipeCreate(RecipeBase):
    id: int | None = None
    lineas: list[RecipeLineCreate] = Field(default_factory=list)


class RecipeUpdate(AppSchema):
    cliente_id: str | None = None
    nombre: str | None = None
    codigo_receta: str | None = None
    version: str | None = None
    es_base: bool | None = None
    receta_base_id: int | None = None
    masa_final_deseada_g: float | None = None
    peso_pieza_g: float | None = None
    numero_piezas: int | None = None
    observaciones: str | None = None
    proceso: str | None = None
    estado: str | None = None
    lineas: list[RecipeLineCreate] | None = None


class RecipeScalePayload(AppSchema):
    recipe_id: int
    mode: str
    target_value_g: float


class RecipeCalculationPayload(AppSchema):
    receta: RecipeListItem
    lineas: list[RecipeLineRead] = Field(default_factory=list)


__all__ = [
    "RecipeBase",
    "RecipeCalculationPayload",
    "RecipeCreate",
    "RecipeDetail",
    "RecipeLineBase",
    "RecipeLineCreate",
    "RecipeLineRead",
    "RecipeItem",
    "RecipeItemListResponse",
    "RecipeListItem",
    "RecipeListResponse",
    "RecipeScalePayload",
    "RecipeUpdate",
]

from __future__ import annotations

from datetime import date

from sqlmodel import Field

from .base import AppSchema


class CatalogOption(AppSchema):
    id: str
    name: str
    code: str = ""
    parent_id: str = ""


class NutritionValues(AppSchema):
    articulo_id: str = ""
    energia_kj: float = 0.0
    energia_kcal: float = 0.0
    grasas_g: float = 0.0
    saturadas_g: float = 0.0
    hidratos_g: float = 0.0
    azucares_g: float = 0.0
    fibra_g: float = 0.0
    proteinas_g: float = 0.0
    sal_g: float = 0.0


class IngredientIreksBase(AppSchema):
    almacen_id: str = ""
    fabricante_id: str = ""
    distribuidor_id: str = ""
    articulo_id: str = ""
    articulo_referencia: str = ""
    articulo_referencia_corta: str = ""
    articulo_descripcion: str = ""
    articulo_envase_id: str = ""
    articulo_contenido_unidad: str = ""
    articulo_envase_cantidad: float = 0.0
    articulo_envase_peso: float = 0.0
    articulo_envase_unidad_medida: str = ""
    articulo_envase_peso_total: float = 0.0
    transporte_pallet_tipo: str = ""
    transporte_cajas_por_capa: float = 0.0
    transporte_capas_por_pallet: float = 0.0
    transporte_cajas_por_pallet: float = 0.0
    transporte_unidades_por_pallet: float = 0.0
    transporte_kg_por_pallet: float = 0.0
    transporte_observaciones: str = ""
    articulo_familia_id: str = ""
    articulo_grupo_id: str = ""
    articulo_subfamilia_id: str = ""
    categoria: str = ""
    articulo_status_activo: bool = True
    articulo_status_en_lista: bool = False


class IngredientIreksRead(IngredientIreksBase):
    id: int | None = None


class IngredientIreksCreate(IngredientIreksBase):
    id: int | None = None


class IngredientIreksUpdate(AppSchema):
    almacen_id: str | None = None
    fabricante_id: str | None = None
    distribuidor_id: str | None = None
    articulo_id: str | None = None
    articulo_referencia: str | None = None
    articulo_referencia_corta: str | None = None
    articulo_descripcion: str | None = None
    articulo_envase_id: str | None = None
    articulo_contenido_unidad: str | None = None
    articulo_envase_cantidad: float | None = None
    articulo_envase_peso: float | None = None
    articulo_envase_unidad_medida: str | None = None
    transporte_pallet_tipo: str | None = None
    transporte_cajas_por_capa: float | None = None
    transporte_capas_por_pallet: float | None = None
    transporte_observaciones: str | None = None
    articulo_familia_id: str | None = None
    articulo_grupo_id: str | None = None
    articulo_subfamilia_id: str | None = None
    categoria: str | None = None
    articulo_status_activo: bool | None = None
    articulo_status_en_lista: bool | None = None


class IngredientIreksCatalogsPayload(AppSchema):
    distribuidores: list[CatalogOption] = Field(default_factory=list)
    fabricantes: list[CatalogOption] = Field(default_factory=list)
    familias: list[CatalogOption] = Field(default_factory=list)
    subfamilias: list[CatalogOption] = Field(default_factory=list)
    envases: list[CatalogOption] = Field(default_factory=list)


class IngredientIreksListPayload(AppSchema):
    rows: list[IngredientIreksRead] = Field(default_factory=list)
    catalogs: IngredientIreksCatalogsPayload = Field(default_factory=IngredientIreksCatalogsPayload)


class TarifaPrecioIreksRead(AppSchema):
    id: int | None = None
    articulo_id: str = ""
    tarifa_ano: int = 0
    precio_fabricante: float = 0.0
    precio_distribuidor: float = 0.0
    descuento_pct: float = 0.0


class TarifaPrecioIreksCreate(AppSchema):
    articulo_id: str
    tarifa_ano: int
    precio_fabricante: float = 0.0
    precio_distribuidor: float = 0.0
    descuento_pct: float = 0.0


class TarifaPrecioIreksUpdate(AppSchema):
    tarifa_ano: int
    precio_fabricante: float = 0.0
    precio_distribuidor: float = 0.0
    descuento_pct: float = 0.0


class IngredientActiveUpdate(AppSchema):
    activo: bool


class IngredientStdBase(AppSchema):
    articulo_referencia_distribuidor: str = ""
    proveedor_id: str = ""
    distribuidor_id: str = ""
    articulo_descripcion: str = ""
    articulo_grupo_id: str = ""
    articulo_familia_id: str = ""
    articulo_subfamilia_id: str = ""
    categoria: str = ""
    formato: str = ""
    formato_cantidad: float = 0.0
    formato_unidad: str = "kg"
    pvp_formato: float = 0.0
    pvp_unidad_medida: float = 0.0
    activo: bool = True


class IngredientStdRead(IngredientStdBase):
    articulo_id: str
    distribuidor_nombre: str = ""


class IngredientStdCreate(IngredientStdBase):
    articulo_id: str | None = None


class IngredientStdUpdate(AppSchema):
    articulo_referencia_distribuidor: str | None = None
    proveedor_id: str | None = None
    distribuidor_id: str | None = None
    articulo_descripcion: str | None = None
    articulo_grupo_id: str | None = None
    articulo_familia_id: str | None = None
    articulo_subfamilia_id: str | None = None
    categoria: str | None = None
    formato: str | None = None
    formato_cantidad: float | None = None
    formato_unidad: str | None = None
    pvp_formato: float | None = None
    pvp_unidad_medida: float | None = None
    activo: bool | None = None


class MateriaPrimaPrecioRead(AppSchema):
    id: int | None = None
    articulo_id: str
    fecha_precio: date
    costo_neto: float = 0.0


__all__ = [
    "CatalogOption",
    "IngredientIreksBase",
    "IngredientIreksCatalogsPayload",
    "IngredientIreksCreate",
    "IngredientIreksListPayload",
    "IngredientIreksRead",
    "IngredientIreksUpdate",
    "IngredientStdBase",
    "IngredientStdCreate",
    "IngredientStdRead",
    "IngredientStdUpdate",
    "IngredientActiveUpdate",
    "MateriaPrimaPrecioRead",
    "NutritionValues",
    "TarifaPrecioIreksCreate",
    "TarifaPrecioIreksRead",
    "TarifaPrecioIreksUpdate",
]

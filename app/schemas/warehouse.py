from __future__ import annotations

from datetime import date

from sqlmodel import Field

from .base import AppSchema


class WarehouseOption(AppSchema):
    almacen_id: str
    almacen_nombre: str


class WarehouseMovementRead(AppSchema):
    id: int | None = None
    almacen_id: str
    articulo_id: str
    pedido_numero: str = ""
    pedido_albaran_numero: str = ""
    cantidad: float = 0.0
    articulo_lote: str = ""
    articulo_caducidad: date | None = None
    fecha_pedido: date
    albaran_item_id: str = ""


class WarehouseManualMovementCreate(AppSchema):
    almacen_id: str
    articulo_id: str
    cantidad: float
    mode: str = "in"
    fecha_pedido: date
    articulo_lote: str = ""
    articulo_caducidad: date | None = None
    pedido_albaran_numero: str = ""


class WarehouseStockRead(AppSchema):
    almacen_id: str
    articulo_id: str
    cantidad_total: float = 0.0


class InventoryHeaderRead(AppSchema):
    inventario_id: str
    almacen_id: str = ""
    fecha: date
    contador: str = ""
    aprobador: str = ""
    estado: str = ""
    lineas: int = 0
    ajustes: int = 0


class InventoryDetailRead(AppSchema):
    id: int | None = None
    inventario_id: str
    almacen_id: str = ""
    articulo_id: str = ""
    articulo_lote: str = ""
    articulo_caducidad: date | None = None
    teorico_uds: float = 0.0
    conteo_uds: float = 0.0
    diferencia_uds: float = 0.0
    kg_ajuste: float = 0.0


class InventoryAdjustmentInput(AppSchema):
    articulo_id: str
    articulo_lote: str = ""
    articulo_caducidad: date | None = None
    teorico_uds: float = 0.0
    conteo_uds: float = 0.0
    diferencia_uds: float = 0.0
    kg_ajuste: float = 0.0


class InventoryAdjustmentPayload(AppSchema):
    almacen_id: str
    contador: str = ""
    aprobador: str = ""
    adjustments: list[InventoryAdjustmentInput] = Field(default_factory=list)


class InventoryExportPayload(AppSchema):
    headers: list[InventoryHeaderRead] = Field(default_factory=list)
    details: list[InventoryDetailRead] = Field(default_factory=list)


__all__ = [
    "InventoryAdjustmentInput",
    "InventoryAdjustmentPayload",
    "InventoryDetailRead",
    "InventoryExportPayload",
    "InventoryHeaderRead",
    "WarehouseMovementRead",
    "WarehouseManualMovementCreate",
    "WarehouseOption",
    "WarehouseStockRead",
]

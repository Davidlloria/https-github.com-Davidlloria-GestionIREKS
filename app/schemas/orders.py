from __future__ import annotations

from datetime import date, datetime

from sqlmodel import Field

from .base import AppSchema, PaginatedResponse


class OrderLinePayload(AppSchema):
    articulo_id: str
    uds: float = 0.0


class OrderLineWrite(AppSchema):
    articulo_id: str
    articulo_cantidad: float = 0.0


class OrderBase(AppSchema):
    almacen_id: str = ""
    pedido_fecha: date
    pedido_numero: str = ""
    pedido_albaran_numero: str = ""
    pedido_factura_numero: str = ""
    pedido_ref: str = ""
    pedido_estado: str = ""


class OrderRead(OrderBase):
    pedido_id: str


class OrderListItem(OrderRead):
    almacen_nombre: str = ""
    semana: int = 0
    total_kg: float = 0.0


class OrderListResponse(PaginatedResponse):
    items: list[OrderListItem] = Field(default_factory=list)


class OrderCreate(AppSchema):
    almacen_id: str
    pedido_fecha: date
    pedido_numero: str = ""
    lines: list[OrderLinePayload] = Field(default_factory=list)
    is_pending: bool = False


class OrderUpdate(AppSchema):
    pedido_fecha: date
    pedido_numero: str = ""
    lines: list[OrderLinePayload] = Field(default_factory=list)
    submit_mode: str = ""


class OrderItemRead(AppSchema):
    item_id: str
    pedido_id: str
    pedido_numero: str = ""
    pedido_albaran_numero: str = ""
    pedido_item_fecha: date
    articulo_id: str
    articulo_cantidad: float = 0.0


class OrderItemListResponse(PaginatedResponse):
    items: list[OrderItemRead] = Field(default_factory=list)


class AlbaranRead(AppSchema):
    albaran_id: str
    almacen_id: str = ""
    pedido_id: str = ""
    albaran_numero: str = ""
    albaran_fecha: date


class AlbaranItemRead(AppSchema):
    item_id: str
    pedido_id: str = ""
    albaran_id: str = ""
    albaran_numero: str = ""
    albaran_fecha: date
    articulo_codigo: str = ""
    articulo_id: str = ""
    articulo_cantidad: float = 0.0
    articulo_lote: str = ""
    articulo_caducidad: date | None = None


class FacturaRead(AppSchema):
    factura_id: str
    almacen_id: str = ""
    pedido_id: str = ""
    factura_numero: str = ""
    factura_fecha: date
    albaran_numero: str = ""
    factura_referencia: str = ""
    total_kilos: float = 0.0
    importe_neto: float = 0.0
    total_factura: float = 0.0


class FacturaItemRead(AppSchema):
    item_id: str
    pedido_id: str = ""
    factura_id: str = ""
    factura_numero: str = ""
    factura_fecha: date
    albaran_numero: str = ""
    articulo_codigo: str = ""
    articulo_id: str = ""
    articulo_descripcion: str = ""
    articulo_cantidad: float = 0.0
    articulo_envase: float = 0.0
    articulo_kilos: float = 0.0
    articulo_lote: str = ""
    articulo_caducidad: date | None = None
    precio_unitario: float = 0.0
    dto_pct: float = 0.0
    iva_pct: float = 0.0
    total_linea: float = 0.0


class OrderPendingRead(AppSchema):
    pendiente_id: str
    pedido_id: str = ""
    albaran_id: str = ""
    articulo_id: str = ""
    cantidad_pedida: float = 0.0
    cantidad_recibida: float = 0.0
    cantidad_pendiente: float = 0.0
    estado: str = ""
    fecha_registro: datetime | None = None


class OrderPendingListResponse(PaginatedResponse):
    items: list[OrderPendingRead] = Field(default_factory=list)


class OrderJsonImportPayload(AppSchema):
    almacen_id: str
    source_path: str


class OrderJsonImportResponse(AppSchema):
    pedido_id: str = ""
    imported_items: int = 0
    skipped_unknown: list[str] = Field(default_factory=list)
    skipped_invalid: int = 0


class OrderDocumentImportPayload(AppSchema):
    source_path: str


class OrderDocumentImportResponse(AppSchema):
    imported: int = 0
    errors: list[str] = Field(default_factory=list)
    already_imported: bool = False
    message: str = ""


class OrderItemsImportResponse(AppSchema):
    imported: int = 0
    errors: list[str] = Field(default_factory=list)


__all__ = [
    "AlbaranItemRead",
    "AlbaranRead",
    "FacturaItemRead",
    "FacturaRead",
    "OrderBase",
    "OrderCreate",
    "OrderDocumentImportPayload",
    "OrderDocumentImportResponse",
    "OrderItemRead",
    "OrderItemListResponse",
    "OrderItemsImportResponse",
    "OrderJsonImportPayload",
    "OrderJsonImportResponse",
    "OrderLinePayload",
    "OrderLineWrite",
    "OrderListItem",
    "OrderListResponse",
    "OrderPendingRead",
    "OrderPendingListResponse",
    "OrderRead",
    "OrderUpdate",
]

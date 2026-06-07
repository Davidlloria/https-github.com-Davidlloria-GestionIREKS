from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.order_edit_flow_service import OrderEditFlowService
from app.services.order_service import OrderService


@dataclass
class OrderSelectedEditContext:
    status: str
    message: str = ""
    pedido_id: str = ""
    pedido: Any | None = None
    qty_by_articulo: dict[str, float] = field(default_factory=dict)
    confirm_label: str = ""
    allow_pending: bool = False


@dataclass
class OrderSelectedSaveResult:
    status: str
    message: str = ""
    pedido_id: str = ""


class OrderSelectedFlowService:
    def __init__(
        self,
        *,
        order_edit_flow_service: OrderEditFlowService | None = None,
        order_service: OrderService | None = None,
    ) -> None:
        self.order_edit_flow_service = order_edit_flow_service or OrderEditFlowService()
        self.order_service = order_service or OrderService()

    def build_edit_context(self, pedido_id: str, pedido_estado: str) -> OrderSelectedEditContext:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return OrderSelectedEditContext(status="not_found", message="Pedido no encontrado.")

        context = self.order_edit_flow_service.build_edit_context(clean_pedido_id)
        if context.status != "ready":
            return OrderSelectedEditContext(
                status=context.status,
                message=str(getattr(context, "message", "") or ""),
                pedido_id=str(getattr(context, "pedido_id", "") or clean_pedido_id),
            )

        estado = str(pedido_estado or "").strip().upper()
        return OrderSelectedEditContext(
            status="ready",
            pedido_id=context.pedido_id or clean_pedido_id,
            pedido=context.pedido,
            qty_by_articulo=dict(context.qty_by_articulo or {}),
            confirm_label="Guardar" if estado == "E" else "Consignar",
            allow_pending=(estado != "E"),
        )

    def save_selected_order_header(self, pedido_id: str, pedido_fecha: date, pedido_numero: str) -> OrderSelectedSaveResult:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return OrderSelectedSaveResult(status="not_found", message="Pedido no encontrado.")
        try:
            self.order_service.update_order_header(clean_pedido_id, pedido_fecha, str(pedido_numero or "").strip())
        except ValueError as exc:
            return OrderSelectedSaveResult(status="not_found", message=str(exc), pedido_id=clean_pedido_id)
        except Exception as exc:  # noqa: BLE001
            return OrderSelectedSaveResult(status="error", message=str(exc), pedido_id=clean_pedido_id)
        return OrderSelectedSaveResult(status="success", pedido_id=clean_pedido_id)

    def submit_selected_order_edit(
        self,
        pedido_id: str,
        pedido_fecha: date,
        pedido_numero: str,
        lines: list[Any],
        submit_mode: str,
    ) -> OrderSelectedSaveResult:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return OrderSelectedSaveResult(status="not_found", message="Pedido no encontrado.")
        result = self.order_edit_flow_service.submit_edit(
            clean_pedido_id,
            pedido_fecha,
            pedido_numero,
            list(lines or []),
            submit_mode,
        )
        return OrderSelectedSaveResult(status=result.status, message=result.message, pedido_id=result.pedido_id or clean_pedido_id)

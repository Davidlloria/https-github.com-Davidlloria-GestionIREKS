from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.order_query_service import OrderQueryService
from app.services.order_service import OrderLineInput, OrderService


@dataclass
class OrderEditFlowResult:
    status: str
    message: str = ""
    pedido_id: str = ""
    pedido: Any | None = None
    qty_by_articulo: dict[str, float] = field(default_factory=dict)


class OrderEditFlowService:
    def __init__(
        self,
        *,
        order_query_service: OrderQueryService | None = None,
        order_service: OrderService | None = None,
    ) -> None:
        self.order_query_service = order_query_service or OrderQueryService()
        self.order_service = order_service or OrderService()

    def build_edit_context(self, pedido_id: str) -> OrderEditFlowResult:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return OrderEditFlowResult(status="not_found", message="Pedido no encontrado.")
        try:
            pedido, qty_by_articulo = self.order_query_service.get_order_edit_payload(clean_pedido_id)
        except ValueError as exc:
            return OrderEditFlowResult(status="not_found", message=str(exc), pedido_id=clean_pedido_id)
        except Exception as exc:  # noqa: BLE001
            return OrderEditFlowResult(status="error", message=str(exc), pedido_id=clean_pedido_id)

        return OrderEditFlowResult(
            status="ready",
            pedido_id=clean_pedido_id,
            pedido=pedido,
            qty_by_articulo=dict(qty_by_articulo or {}),
        )

    def submit_edit(
        self,
        pedido_id: str,
        pedido_fecha: date,
        pedido_numero: str,
        lines: list[Any],
        submit_mode: str,
    ) -> OrderEditFlowResult:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return OrderEditFlowResult(status="not_found", message="Pedido no encontrado.")
        if not lines:
            return OrderEditFlowResult(status="empty_lines", pedido_id=clean_pedido_id)
        try:
            self.order_service.update_order(
                pedido_id=clean_pedido_id,
                pedido_fecha=pedido_fecha,
                pedido_numero=str(pedido_numero or "").strip(),
                lines=[OrderLineInput(line.articulo_id, float(line.uds)) for line in lines],
                submit_mode=str(submit_mode or "").strip(),
            )
        except ValueError as exc:
            return OrderEditFlowResult(status="not_found", message=str(exc), pedido_id=clean_pedido_id)
        except Exception as exc:  # noqa: BLE001
            return OrderEditFlowResult(status="error", message=str(exc), pedido_id=clean_pedido_id)
        return OrderEditFlowResult(status="success", pedido_id=clean_pedido_id)

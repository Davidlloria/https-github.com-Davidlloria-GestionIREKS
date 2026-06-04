from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.services.order_export_service import OrderExportService


@dataclass
class OrderMailFlowResult:
    status: str
    message: str = ""
    pedido_id: str = ""
    pedido_numero: str = ""
    destino_email: str = ""
    attachment_path: Path | None = None
    preview: dict[str, str] = field(default_factory=dict)
    edited_preview: dict[str, str] = field(default_factory=dict)
    send_direct: bool = False


class OrderMailFlowService:
    def __init__(self, *, order_export_service: OrderExportService | None = None) -> None:
        self.order_export_service = order_export_service or OrderExportService()

    def prepare_mail(self, *, pedido_id: str, pedido_numero: str, destino_email: str) -> OrderMailFlowResult:
        try:
            preparation = self.order_export_service.prepare_order_mail_attachment(
                pedido_id=pedido_id,
                pedido_numero=pedido_numero,
                destino_email=destino_email,
            )
        except Exception as exc:  # noqa: BLE001
            return OrderMailFlowResult(
                status="error",
                message=f"No se pudo preparar el email.\n{exc}",
                pedido_id=pedido_id,
                pedido_numero=pedido_numero,
                destino_email=destino_email,
            )

        return OrderMailFlowResult(
            status="prepared",
            pedido_id=pedido_id,
            pedido_numero=pedido_numero,
            destino_email=destino_email,
            attachment_path=preparation.attachment_path,
            preview=dict(preparation.preview or {}),
        )

    def send_prepared_mail(
        self,
        preparation: OrderMailFlowResult,
        edited_preview: dict[str, str] | None,
        *,
        send_direct: bool,
    ) -> OrderMailFlowResult:
        if preparation.status != "prepared" or preparation.attachment_path is None:
            return OrderMailFlowResult(
                status="error",
                message="No se pudo preparar el email.",
                pedido_id=preparation.pedido_id,
                pedido_numero=preparation.pedido_numero,
                destino_email=preparation.destino_email,
            )
        if edited_preview is None:
            return OrderMailFlowResult(
                status="cancelled",
                pedido_id=preparation.pedido_id,
                pedido_numero=preparation.pedido_numero,
                destino_email=preparation.destino_email,
                attachment_path=preparation.attachment_path,
                preview=dict(preparation.preview or {}),
            )

        try:
            outcome = self.order_export_service.send_order_mail(
                pedido_id=preparation.pedido_id,
                pedido_numero=preparation.pedido_numero,
                attachment_path=preparation.attachment_path,
                destino_email=str(edited_preview.get("to_email") or "").strip(),
                send_direct=send_direct,
                subject=str(edited_preview.get("subject") or "").strip(),
                body=str(edited_preview.get("body") or ""),
            )
        except Exception as exc:  # noqa: BLE001
            return OrderMailFlowResult(
                status="error",
                message=f"No se pudo preparar el email.\n{exc}",
                pedido_id=preparation.pedido_id,
                pedido_numero=preparation.pedido_numero,
                destino_email=preparation.destino_email,
                attachment_path=preparation.attachment_path,
                preview=dict(preparation.preview or {}),
                edited_preview=dict(edited_preview or {}),
                send_direct=send_direct,
            )

        return OrderMailFlowResult(
            status="sent" if send_direct else "drafted",
            pedido_id=preparation.pedido_id,
            pedido_numero=preparation.pedido_numero,
            destino_email=str(edited_preview.get("to_email") or "").strip(),
            attachment_path=preparation.attachment_path,
            preview=dict(preparation.preview or {}),
            edited_preview=dict(edited_preview or {}),
            send_direct=send_direct,
            message=str(outcome.get("subject") or "").strip(),
        )

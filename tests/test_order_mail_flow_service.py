from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services.order_mail_flow_service import OrderMailFlowResult, OrderMailFlowService


class _FakeOrderExportService:
    def __init__(self, *, prepare_error: Exception | None = None, send_error: Exception | None = None) -> None:
        self.prepare_error = prepare_error
        self.send_error = send_error
        self.prepare_calls: list[tuple[str, str, str]] = []
        self.send_calls: list[dict[str, object]] = []

    def prepare_order_mail_attachment(self, *, pedido_id: str, pedido_numero: str, destino_email: str) -> SimpleNamespace:
        self.prepare_calls.append((pedido_id, pedido_numero, destino_email))
        if self.prepare_error is not None:
            raise self.prepare_error
        return SimpleNamespace(
            attachment_path=Path("E:/tmp/pedido.xlsx"),
            preview={
                "to_email": destino_email,
                "subject": f"Pedido {pedido_numero}",
                "body": "Cuerpo",
            },
        )

    def send_order_mail(
        self,
        *,
        pedido_id: str,
        pedido_numero: str,
        attachment_path: Path,
        destino_email: str,
        send_direct: bool,
        subject: str,
        body: str,
    ) -> dict[str, str]:
        self.send_calls.append(
            {
                "pedido_id": pedido_id,
                "pedido_numero": pedido_numero,
                "attachment_path": attachment_path,
                "destino_email": destino_email,
                "send_direct": send_direct,
                "subject": subject,
                "body": body,
            }
        )
        if self.send_error is not None:
            raise self.send_error
        return {"subject": subject}


def test_prepare_mail_returns_prepared_result() -> None:
    fake_export = _FakeOrderExportService()
    service = OrderMailFlowService(order_export_service=fake_export)  # type: ignore[arg-type]

    result = service.prepare_mail(pedido_id="ped-1", pedido_numero="P-10", destino_email="test@example.com")

    assert result.status == "prepared"
    assert result.attachment_path == Path("E:/tmp/pedido.xlsx")
    assert result.preview == {
        "to_email": "test@example.com",
        "subject": "Pedido P-10",
        "body": "Cuerpo",
    }
    assert fake_export.prepare_calls == [("ped-1", "P-10", "test@example.com")]
    assert fake_export.send_calls == []


def test_prepare_mail_returns_error_without_outlook() -> None:
    fake_export = _FakeOrderExportService(prepare_error=RuntimeError("fallo prepare"))
    service = OrderMailFlowService(order_export_service=fake_export)  # type: ignore[arg-type]

    result = service.prepare_mail(pedido_id="ped-1", pedido_numero="P-10", destino_email="test@example.com")

    assert result.status == "error"
    assert result.message == "No se pudo preparar el email.\nfallo prepare"
    assert fake_export.prepare_calls == [("ped-1", "P-10", "test@example.com")]
    assert fake_export.send_calls == []


def test_send_prepared_mail_returns_cancelled_when_preview_is_closed() -> None:
    fake_export = _FakeOrderExportService()
    service = OrderMailFlowService(order_export_service=fake_export)  # type: ignore[arg-type]
    preparation = OrderMailFlowResult(
        status="prepared",
        pedido_id="ped-1",
        pedido_numero="P-10",
        destino_email="test@example.com",
        attachment_path=Path("E:/tmp/pedido.xlsx"),
        preview={"to_email": "test@example.com", "subject": "Pedido P-10", "body": "Cuerpo"},
    )

    result = service.send_prepared_mail(preparation, None, send_direct=False)

    assert result.status == "cancelled"
    assert fake_export.send_calls == []


def test_send_prepared_mail_returns_drafted_result() -> None:
    fake_export = _FakeOrderExportService()
    service = OrderMailFlowService(order_export_service=fake_export)  # type: ignore[arg-type]
    preparation = OrderMailFlowResult(
        status="prepared",
        pedido_id="ped-1",
        pedido_numero="P-10",
        destino_email="test@example.com",
        attachment_path=Path("E:/tmp/pedido.xlsx"),
        preview={"to_email": "test@example.com", "subject": "Pedido P-10", "body": "Cuerpo"},
    )

    result = service.send_prepared_mail(
        preparation,
        {"to_email": "edit@example.com", "subject": "Borrador", "body": "Texto"},
        send_direct=False,
    )

    assert result.status == "drafted"
    assert result.message == "Borrador"
    assert fake_export.send_calls == [
        {
            "pedido_id": "ped-1",
            "pedido_numero": "P-10",
            "attachment_path": Path("E:/tmp/pedido.xlsx"),
            "destino_email": "edit@example.com",
            "send_direct": False,
            "subject": "Borrador",
            "body": "Texto",
        }
    ]


def test_send_prepared_mail_returns_sent_result() -> None:
    fake_export = _FakeOrderExportService()
    service = OrderMailFlowService(order_export_service=fake_export)  # type: ignore[arg-type]
    preparation = OrderMailFlowResult(
        status="prepared",
        pedido_id="ped-1",
        pedido_numero="P-10",
        destino_email="test@example.com",
        attachment_path=Path("E:/tmp/pedido.xlsx"),
        preview={"to_email": "test@example.com", "subject": "Pedido P-10", "body": "Cuerpo"},
    )

    result = service.send_prepared_mail(
        preparation,
        {"to_email": "edit@example.com", "subject": "Enviar", "body": "Texto"},
        send_direct=True,
    )

    assert result.status == "sent"
    assert result.message == "Enviar"
    assert fake_export.send_calls == [
        {
            "pedido_id": "ped-1",
            "pedido_numero": "P-10",
            "attachment_path": Path("E:/tmp/pedido.xlsx"),
            "destino_email": "edit@example.com",
            "send_direct": True,
            "subject": "Enviar",
            "body": "Texto",
        }
    ]


def test_send_prepared_mail_returns_error_without_outlook() -> None:
    fake_export = _FakeOrderExportService(send_error=RuntimeError("fallo outlook"))
    service = OrderMailFlowService(order_export_service=fake_export)  # type: ignore[arg-type]
    preparation = OrderMailFlowResult(
        status="prepared",
        pedido_id="ped-1",
        pedido_numero="P-10",
        destino_email="test@example.com",
        attachment_path=Path("E:/tmp/pedido.xlsx"),
        preview={"to_email": "test@example.com", "subject": "Pedido P-10", "body": "Cuerpo"},
    )

    result = service.send_prepared_mail(
        preparation,
        {"to_email": "edit@example.com", "subject": "Enviar", "body": "Texto"},
        send_direct=True,
    )

    assert result.status == "error"
    assert result.message == "No se pudo preparar el email.\nfallo outlook"
    assert fake_export.send_calls == [
        {
            "pedido_id": "ped-1",
            "pedido_numero": "P-10",
            "attachment_path": Path("E:/tmp/pedido.xlsx"),
            "destino_email": "edit@example.com",
            "send_direct": True,
            "subject": "Enviar",
            "body": "Texto",
        }
    ]

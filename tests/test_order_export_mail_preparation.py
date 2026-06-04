from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import Workbook
from sqlmodel import SQLModel, Session, create_engine

import app.services.order_export_service as order_export_service_module
from app.models import Pedido
from app.services.order_export_service import OrderExportService, OrderMailPreparation


def _make_service_with_isolated_engine(tmp_path: Path, monkeypatch) -> OrderExportService:
    engine = create_engine(f"sqlite:///{tmp_path / 'orders.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(order_export_service_module, 'engine', engine)
    service = OrderExportService()
    service.orders_mail_settings.load = lambda: {'historico_dir': str(tmp_path / 'historial')}  # type: ignore[method-assign]
    return service


def test_prepare_order_mail_attachment_delegates_to_workbook_history_and_preview(tmp_path: Path) -> None:
    service = OrderExportService()
    fake_workbook = object()
    attachment_path = tmp_path / 'pedido.xlsx'

    def fake_build_order_workbook(pedido_id: str) -> tuple[object, str]:
        assert pedido_id == 'order-1'
        return fake_workbook, 'BASE-ORDER-1'

    def fake_save_order_excel_history(pedido_id: str, wb: object, default_base_name: str) -> Path:
        assert pedido_id == 'order-1'
        assert wb is fake_workbook
        assert default_base_name == 'BASE-ORDER-1'
        return attachment_path

    def fake_build_order_mail_preview(pedido_id: str, pedido_numero: str, destino_email: str) -> dict[str, str]:
        assert pedido_id == 'order-1'
        assert pedido_numero == 'PED-1'
        assert destino_email == 'destino@empresa.com'
        return {
            'to_email': destino_email,
            'subject': 'Pedido Semana 23',
            'body': 'Buenos dias Vanessa\nSaludos',
        }

    service.build_order_workbook = fake_build_order_workbook  # type: ignore[method-assign]
    service.save_order_excel_history = fake_save_order_excel_history  # type: ignore[method-assign]
    service.build_order_mail_preview = fake_build_order_mail_preview  # type: ignore[method-assign]

    preparation = service.prepare_order_mail_attachment('order-1', 'PED-1', 'destino@empresa.com')

    assert isinstance(preparation, OrderMailPreparation)
    assert preparation.attachment_path == attachment_path
    assert preparation.preview == {
        'to_email': 'destino@empresa.com',
        'subject': 'Pedido Semana 23',
        'body': 'Buenos dias Vanessa\nSaludos',
    }


def test_save_order_excel_history_uses_versioned_paths_in_configured_directory(tmp_path: Path, monkeypatch) -> None:
    service = _make_service_with_isolated_engine(tmp_path, monkeypatch)
    output = Workbook()

    with Session(order_export_service_module.engine) as session:
        session.add(Pedido(pedido_id='order-1', almacen_id='alm-1', pedido_fecha=date(2026, 5, 1)))
        session.commit()

    first = service.save_order_excel_history('order-1', output, 'Pedido Semana 18')
    second = service.save_order_excel_history('order-1', output, 'Pedido Semana 18')

    assert first.parent == tmp_path / 'historial' / '2026' / '05'
    assert first.name == 'Pedido Semana 18_v1.xlsx'
    assert second.name == 'Pedido Semana 18_v2.xlsx'
    assert first.exists()
    assert second.exists()


def test_send_order_mail_logs_success_and_returns_outcome(tmp_path: Path) -> None:
    service = OrderExportService()
    attachment_path = tmp_path / 'pedido.xlsx'
    logged: list[dict[str, str]] = []

    def fake_open_outlook_mail_with_attachment(**kwargs: object) -> dict[str, str]:
        assert kwargs['pedido_id'] == 'order-1'
        assert kwargs['pedido_numero'] == 'PED-1'
        assert kwargs['attachment_path'] == attachment_path
        assert kwargs['destino_email'] == 'destino@empresa.com'
        assert kwargs['send_direct'] is False
        assert kwargs['subject'] == 'Asunto final'
        assert kwargs['body'] == 'Cuerpo final'
        return {'subject': 'Asunto final'}

    def fake_log_order_mail_event(**kwargs: str) -> None:
        logged.append(kwargs)

    service.open_outlook_mail_with_attachment = fake_open_outlook_mail_with_attachment  # type: ignore[method-assign]
    service.log_order_mail_event = fake_log_order_mail_event  # type: ignore[method-assign]

    outcome = service.send_order_mail(
        pedido_id='order-1',
        pedido_numero='PED-1',
        attachment_path=attachment_path,
        destino_email='destino@empresa.com',
        send_direct=False,
        subject='Asunto final',
        body='Cuerpo final',
    )

    assert outcome == {'subject': 'Asunto final'}
    assert logged == [
        {
            'pedido_id': 'order-1',
            'pedido_numero': 'PED-1',
            'destino_email': 'destino@empresa.com',
            'asunto': 'Asunto final',
            'adjunto_path': str(attachment_path),
            'modo_envio': 'draft',
            'estado': 'BORRADOR',
            'error_detalle': '',
        }
    ]


def test_send_order_mail_logs_error_and_reraises_when_outlook_fails(tmp_path: Path) -> None:
    service = OrderExportService()
    attachment_path = tmp_path / 'pedido.xlsx'
    logged: list[dict[str, str]] = []

    def fake_open_outlook_mail_with_attachment(**kwargs: object) -> dict[str, str]:
        raise RuntimeError('Outlook no disponible')

    def fake_log_order_mail_event(**kwargs: str) -> None:
        logged.append(kwargs)

    service.open_outlook_mail_with_attachment = fake_open_outlook_mail_with_attachment  # type: ignore[method-assign]
    service.log_order_mail_event = fake_log_order_mail_event  # type: ignore[method-assign]

    try:
        service.send_order_mail(
            pedido_id='order-1',
            pedido_numero='PED-1',
            attachment_path=attachment_path,
            destino_email='destino@empresa.com',
            send_direct=True,
            subject='Asunto final',
            body='Cuerpo final',
        )
    except RuntimeError as exc:
        assert str(exc) == 'Outlook no disponible'
    else:
        raise AssertionError('Expected RuntimeError')

    assert logged == [
        {
            'pedido_id': 'order-1',
            'pedido_numero': 'PED-1',
            'destino_email': 'destino@empresa.com',
            'asunto': '',
            'adjunto_path': str(attachment_path),
            'modo_envio': 'send',
            'estado': 'ERROR',
            'error_detalle': 'Outlook no disponible',
        }
    ]

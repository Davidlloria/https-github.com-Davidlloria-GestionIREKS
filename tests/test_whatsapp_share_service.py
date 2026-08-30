from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import SQLModel, create_engine

from app.models import Cliente, Contacto
import app.services.whatsapp_share_service as service_module
from app.services.whatsapp_share_service import (
    WhatsAppPhoneError,
    WhatsAppShareService,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("600 123 456", "34600123456"),
        ("+34 600-123-456", "34600123456"),
        ("0034 600 123 456", "34600123456"),
        ("34600123456", "34600123456"),
    ],
)
def test_normalize_phone_supports_spanish_and_international_formats(
    raw: str,
    expected: str,
) -> None:
    assert WhatsAppShareService.normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "600123", "600123456 ext 2"])
def test_normalize_phone_rejects_unsafe_or_incomplete_values(raw: str) -> None:
    with pytest.raises(WhatsAppPhoneError):
        WhatsAppShareService.normalize_phone(raw)


def test_build_chat_url_encodes_phone_and_message() -> None:
    url = WhatsAppShareService.build_chat_url(
        "600 123 456",
        "Hola, ficha técnica",
    )

    assert url == (
        "https://wa.me/34600123456"
        "?text=Hola%2C%20ficha%20t%C3%A9cnica"
    )


def test_list_recipients_combines_customers_and_contacts(tmp_path: Path) -> None:
    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'whatsapp.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(db_engine)
    from sqlmodel import Session

    customer = Cliente(
        cliente_id="customer-1",
        cliente_codigo=1,
        cliente_nombre_comercial="Panadería Norte",
        cliente_telefono="600111222",
    )
    contact = Contacto(
        contacto_id="contact-1",
        contacto_codigo=1,
        cliente_id=customer.cliente_id,
        nombre="Ana",
        apellidos="López",
        telefono="+34 600 333 444",
    )
    with Session(db_engine) as session:
        session.add(customer)
        session.add(contact)
        session.commit()

    recipients = WhatsAppShareService(db_engine).list_recipients()

    assert [(item.source, item.label, item.phone) for item in recipients] == [
        ("Contacto", "Ana López · Panadería Norte", "+34 600 333 444"),
        ("Cliente", "Panadería Norte", "600111222"),
    ]


def test_reveal_file_uses_windows_explorer_selection(
    monkeypatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "Ficha técnica.pdf"
    calls: list[tuple[list[str], int]] = []
    monkeypatch.setattr(
        service_module.subprocess,
        "Popen",
        lambda args, creationflags=0: calls.append((args, creationflags)),
    )

    assert WhatsAppShareService.reveal_file(path) is True
    assert calls[0][0] == ["explorer.exe", f"/select,{path.resolve()}"]

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.core.database import engine
from app.models import Cliente, Contacto


class WhatsAppPhoneError(ValueError):
    """Raised when a phone number cannot be converted to WhatsApp format."""


@dataclass(frozen=True)
class WhatsAppRecipient:
    label: str
    phone: str
    source: str


class WhatsAppShareService:
    def __init__(self, db_engine: Engine = engine) -> None:
        self._engine = db_engine

    def list_recipients(self) -> list[WhatsAppRecipient]:
        with Session(self._engine) as session:
            customers = list(
                session.exec(
                    select(Cliente).order_by(Cliente.cliente_nombre_comercial)
                )
            )
            contacts = list(
                session.exec(
                    select(Contacto).order_by(Contacto.nombre, Contacto.apellidos)
                )
            )

        customer_names = {
            customer.cliente_id: self._customer_name(customer)
            for customer in customers
        }
        recipients = [
            WhatsAppRecipient(
                label=self._customer_name(customer),
                phone=str(customer.cliente_telefono or "").strip(),
                source="Cliente",
            )
            for customer in customers
            if str(customer.cliente_telefono or "").strip()
        ]
        for contact in contacts:
            phone = str(contact.telefono or "").strip()
            if not phone:
                continue
            name = f"{contact.nombre or ''} {contact.apellidos or ''}".strip()
            company = customer_names.get(contact.cliente_id, "")
            label = name or company or "Contacto"
            if company and company.casefold() != label.casefold():
                label = f"{label} · {company}"
            recipients.append(
                WhatsAppRecipient(label=label, phone=phone, source="Contacto")
            )
        return sorted(
            recipients,
            key=lambda item: (item.label.casefold(), item.phone),
        )

    @staticmethod
    def normalize_phone(phone: str) -> str:
        raw = str(phone or "").strip()
        if not raw:
            raise WhatsAppPhoneError("Introduce un número de teléfono.")
        if not re.fullmatch(r"[+\d\s().-]+", raw):
            raise WhatsAppPhoneError(
                "El teléfono contiene caracteres no admitidos."
            )
        digits = "".join(character for character in raw if character.isdigit())
        if raw.startswith("00"):
            digits = digits[2:]
        elif not raw.startswith("+") and len(digits) == 9:
            digits = f"34{digits}"
        if not 10 <= len(digits) <= 15:
            raise WhatsAppPhoneError(
                "Usa un número de 9 cifras de España o incluye el prefijo internacional."
            )
        return digits

    @classmethod
    def build_chat_url(cls, phone: str, message: str) -> str:
        normalized_phone = cls.normalize_phone(phone)
        encoded_message = quote(str(message or "").strip(), safe="")
        url = f"https://wa.me/{normalized_phone}"
        return f"{url}?text={encoded_message}" if encoded_message else url

    @staticmethod
    def reveal_file(path: Path) -> bool:
        resolved = Path(path).resolve()
        try:
            subprocess.Popen(
                ["explorer.exe", f"/select,{resolved}"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            return False
        return True

    @staticmethod
    def _customer_name(customer: Cliente) -> str:
        return (
            str(customer.cliente_nombre_comercial or "").strip()
            or str(customer.cliente_nombre_fiscal or "").strip()
            or str(customer.cliente_nombre_interno or "").strip()
            or f"Cliente {customer.cliente_codigo}"
        )

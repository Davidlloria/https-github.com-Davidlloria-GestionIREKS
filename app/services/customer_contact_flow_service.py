from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.core.database import engine as default_engine
from app.models import Cliente, Contacto
from app.viewmodels import CustomerViewModel
from app.viewmodels.contact_viewmodel import ContactViewModel


@dataclass(slots=True)
class CustomerContactFlowService:
    engine: object = default_engine
    customer_vm: CustomerViewModel | None = None
    contact_vm: ContactViewModel | None = None

    def __post_init__(self) -> None:
        if self.customer_vm is None:
            self.customer_vm = CustomerViewModel()
        if self.contact_vm is None:
            self.contact_vm = ContactViewModel()

    def related_contacts(self, cliente_id: str) -> list[Contacto]:
        clean_id = str(cliente_id or "").strip()
        if not clean_id:
            return []
        with Session(self.engine) as session:
            return list(
                session.exec(
                    select(Contacto)
                    .where(Contacto.cliente_id == clean_id)
                    .order_by(Contacto.apellidos, Contacto.nombre)
                )
            )

    def create_contact(self, payload: dict) -> Contacto:
        with Session(self.engine) as session:
            return self.contact_vm.create(session, payload)

    def update_contact(self, contacto_id: str, payload: dict) -> None:
        with Session(self.engine) as session:
            self.contact_vm.update(session, contacto_id, payload)

    def upsert_contact(self, contacto_id: str, payload: dict) -> str:
        with Session(self.engine) as session:
            if contacto_id:
                self.contact_vm.update(session, contacto_id, payload)
                return contacto_id
            created = self.contact_vm.create(session, payload)
            return str(getattr(created, "contacto_id", "") or "")

    def get_contact(self, contacto_id: str) -> Contacto | None:
        clean_id = str(contacto_id or "").strip()
        if not clean_id:
            return None
        with Session(self.engine) as session:
            return session.get(Contacto, clean_id)

    def ensure_unlinked_customer(self, unlinked_client_id: str) -> None:
        clean_id = str(unlinked_client_id or "").strip()
        if not clean_id:
            return
        with Session(self.engine) as session:
            existing = session.get(Cliente, clean_id)
            if existing:
                return
            self.customer_vm.create(
                session,
                {
                    "cliente_id": clean_id,
                    "cliente_nombre_comercial": "SIN CLIENTE",
                    "cliente_nombre_fiscal": "SIN CLIENTE",
                    "activo": True,
                },
            )

    def unlink_contact(self, contacto_id: str, unlinked_client_id: str) -> None:
        clean_contacto_id = str(contacto_id or "").strip()
        if not clean_contacto_id:
            raise ValueError("Contacto no encontrado.")
        with Session(self.engine) as session:
            contact = session.get(Contacto, clean_contacto_id)
            if not contact:
                raise ValueError("Contacto no encontrado.")
        self.ensure_unlinked_customer(unlinked_client_id)
        self.update_contact(clean_contacto_id, {"cliente_id": str(unlinked_client_id or "").strip()})

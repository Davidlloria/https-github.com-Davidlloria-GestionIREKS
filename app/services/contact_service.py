from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.database import engine
from app.core.pagination import DEFAULT_PAGE_LIMIT, page_items
from app.models import Cliente, Contacto
from app.schemas.contacts import (
    ContactCompanyOption,
    ContactCreate,
    ContactDetail,
    ContactListItem,
    ContactListResponse,
    ContactUpdate,
)
from app.services.import_service import ImportService
from app.viewmodels.contact_viewmodel import ContactViewModel
from app.viewmodels.customer_viewmodel import CustomerViewModel


@dataclass
class ContactCompanyLookup:
    id_to_name: dict[str, str] = field(default_factory=dict)
    name_to_id: dict[str, str] = field(default_factory=dict)


class ContactPayloadError(ValueError):
    """Raised when contact payload contains invalid related data."""


class ContactService:
    def __init__(self) -> None:
        self.vm = ContactViewModel()
        self.customer_vm = CustomerViewModel()
        self.import_service = ImportService()

    def company_lookup(self) -> ContactCompanyLookup:
        with Session(engine) as session:
            companies = list(session.exec(select(Cliente).order_by(Cliente.cliente_nombre_comercial)))
        lookup = ContactCompanyLookup()
        for company in companies:
            company_name = (company.cliente_nombre_comercial or "").strip()
            cliente_id = (getattr(company, "cliente_id", "") or "").strip()
            if not company_name:
                continue
            if cliente_id:
                lookup.id_to_name[cliente_id] = company_name
                lookup.name_to_id[company_name] = cliente_id
                lookup.name_to_id[company_name.lower()] = cliente_id
        return lookup

    def company_options_payload(self) -> list[ContactCompanyOption]:
        lookup = self.company_lookup()
        return [
            ContactCompanyOption(cliente_id=cliente_id, nombre=name)
            for cliente_id, name in sorted(lookup.id_to_name.items(), key=lambda item: item[1].lower())
        ]

    def list(
        self,
        term: str = "",
        company_id: str = "",
        company_id_to_name: dict[str, str] | None = None,
    ) -> list[Contacto]:
        company_id_to_name = company_id_to_name or {}
        with Session(engine) as session:
            rows = self.vm.list(session, "")
        clean_company_id = (company_id or "").strip()
        if clean_company_id:
            rows = [row for row in rows if str(row.cliente_id or "").strip() == clean_company_id]
        text = (term or "").strip().lower()
        if not text:
            return rows
        filtered = []
        for row in rows:
            full_name = f"{(row.nombre or '').strip()} {(row.apellidos or '').strip()}".strip().lower()
            company = company_id_to_name.get(row.cliente_id, "").lower()
            if text in full_name or text in company:
                filtered.append(row)
        return filtered

    def list_payload(
        self,
        term: str = "",
        *,
        company_id: str = "",
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> ContactListResponse:
        lookup = self.company_lookup()
        rows = self.list(term, company_id, lookup.id_to_name)
        page_rows = page_items(rows, limit=limit, offset=offset)
        return ContactListResponse(
            items=[self._contact_list_item(row, lookup.id_to_name) for row in page_rows],
            total=len(rows),
            limit=limit,
            offset=offset,
        )

    def detail_payload(self, contacto_id: str) -> ContactDetail | None:
        with Session(engine) as session:
            entity = session.get(Contacto, contacto_id)
            if entity is None:
                return None
            customer = session.get(Cliente, str(entity.cliente_id or ""))
            cliente_nombre = (
                str(getattr(customer, "cliente_nombre_comercial", "") or "").strip()
                or str(getattr(customer, "cliente_nombre_fiscal", "") or "").strip()
                if customer is not None
                else ""
            )
            payload = ContactDetail.from_entity(entity)
            payload.cliente_nombre = cliente_nombre
            return payload

    def create(self, payload: dict) -> Contacto:
        with Session(engine) as session:
            return self.vm.create(session, payload)

    def create_from_payload(self, payload: ContactCreate | dict) -> ContactDetail:
        data = self._payload_dict(payload, ContactCreate, exclude_none=True)
        self._ensure_customer_exists(str(data.get("cliente_id") or "").strip())
        created = self.create(data)
        return self._contact_detail_from_entity(created)

    def update(self, contacto_id: str, payload: dict) -> Contacto:
        with Session(engine) as session:
            return self.vm.update(session, contacto_id, payload)

    def update_from_payload(self, contacto_id: str, payload: ContactUpdate | dict) -> ContactDetail:
        data = self._payload_dict(payload, ContactUpdate, exclude_none=True)
        if "cliente_id" in data:
            self._ensure_customer_exists(str(data.get("cliente_id") or "").strip())
        updated = self.update(contacto_id, data)
        return self._contact_detail_from_entity(updated)

    def delete(self, contacto_id: str) -> bool:
        with Session(engine) as session:
            return self.vm.delete(session, contacto_id)

    def delete_blockers(self, contacto_id: str) -> list[str]:
        with engine.begin() as conn:
            asistentes = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM asistentes WHERE contacto_id = ?",
                (contacto_id,),
            ).scalar_one()
        if int(asistentes or 0) <= 0:
            return []
        return [f"{int(asistentes)} asistente(s) en cursos"]

    def import_file(self, file_path: Path) -> tuple[int, list[str]]:
        schema = [
            {"name": "contacto_id", "label": "Contacto_ID"},
            {"name": "nombre", "label": "Contacto_Nombre"},
            {"name": "apellidos", "label": "Contacto_Apellidos"},
            {"name": "cargo", "label": "Contacto_Cargo"},
            {"name": "nif", "label": "Contacto_NIF"},
            {"name": "telefono", "label": "Contacto_Telefono"},
            {"name": "email", "label": "Contacto_Email"},
            {"name": "cliente_id", "label": "Cliente_ID"},
        ]
        aliases = {
            "contacto_id": ["contacto_uuid"],
            "nombre": ["nombre", "contacto_nombre"],
            "apellidos": ["apellidos", "contacto_apellidos"],
            "cargo": ["cargo", "puesto"],
            "nif": ["dni", "documento"],
            "telefono": ["telefono", "movil", "celular"],
            "email": ["correo", "mail", "e_mail"],
            "cliente_id": ["empresa_id", "empresa_uuid", "cliente_uuid", "cliente_id"],
        }

        def create_payload_from_import(payload: dict) -> None:
            cliente_id = self.ensure_cliente_for_import(payload.get("cliente_id", ""))
            data = {
                "nombre": (payload.get("nombre") or "").strip(),
                "apellidos": (payload.get("apellidos") or "").strip(),
                "cargo": (payload.get("cargo") or "").strip(),
                "nif": (payload.get("nif") or "").strip(),
                "telefono": (payload.get("telefono") or "").strip(),
                "email": (payload.get("email") or "").strip(),
                "cliente_id": cliente_id,
            }
            contacto_id = (payload.get("contacto_id") or "").strip()
            if contacto_id:
                data["contacto_id"] = contacto_id
            self.create(data)

        return self.import_service.import_with_schema(
            file_path=file_path,
            schema=schema,
            create_fn=create_payload_from_import,
            required_fields=["contacto_id", "nombre", "cliente_id"],
            aliases=aliases,
        )

    def ensure_cliente_for_import(self, cliente_id: str) -> str:
        normalized = (cliente_id or "").strip()
        if not normalized:
            raise ValueError("Cliente_ID es obligatorio.")

        with Session(engine) as session:
            found = session.get(Cliente, normalized)
            if found:
                return found.cliente_id

            existing_id = session.exec(
                select(Cliente.cliente_id).where(func.lower(Cliente.cliente_id) == normalized.lower())
            ).first()
            if existing_id:
                return str(existing_id)

            placeholder_name = f"EMPRESA IMPORTADA {normalized[:8]}"
            self.customer_vm.create(
                session,
                {
                    "cliente_id": normalized,
                    "cliente_nombre_comercial": placeholder_name,
                    "cliente_nombre_fiscal": placeholder_name,
                    "activo": True,
                },
            )
            return normalized

    @staticmethod
    def _payload_dict(payload: object, schema_cls: type, *, exclude_none: bool) -> dict:
        if isinstance(payload, dict):
            model = schema_cls.model_validate(payload)
        else:
            model = schema_cls.model_validate(payload)
        return model.model_dump(exclude_none=exclude_none)

    @staticmethod
    def _contact_list_item(row: Contacto, company_id_to_name: dict[str, str]) -> ContactListItem:
        item = ContactListItem.from_entity(row)
        item.cliente_nombre = company_id_to_name.get(str(row.cliente_id or ""), "")
        return item

    def _contact_detail_from_entity(self, row: Contacto) -> ContactDetail:
        item = ContactDetail.from_entity(row)
        lookup = self.company_lookup()
        item.cliente_nombre = lookup.id_to_name.get(str(row.cliente_id or ""), "")
        return item

    @staticmethod
    def _ensure_customer_exists(cliente_id: str) -> None:
        clean_cliente_id = str(cliente_id or "").strip()
        if not clean_cliente_id:
            raise ContactPayloadError("El cliente indicado no existe o no es valido.")
        with Session(engine) as session:
            if session.get(Cliente, clean_cliente_id) is None:
                raise ContactPayloadError("El cliente indicado no existe o no es valido.")

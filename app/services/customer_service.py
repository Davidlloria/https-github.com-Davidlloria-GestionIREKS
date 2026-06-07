from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from app.core.database import engine
from app.core.pagination import DEFAULT_PAGE_LIMIT, page_items
from app.models import CodigoPostal, Cliente, Contacto, Isla, Localidad, Municipio, Provincia, Receta
from app.schemas.customers import (
    AddressOption,
    CustomerAddressCatalogsPayload,
    CustomerCreate,
    CustomerDetail,
    CustomerListItem,
    CustomerListResponse,
    CustomerUpdate,
)
from app.services.import_service import ImportService
from app.services.customer_contact_flow_service import CustomerContactFlowService
from app.viewmodels import CustomerViewModel


@dataclass
class AddressCatalogs:
    provincias: list[Provincia]
    islas: list[Isla]
    municipios: list[Municipio]
    codigos_postales: list[CodigoPostal]
    localidades: list[Localidad]


class CustomerService:
    def __init__(self) -> None:
        self.vm = CustomerViewModel()
        self.import_service = ImportService()
        self.contact_flow_service = CustomerContactFlowService(engine=engine, customer_vm=self.vm)

    def address_catalogs(self) -> AddressCatalogs:
        with Session(engine) as session:
            return AddressCatalogs(
                provincias=list(session.exec(select(Provincia).order_by(Provincia.provincia_nombre))),
                islas=list(session.exec(select(Isla).order_by(Isla.isla_nombre))),
                municipios=list(session.exec(select(Municipio).order_by(Municipio.municipio_nombre))),
                codigos_postales=list(
                    session.exec(select(CodigoPostal).order_by(CodigoPostal.codigo_postal, CodigoPostal.municipio_id))
                ),
                localidades=list(session.exec(select(Localidad).order_by(Localidad.localidad_nombre))),
            )

    def address_catalogs_payload(self) -> CustomerAddressCatalogsPayload:
        catalogs = self.address_catalogs()
        return CustomerAddressCatalogsPayload(
            provincias=[
                self._address_option(row, "provincia_id", "provincia_nombre", code_attr="provincia_codigo")
                for row in catalogs.provincias
            ],
            islas=[
                self._address_option(row, "isla_id", "isla_nombre", code_attr="isla_codigo", parent_attr="provincia_id")
                for row in catalogs.islas
            ],
            municipios=[
                self._address_option(
                    row,
                    "municipio_id",
                    "municipio_nombre",
                    code_attr="municipio_codigo",
                    parent_attr="isla_id",
                )
                for row in catalogs.municipios
            ],
            codigos_postales=[
                AddressOption(
                    id=f"{row.municipio_id}:{row.codigo_postal}",
                    label=str(row.codigo_postal or ""),
                    code=str(row.codigo_postal or ""),
                    parent_id=str(row.municipio_id or ""),
                )
                for row in catalogs.codigos_postales
            ],
            localidades=[
                self._address_option(
                    row,
                    "localidad_id",
                    "localidad_nombre",
                    code_attr="codigo_postal",
                    parent_attr="municipio_id",
                )
                for row in catalogs.localidades
            ],
        )

    def list(self, term: str = "") -> list[Cliente]:
        with Session(engine) as session:
            return self.vm.list(session, term)

    def list_payload(
        self,
        term: str = "",
        *,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> CustomerListResponse:
        rows = self.list(term)
        page_rows = page_items(rows, limit=limit, offset=offset)
        return CustomerListResponse(
            items=CustomerListItem.list_from_entities(page_rows),
            total=len(rows),
            limit=limit,
            offset=offset,
        )

    def detail_payload(self, customer_id: str) -> CustomerDetail | None:
        with Session(engine) as session:
            entity = session.get(Cliente, customer_id)
            if entity is None:
                return None
            return CustomerDetail.from_entity(entity)

    def create(self, payload: dict) -> Cliente:
        with Session(engine) as session:
            return self.vm.create(session, payload)

    def create_from_payload(self, payload: CustomerCreate | dict) -> CustomerDetail:
        data = self._payload_dict(payload, CustomerCreate, exclude_none=True)
        created = self.create(data)
        return CustomerDetail.from_entity(created)

    def update(self, entity_id: str, payload: dict) -> Cliente:
        with Session(engine) as session:
            return self.vm.update(session, entity_id, payload)

    def update_from_payload(self, entity_id: str, payload: CustomerUpdate | dict) -> CustomerDetail:
        data = self._payload_dict(payload, CustomerUpdate, exclude_none=True)
        updated = self.update(entity_id, data)
        return CustomerDetail.from_entity(updated)

    def delete(self, entity_id: str) -> bool:
        with Session(engine) as session:
            return self.vm.delete(session, entity_id)

    def delete_blockers(self, customer_id: str) -> list[str]:
        with engine.begin() as conn:
            counts = {
                "contactos": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM contactos WHERE cliente_id = ?",
                    (customer_id,),
                ).scalar_one(),
                "recetas": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM recetas WHERE cliente_id = ?",
                    (customer_id,),
                ).scalar_one(),
                "asistentes": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM asistentes WHERE cliente_id = ?",
                    (customer_id,),
                ).scalar_one(),
            }
        labels = {
            "contactos": "contacto(s)",
            "recetas": "receta(s)",
            "asistentes": "asistente(s) en cursos",
        }
        return [f"{count} {labels[name]}" for name, count in counts.items() if int(count or 0) > 0]

    def related_contacts(self, cliente_id: str) -> list[Contacto]:
        return self.contact_flow_service.related_contacts(cliente_id)

    def related_recipes(self, cliente_id: str) -> list[Receta]:
        clean_id = str(cliente_id or "").strip()
        if not clean_id:
            return []
        with Session(engine) as session:
            return list(
                session.exec(
                    select(Receta)
                    .where(Receta.cliente_id == clean_id)
                    .order_by(Receta.nombre, Receta.version)
                )
            )

    def recipe_customer_id(self, recipe_id: int) -> str:
        if recipe_id <= 0:
            return ""
        with Session(engine) as session:
            recipe = session.get(Receta, recipe_id)
        return str(getattr(recipe, "cliente_id", "") or "").strip() if recipe is not None else ""

    def create_contact(self, payload: dict) -> Contacto:
        return self.contact_flow_service.create_contact(payload)

    def update_contact(self, contacto_id: str, payload: dict) -> None:
        self.contact_flow_service.update_contact(contacto_id, payload)

    def upsert_contact(self, contacto_id: str, payload: dict) -> str:
        return self.contact_flow_service.upsert_contact(contacto_id, payload)

    def get_contact(self, contacto_id: str) -> Contacto | None:
        return self.contact_flow_service.get_contact(contacto_id)

    def ensure_unlinked_customer(self, unlinked_client_id: str) -> None:
        self.contact_flow_service.ensure_unlinked_customer(unlinked_client_id)

    def unlink_contact(self, contacto_id: str, unlinked_client_id: str) -> None:
        self.contact_flow_service.unlink_contact(contacto_id, unlinked_client_id)

    def import_file(self, file_path: Path, schema: list[dict]) -> tuple[int, list[str]]:
        aliases = {
            "cliente_id": ["cliente_uuid", "clienteid"],
            "cliente_nombre_fiscal": ["razon_social", "nombre_fiscal_cliente", "nombre_fiscal"],
            "cliente_nombre_comercial": ["cliente", "nombre", "nombre_cliente", "nombre_comercial"],
            "cliente_nombre_interno": ["nombre_interno"],
            "cliente_abreviatura": ["abreviatura", "abrev_pedido", "siglas"],
            "cliente_cif": ["cif", "nif"],
            "cliente_telefono": ["telefono_1", "movil", "tlf", "telefono"],
            "cliente_email": ["correo", "correo_electronico", "email"],
            "cliente_direccion": ["domicilio", "direccion"],
            "cliente_direccion_cp": ["cp", "codigo_postal"],
            "cliente_tipo": ["tipo"],
            "cliente_grupo": ["grupo"],
            "activo": ["estado", "habilitado"],
        }
        return self.import_service.import_with_schema(
            file_path=file_path,
            schema=schema,
            create_fn=self.create,
            required_fields=["cliente_id", "cliente_nombre_comercial"],
            aliases=aliases,
        )

    @staticmethod
    def _payload_dict(payload: object, schema_cls: type, *, exclude_none: bool) -> dict:
        if isinstance(payload, dict):
            model = schema_cls.model_validate(payload)
        else:
            model = schema_cls.model_validate(payload)
        return model.model_dump(exclude_none=exclude_none)

    @staticmethod
    def _address_option(
        row: object,
        id_attr: str,
        label_attr: str,
        *,
        code_attr: str = "",
        parent_attr: str = "",
    ) -> AddressOption:
        return AddressOption(
            id=str(getattr(row, id_attr, "") or ""),
            label=str(getattr(row, label_attr, "") or ""),
            code=str(getattr(row, code_attr, "") or "") if code_attr else "",
            parent_id=str(getattr(row, parent_attr, "") or "") if parent_attr else "",
        )

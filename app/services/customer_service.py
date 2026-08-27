from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import unicodedata

from sqlmodel import Session, col, select

from app.core.database import engine
from app.core.pagination import DEFAULT_PAGE_LIMIT, page_items
from app.models import ClienteAgenda, CodigoPostal, Cliente, Contacto, Isla, Localidad, Municipio, Provincia, Receta
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
from app.services.customer_agenda_service import CustomerAgendaService
from app.services.customer_contact_flow_service import CustomerContactFlowService
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService
from app.viewmodels import CustomerViewModel


@dataclass
class AddressCatalogs:
    provincias: list[Provincia]
    islas: list[Isla]
    municipios: list[Municipio]
    codigos_postales: list[CodigoPostal]
    localidades: list[Localidad]


@dataclass(frozen=True)
class CustomerMergePreview:
    source_customer_id: str
    target_customer_id: str
    source_label: str
    target_label: str
    counts: dict[str, int]


@dataclass(frozen=True)
class CustomerMergeResult(CustomerMergePreview):
    deleted_source: bool


class CustomerService:
    def __init__(self) -> None:
        self.vm = CustomerViewModel()
        self.import_service = ImportService()
        self.agenda_service = CustomerAgendaService(engine=engine)
        self.contact_flow_service = CustomerContactFlowService(engine=engine, customer_vm=self.vm)
        self.sales_summary_service = SalesAnnualComparisonService(db_engine=engine)

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
                self._address_option(row, "isla_id", "isla_nombre", code_attr="isla_iniciales", parent_attr="provincia_id")
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

    def preview_merge(self, source_customer_id: str, target_customer_id: str) -> CustomerMergePreview:
        source_id, target_id = self._validate_merge_ids(source_customer_id, target_customer_id)
        with engine.begin() as conn:
            source = self._customer_merge_row(conn, source_id)
            target = self._customer_merge_row(conn, target_id)
            if source is None:
                raise ValueError("Cliente origen no encontrado.")
            if target is None:
                raise ValueError("Cliente destino no encontrado.")
            return CustomerMergePreview(
                source_customer_id=source_id,
                target_customer_id=target_id,
                source_label=self._customer_merge_label(source),
                target_label=self._customer_merge_label(target),
                counts=self._customer_merge_counts(conn, source_id, target_id),
            )

    def merge_customers(self, source_customer_id: str, target_customer_id: str) -> CustomerMergeResult:
        source_id, target_id = self._validate_merge_ids(source_customer_id, target_customer_id)
        with engine.begin() as conn:
            source = self._customer_merge_row(conn, source_id)
            target = self._customer_merge_row(conn, target_id)
            if source is None:
                raise ValueError("Cliente origen no encontrado.")
            if target is None:
                raise ValueError("Cliente destino no encontrado.")
            counts = self._customer_merge_counts(conn, source_id, target_id)
            for table_name in (
                "contactos",
                "recetas",
                "clientes_agenda",
                "asistentes",
                "promociones_clientes_productos",
                "ventas_clientes_raw",
            ):
                if table_name == "ventas_clientes_raw":
                    continue
                conn.exec_driver_sql(
                    f"UPDATE {table_name} SET cliente_id = ? WHERE cliente_id = ?",
                    (target_id, source_id),
                )
            sales_source_ids = self._customer_merge_sales_source_ids(conn, source_id, target_id, include_target=False)
            for sales_source_id in sorted(sales_source_ids):
                conn.exec_driver_sql(
                    "UPDATE ventas_clientes_raw SET cliente_id = ? WHERE cliente_id = ?",
                    (target_id, sales_source_id),
                )
            deleted = conn.exec_driver_sql(
                "DELETE FROM clientes WHERE cliente_id = ?",
                (source_id,),
            ).rowcount
            return CustomerMergeResult(
                source_customer_id=source_id,
                target_customer_id=target_id,
                source_label=self._customer_merge_label(source),
                target_label=self._customer_merge_label(target),
                counts=counts,
                deleted_source=bool(deleted),
            )

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
                "agenda": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM clientes_agenda WHERE cliente_id = ?",
                    (customer_id,),
                ).scalar_one(),
                "asistentes": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM asistentes WHERE cliente_id = ?",
                    (customer_id,),
                ).scalar_one(),
                "ventas_clientes": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM ventas_clientes_raw WHERE cliente_id = ?",
                    (customer_id,),
                ).scalar_one(),
                "promociones": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM promociones_clientes_productos WHERE cliente_id = ?",
                    (customer_id,),
                ).scalar_one(),
            }
        labels = {
            "contactos": "contacto(s)",
            "recetas": "receta(s)",
            "agenda": "actividad(es) de agenda",
            "asistentes": "asistente(s) en cursos",
            "ventas_clientes": "venta(s) de clientes",
            "promociones": "promoción(es) comercial(es)",
        }
        return [f"{count} {labels[name]}" for name, count in counts.items() if int(count or 0) > 0]

    def _validate_merge_ids(self, source_customer_id: str, target_customer_id: str) -> tuple[str, str]:
        source_id = str(source_customer_id or "").strip()
        target_id = str(target_customer_id or "").strip()
        if not source_id:
            raise ValueError("Cliente origen no indicado.")
        if not target_id:
            raise ValueError("Cliente destino no indicado.")
        if source_id == target_id:
            raise ValueError("El cliente origen y destino no pueden ser el mismo.")
        return source_id, target_id

    def _customer_merge_row(self, conn, customer_id: str):
        return conn.exec_driver_sql(
            """
            SELECT cliente_id, cliente_codigo, cliente_nombre_comercial, cliente_nombre_fiscal
            FROM clientes
            WHERE cliente_id = ?
            """,
            (customer_id,),
        ).fetchone()

    def _customer_merge_label(self, row) -> str:
        code = str(row[1] or "").strip()
        name = str(row[2] or row[3] or "").strip()
        return f"{code} - {name}".strip(" -")

    def _customer_merge_counts(self, conn, source_customer_id: str, target_customer_id: str = "") -> dict[str, int]:
        sales_source_ids = self._customer_merge_sales_source_ids(conn, source_customer_id, target_customer_id, include_target=True)
        queries = {
            "contactos": "SELECT COUNT(*) FROM contactos WHERE cliente_id = ?",
            "recetas": "SELECT COUNT(*) FROM recetas WHERE cliente_id = ?",
            "agenda": "SELECT COUNT(*) FROM clientes_agenda WHERE cliente_id = ?",
            "asistentes": "SELECT COUNT(*) FROM asistentes WHERE cliente_id = ?",
            "promociones": "SELECT COUNT(*) FROM promociones_clientes_productos WHERE cliente_id = ?",
        }
        counts = {
            name: int(conn.exec_driver_sql(query, (customer_id,)).scalar_one() or 0)
            for name, query in queries.items()
            for customer_id in [source_customer_id]
        }
        counts["ventas_clientes"] = sum(
            int(
                conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM ventas_clientes_raw WHERE cliente_id = ?",
                    (sales_source_id,),
                ).scalar_one()
                or 0
            )
            for sales_source_id in sales_source_ids
        )
        return counts

    def _customer_merge_sales_source_ids(
        self,
        conn,
        source_customer_id: str,
        target_customer_id: str = "",
        *,
        include_target: bool,
    ) -> set[str]:
        source_id = str(source_customer_id or "").strip()
        target_id = str(target_customer_id or "").strip()
        source = self._customer_merge_row(conn, source_id)
        if source is None:
            return {source_id} if source_id else set()
        search_terms = {
            self._normalize_merge_text(source[2]),
            self._normalize_merge_text(source[3]),
        }
        search_terms = {term for term in search_terms if term}
        ids = {source_id}
        if search_terms:
            rows = conn.exec_driver_sql(
                """
                SELECT cliente_id, cliente_codigo, cliente_nombre_comercial, cliente_nombre_fiscal, cliente_abreviatura
                FROM clientes
                """
            ).fetchall()
            for row in rows:
                row_id = str(row[0] or "").strip()
                if not row_id:
                    continue
                searchable = self._normalize_merge_text(
                    " ".join(str(value or "") for value in (row[1], row[2], row[3], row[4]))
                )
                if any(term in searchable or searchable in term for term in search_terms):
                    ids.add(row_id)
        if not include_target:
            ids.discard(target_id)
        return ids

    def _normalize_merge_text(self, value: object) -> str:
        text = str(value or "").strip().lower()
        decomposed = unicodedata.normalize("NFKD", text)
        return "".join(char for char in decomposed if not unicodedata.combining(char))

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
                    .where(
                        Receta.cliente_id == clean_id,
                        col(Receta.es_base).is_(False),
                    )
                    .order_by(Receta.nombre, Receta.version)
                )
            )

    def related_sales_years(self) -> list[int]:
        return self.sales_summary_service.list_years_clientes()

    def related_sales_latest_month(self, year: int) -> int:
        return self.sales_summary_service.latest_sales_month_clientes(year)

    def related_sales_months(self, cliente_id: str, year: int) -> tuple[int, ...]:
        return self.sales_summary_service.sales_months_clientes(year, cliente_id=cliente_id)

    def related_sales(self, cliente_id: str, year: int, *, month_from: int = 1, month_to: int = 12) -> list[Any]:
        clean_id = str(cliente_id or "").strip()
        clean_year = int(year or 0)
        if not clean_id or clean_year <= 0:
            return []
        return self.sales_summary_service.listar_resumen_anual_clientes(
            year=clean_year,
            cliente_id=clean_id,
            month_from=month_from,
            month_to=month_to,
        )

    def related_sales_monthly_product(
        self,
        cliente_id: str,
        year: int,
        *,
        articulo_id: str = "",
        articulo_codigo: str = "",
    ) -> list[Any]:
        clean_id = str(cliente_id or "").strip()
        clean_year = int(year or 0)
        if not clean_id or clean_year <= 0:
            return []
        return self.sales_summary_service.listar_ventas_mensuales_cliente_producto(
            year=clean_year,
            cliente_id=clean_id,
            articulo_id=articulo_id,
            articulo_codigo=articulo_codigo,
        )

    def related_agenda(self, cliente_id: str) -> list[ClienteAgenda]:
        return self.agenda_service.related_agenda(cliente_id)

    def get_agenda_activity(self, agenda_id: str) -> ClienteAgenda | None:
        return self.agenda_service.get_activity(agenda_id)

    def upsert_agenda_activity(self, agenda_id: str, payload: dict) -> ClienteAgenda:
        return self.agenda_service.upsert_activity(agenda_id, payload)

    def create_agenda_activity(self, payload: dict) -> ClienteAgenda:
        return self.agenda_service.create_activity(payload)

    def update_agenda_activity(self, agenda_id: str, payload: dict) -> ClienteAgenda:
        return self.agenda_service.update_activity(agenda_id, payload)

    def delete_agenda_activity(self, agenda_id: str) -> bool:
        return self.agenda_service.delete_activity(agenda_id)


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
            "cliente_actividad": ["actividad", "grupo"],
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

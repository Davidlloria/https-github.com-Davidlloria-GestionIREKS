from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
import warnings
from uuid import NAMESPACE_URL, uuid4, uuid5

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlmodel import Session, col, select
from sqlalchemy import func

from app.core.config import BASE_DIR
from app.core.database import engine
from app.models import (
    AlmacenMovimiento,
    Cliente,
    Distribuidor,
    Fabricante,
    Familia,
    IngredienteIreks,
    ReferenciaDistribuidor,
    Subfamilia,
    TarifaPrecioIreks,
    VentaClientesImportLote,
    VentaClientesRaw,
    VentaImportLote,
    VentaMensualRaw,
)
from app.services.igsa_sales_pdf_flow_service import IgsaSalesPdfFlowService
from app.services.igsa_sales_workbook_flow_service import IgsaSalesWorkbookFlowService
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService
from app.services.sales_annual_comparison_service import SalesComparisonRow
from app.services.sales_text_normalizer import normalize_search_text


SALES_CLIENT_TYPES = {"distribuidor", "directo", "cliente directo", "cliente_directo"}
SALES_CLIENT_EXCLUDED_TYPES = SALES_CLIENT_TYPES


@dataclass
class SalesOpResult:
    ok: bool
    message: str
    imported: int = 0
    incidencias: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClientesImportLoteRow:
    lote_id: str
    creado_en: str
    archivo_nombre: str
    anio: int
    estado: str
    archivo_hash: str
    filas: int


@dataclass
class IgsaPdfParsedLine:
    source_file: str
    doc_type: str
    fecha: str
    ref_pedido: str
    codigo: str
    descripcion: str
    kilos: float
    envases: float
    emb: float
    precio: float
    descuento_pct: float
    total: float
    iva: float
    lote: str
    carga: str
    cons_pref: str


@dataclass
class IgsaWorkbookParsedLine:
    sheet_name: str
    source_row: int
    tipo: str
    periodo: str
    ref_distribuidor: str
    codigo: str
    descripcion: str
    peso_envase: float
    cantidad_total: float
    cantidad_lote: float
    lote: str
    es_sc: bool
    suma_cantidad_lotes: float


@dataclass
class ClientesWorkbookParsedLine:
    source_row: int
    anio: int
    cliente_id: str
    cliente_codigo: str
    cliente_nombre: str
    articulo_id: str
    articulo_descripcion: str
    unidades: float


@dataclass
class ClientesImportPreview:
    total_rows: int
    valid_rows: int
    invalid_rows: int
    preview_rows: list[dict[str, object]]
    issues: list[str]
    anio: int = 0
    duplicate_rows: int = 0
    import_rows: list[dict[str, object]] = field(default_factory=list)


class SalesReconciliationService:
    def __init__(self) -> None:
        self._igsa_unit_codes = {"LPAO", "LPAOP", "555", "777"}
        self._igsa_rows_cache: list[dict[str, object]] | None = None
        self._igsa_mtime_ns: int | None = None
        self._igsa_pdf_flow_service = IgsaSalesPdfFlowService()
        self._igsa_workbook_flow_service = IgsaSalesWorkbookFlowService()
        self._sales_annual_comparison_service = SalesAnnualComparisonService(db_engine=engine)

    def _is_sc_tipo(self, tipo: str) -> bool:
        t = self._normalize_igsa_tipo(tipo)
        return t in {"s/c", "muestra", "muestras", "promocion", "promociones"}

    def _resolve_igsa_distribuidor_ids(self, session: Session, cliente_id: str) -> set[str]:
        ids: set[str] = set()
        clean_cliente_id = str(cliente_id or "").strip()
        if clean_cliente_id:
            ids.add(clean_cliente_id)
        cliente = session.get(Cliente, clean_cliente_id) if clean_cliente_id else None
        distribuidor_id = str(getattr(cliente, "distribuidor_id", "") or "").strip() if cliente else ""
        if distribuidor_id:
            ids.add(distribuidor_id)
        if not distribuidor_id:
            dist_rows = list(session.exec(select(Distribuidor)))
            for row in dist_rows:
                comercial = str(getattr(row, "distribuidor_nombre_comercial", "") or "").strip().lower()
                fiscal = str(getattr(row, "distribuidor_razon_social", "") or "").strip().lower()
                if "igsa" in comercial or "igsa" in fiscal:
                    ids.add(str(getattr(row, "distribuidor_id", "") or "").strip())
                    break
        return {x for x in ids if x}

    def import_ireks_json(self, file_path: Path) -> SalesOpResult:
        try:
            data = self._read_json(file_path)
        except ValueError as exc:
            return SalesOpResult(False, str(exc))
        rows_data, default_year, default_month, default_cliente_id = self._normalize_ireks_json_payload(data)
        if not rows_data:
            return SalesOpResult(False, "El JSON de IREKS no contiene filas.")

        file_hash = self._file_hash(file_path)
        with Session(engine) as session:
            existing = session.exec(
                select(VentaImportLote).where(
                    VentaImportLote.fuente == "ireks",
                    VentaImportLote.archivo_hash == file_hash,
                )
            ).first()
            if existing is not None:
                return SalesOpResult(True, "El archivo ya estaba importado.", imported=0, incidencias=0)

            rows: list[VentaMensualRaw] = []
            skipped = 0
            first_period = ""
            first_cliente_id = ""
            client_rows = list(
                session.exec(
                    select(Cliente.cliente_id, Cliente.cliente_nombre_comercial, Cliente.cliente_nombre_fiscal, Cliente.cliente_tipo)
                )
            )
            allowed_by_id: dict[str, str] = {}
            allowed_by_name: dict[str, str] = {}
            for cid, ncom, nfis, ctype in client_rows:
                tipo = str(ctype or "").strip().lower()
                if tipo not in SALES_CLIENT_TYPES:
                    continue
                cliente_id_val = str(cid or "").strip()
                if not cliente_id_val:
                    continue
                allowed_by_id[cliente_id_val] = cliente_id_val
                for raw_name in (ncom, nfis):
                    norm_name = self._normalize_search_text(raw_name)
                    if norm_name:
                        allowed_by_name[norm_name] = cliente_id_val
            for item in rows_data:
                if not isinstance(item, dict):
                    skipped += 1
                    continue

                year = self._to_int(self._get_any(item, "venta_Anio", "venta_Anio".lower(), "anio", "año"))
                month = self._parse_month(self._get_any(item, "venta_Mes", "mes", "venta_Mes".lower()))
                if year <= 0:
                    year = default_year
                if month < 1 or month > 12:
                    month = default_month
                if year <= 0 or month < 1 or month > 12:
                    skipped += 1
                    continue

                periodo = f"{year:04d}-{month:02d}"
                if not first_period:
                    first_period = periodo
                cliente_id = str(self._get_any(item, "Cliente_ID", "cliente_id", "ClienteId", "clienteid") or "").strip()
                if not cliente_id:
                    cliente_id = default_cliente_id
                if cliente_id and not first_cliente_id:
                    first_cliente_id = cliente_id

                code = self._normalize_code(self._get_any(item, "Código", "CÃ³digo", "Codigo", "codigo"))
                articulo_id = str(self._get_any(item, "Articulo_ID", "articulo_id", "Articulo_Id") or "").strip()
                if self._is_total_row(code) or (not code and not articulo_id):
                    skipped += 1
                    continue

                rows.append(
                    VentaMensualRaw(
                        raw_id=str(uuid4()),
                        lote_id="",
                        fuente="ireks",
                        cliente_id=cliente_id,
                        periodo=periodo,
                        articulo_codigo_origen=code,
                        articulo_id=articulo_id,
                        articulo_descripcion_origen=str(
                            self._get_any(item, "Descripción", "DescripciÃ³n", "Descripcion", "descripcion") or ""
                        ).strip(),
                        venta_kilos=self._to_float(self._get_any(item, "venta_Kilos", "venta_kilos", "Kilos", "kilos")),
                        venta_kilos_sc=self._to_float(
                            self._get_any(item, "venta_kilos_SC", "venta_Kilos_SC", "S/C", "SC", "sc")
                        ),
                        venta_euros=self._to_float(
                            self._get_any(item, "Venta_euros", "venta_Euros", "venta_euros", "Ventas", "ventas")
                        ),
                        payload_json=json.dumps(item, ensure_ascii=False),
                    )
                )

            if not rows:
                return SalesOpResult(False, "No se pudo importar ninguna fila válida.", imported=0, incidencias=skipped)

            lote = VentaImportLote(
                lote_id=str(uuid4()),
                fuente="ireks",
                cliente_id=first_cliente_id,
                periodo=first_period,
                archivo_nombre=file_path.name,
                archivo_hash=file_hash,
                estado="procesado",
            )
            session.add(lote)
            session.flush()
            for row in rows:
                row.lote_id = lote.lote_id
                session.add(row)
            session.commit()

        return SalesOpResult(True, "Importación IREKS completada.", imported=len(rows), incidencias=skipped)

    def import_igsa_excel(self, file_path: Path) -> SalesOpResult:
        try:
            data = self._read_igsa_consolidado_rows(file_path)
        except ValueError as exc:
            return SalesOpResult(False, str(exc))
        if not data:
            return SalesOpResult(False, "El Excel IGSA no contiene filas válidas en hoja 'consolidado'.")

        file_hash = self._file_hash(file_path)
        with Session(engine) as session:
            existing = session.exec(
                select(VentaImportLote).where(
                    VentaImportLote.fuente == "igsa",
                    VentaImportLote.archivo_hash == file_hash,
                )
            ).first()
            was_reimport = existing is not None

            rows: list[VentaMensualRaw] = []
            skipped = 0
            first_period = ""
            first_cliente_id = ""
            client_rows = list(
                session.exec(
                    select(Cliente.cliente_id, Cliente.cliente_nombre_comercial, Cliente.cliente_nombre_fiscal, Cliente.cliente_tipo)
                )
            )
            allowed_by_id: dict[str, str] = {}
            allowed_by_name: dict[str, str] = {}
            for cid, ncom, nfis, ctype in client_rows:
                tipo = str(ctype or "").strip().lower()
                if tipo not in SALES_CLIENT_TYPES:
                    continue
                cliente_id_val = str(cid or "").strip()
                if not cliente_id_val:
                    continue
                allowed_by_id[cliente_id_val] = cliente_id_val
                for raw_name in (ncom, nfis):
                    norm_name = self._normalize_search_text(raw_name)
                    if norm_name:
                        allowed_by_name[norm_name] = cliente_id_val
            for item in data:
                year = self._to_int(item.get("anio"))
                month = self._to_int(item.get("mes_numero"))
                if year <= 0 or month < 1 or month > 12:
                    skipped += 1
                    continue
                periodo = f"{year:04d}-{month:02d}"
                if not first_period:
                    first_period = periodo
                cliente_id = self._resolve_igsa_cliente_id(
                    item.get("distribuidor_uuid"),
                    item.get("distribuidor_nombre"),
                    allowed_by_id,
                    allowed_by_name,
                )
                if cliente_id and not first_cliente_id:
                    first_cliente_id = cliente_id

                code = self._normalize_code(item.get("articulo_referencia"))
                articulo_id = str(item.get("articulo_id") or "").strip()
                if self._is_total_row(code) or (not code and not articulo_id):
                    skipped += 1
                    continue

                tipo = self._normalize_igsa_tipo(item.get("tipo"))
                kilos = self._to_float(item.get("kilos"))
                if tipo == "venta":
                    venta_kilos = kilos
                    venta_kilos_sc = 0.0
                elif tipo in {"s/c", "muestras"}:
                    venta_kilos = 0.0
                    venta_kilos_sc = kilos
                else:
                    skipped += 1
                    continue

                rows.append(
                    VentaMensualRaw(
                        raw_id=str(uuid4()),
                        lote_id="",
                        fuente="igsa",
                        cliente_id=cliente_id,
                        periodo=periodo,
                        articulo_codigo_origen=code,
                        articulo_id=articulo_id,
                        articulo_descripcion_origen=str(item.get("articulo_descripcion") or "").strip(),
                        venta_kilos=venta_kilos,
                        venta_kilos_sc=venta_kilos_sc,
                        venta_euros=0.0,
                        payload_json=json.dumps(item, ensure_ascii=False),
                    )
                )

            if not rows:
                return SalesOpResult(False, "No se pudo importar ninguna fila válida.", imported=0, incidencias=skipped)

            # Reemplaza periodos ya importados de IGSA para evitar duplicados
            # cuando se vuelven a importar meses/años (mismo cliente y periodo).
            period_set = {str(r.periodo or "").strip() for r in rows if str(r.periodo or "").strip()}
            for periodo in period_set:
                stmt = select(VentaMensualRaw).where(
                    col(VentaMensualRaw.fuente) == "igsa",
                    col(VentaMensualRaw.periodo) == periodo,
                )
                for old_row in session.exec(stmt):
                    session.delete(old_row)
            if was_reimport:
                old_lotes = list(
                    session.exec(
                        select(VentaImportLote).where(
                            VentaImportLote.fuente == "igsa",
                            VentaImportLote.archivo_hash == file_hash,
                        )
                    )
                )
                for old_lote in old_lotes:
                    session.delete(old_lote)

            lote = VentaImportLote(
                lote_id=str(uuid4()),
                fuente="igsa",
                cliente_id=first_cliente_id,
                periodo=first_period,
                archivo_nombre=file_path.name,
                archivo_hash=file_hash,
                estado="procesado",
            )
            session.add(lote)
            session.flush()
            for row in rows:
                row.lote_id = lote.lote_id
                session.add(row)
            session.commit()
            self._sync_igsa_sales_to_warehouse(session, rows)
            session.commit()

        self._igsa_rows_cache = None
        self._igsa_mtime_ns = None
        msg = "Importación IGSA completada."
        if was_reimport:
            msg = "Reimportación IGSA completada (periodos reemplazados)."
        return SalesOpResult(True, msg, imported=len(rows), incidencias=skipped)

    def parse_igsa_workbook_by_sheets(self, file_path: Path) -> tuple[list[IgsaWorkbookParsedLine], list[str]]:
        return self._igsa_workbook_flow_service.parse_igsa_workbook_by_sheets(file_path)

    def build_igsa_workbook_preview(
        self,
        lines: list[IgsaWorkbookParsedLine],
        cliente_id: str,
    ) -> tuple[list[dict[str, object]], list[str]]:
        return self._igsa_workbook_flow_service.build_igsa_workbook_preview(lines, cliente_id)

    def import_igsa_workbook_lines(
        self,
        lines: list[IgsaWorkbookParsedLine],
        cliente_id: str,
        *,
        force_reimport: bool = False,
    ) -> SalesOpResult:
        return self._igsa_workbook_flow_service.import_igsa_workbook_lines(
            lines,
            cliente_id,
            force_reimport=force_reimport,
            sync_warehouse_callback=self._sync_igsa_sales_to_warehouse,
        )

    def parse_igsa_pdf_files(self, file_paths: list[Path]) -> tuple[list[IgsaPdfParsedLine], list[str]]:
        return self._igsa_pdf_flow_service.parse_igsa_pdf_files(file_paths)

    def import_igsa_pdf_lines(self, lines: list[IgsaPdfParsedLine], cliente_id: str = "") -> SalesOpResult:
        return self._igsa_pdf_flow_service.import_igsa_pdf_lines(
            lines,
            cliente_id,
            sync_warehouse_callback=self._sync_igsa_sales_to_warehouse,
        )

    def import_clientes_excel(
        self,
        file_path: Path,
        *,
        replace_existing: bool = False,
        force_leve_rows: set[int] | None = None,
        preview: ClientesImportPreview | None = None,
    ) -> SalesOpResult:
        try:
            if preview is None:
                preview = self._build_clientes_import_preview(file_path)
            return self._import_clientes_from_preview(file_path, preview, replace_existing=replace_existing)
        except ValueError as exc:
            return SalesOpResult(False, str(exc))
        try:
            parsed_rows, year = self._parse_clientes_workbook(file_path)
        except ValueError as exc:
            return SalesOpResult(False, str(exc))
        if not parsed_rows:
            return SalesOpResult(False, "El Excel de ventas de clientes no contiene filas validas.")

        file_hash = self._file_hash(file_path)
        allowed_leve_rows = {
            int(value)
            for value in (force_leve_rows or set())
            if isinstance(value, int) or str(value).strip().isdigit()
        }
        with Session(engine) as session:
            if not replace_existing:
                existing = session.exec(
                    select(VentaClientesImportLote).where(
                        VentaClientesImportLote.fuente == "clientes",
                        VentaClientesImportLote.archivo_hash == file_hash,
                    )
                ).first()
                if existing is not None:
                    return SalesOpResult(True, "El archivo ya estaba importado.", imported=0, incidencias=0)

            indirect_clients = {
                str(row.cliente_id or "").strip(): row
                for row in session.exec(select(Cliente)).all()
                if self._is_indirect_client(row)
            }
            product_refs = self._build_clientes_product_reference_lookup(session)
            replacement_keys: set[tuple[str, int, str]] = set()
            if replace_existing:
                for item in parsed_rows:
                    cliente = indirect_clients.get(item.cliente_id)
                    if cliente is None:
                        continue
                    product_id = self._resolve_clientes_product_id(item.articulo_id, product_refs)
                    if not product_id:
                        continue
                    replacement_keys.add((item.cliente_id, int(item.anio or year or 0), product_id))
                for cliente_id, anio, articulo_id in replacement_keys:
                    for raw_row in session.exec(
                        select(VentaClientesRaw).where(
                            VentaClientesRaw.anio == anio,
                            VentaClientesRaw.cliente_id == cliente_id,
                            VentaClientesRaw.articulo_id == articulo_id,
                        )
                    ).all():
                        session.delete(raw_row)

            lote_year = next((int(item.anio or 0) for item in parsed_rows if int(item.anio or 0) > 0), year)
            lote = VentaClientesImportLote(
                lote_id=str(uuid4()),
                fuente="clientes",
                anio=lote_year,
                archivo_nombre=file_path.name,
                archivo_hash=file_hash,
                estado="procesado",
            )
            session.add(lote)
            session.flush()

            rows: list[VentaClientesRaw] = []
            skipped = 0
            warnings_count = 0
            warning_messages: list[str] = []

            for item in parsed_rows:
                cliente = indirect_clients.get(item.cliente_id)
                if cliente is None:
                    skipped += 1
                    continue
                product_id = self._resolve_clientes_product_id(item.articulo_id, product_refs)
                if not product_id:
                    skipped += 1
                    continue
                product = session.get(IngredienteIreks, product_id)
                product_weight = float(getattr(product, "articulo_envase_peso", 0.0) or 0.0)
                if product_weight <= 0:
                    skipped += 1
                    warning_messages.append(
                        f"Fila {item.source_row}: sin peso de envase en la ficha del producto IREKS {product_id}."
                    )
                    continue

                row_year = int(item.anio or lote_year or 0)
                precio_kg = self._resolve_tarifa_precio_kg(session, product_id, row_year, envase_peso=product_weight)
                if precio_kg <= 0:
                    warnings_count += 1
                    warning_messages.append(
                        f"Fila {item.source_row}: sin tarifa valida para el año {row_year} del producto IREKS {product_id}; se importara con precio 0."
                    )
                kg_calc = self._to_float(item.unidades) * product_weight
                if kg_calc <= 0:
                    skipped += 1
                    warning_messages.append(
                        f"Fila {item.source_row}: sin cantidad valida en unidades; no se pudo calcular kg con el peso del envase."
                    )
                    continue
                euros = kg_calc * precio_kg if precio_kg > 0 else 0.0

                row = VentaClientesRaw(
                    raw_id=str(uuid4()),
                    lote_id=lote.lote_id,
                    cliente_id=item.cliente_id,
                    anio=row_year,
                    articulo_codigo_origen=item.articulo_id,
                    articulo_id=product_id,
                    articulo_descripcion_origen=item.articulo_descripcion,
                    envase=float(product_weight or 0.0),
                    unidades=float(item.unidades or 0.0),
                    kg=float(kg_calc or 0.0),
                    precio_kg=float(precio_kg or 0.0),
                    euros=float(euros or 0.0),
                    payload_json=json.dumps(
                        {
                            "source_row": item.source_row,
                            "cliente_id": item.cliente_id,
                            "cliente_codigo": item.cliente_codigo,
                            "cliente_nombre": item.cliente_nombre,
                            "articulo_id": item.articulo_id,
                            "articulo_id_interno": product_id,
                            "articulo_codigo_corto": str(
                                getattr(product, "articulo_referencia_corta", "") or getattr(product, "articulo_referencia", "") or ""
                            ).strip(),
                            "articulo_descripcion": item.articulo_descripcion,
                            "anio": row_year,
                            "articulo_envase_peso": product_weight,
                            "unidades": item.unidades,
                            "precio_kg": precio_kg,
                            "euros": euros,
                        },
                        ensure_ascii=False,
                    ),
                )
                rows.append(row)
                session.add(row)

            if not rows:
                session.rollback()
                return SalesOpResult(False, "No se pudo importar ninguna fila valida.", imported=0, incidencias=skipped)

            session.commit()

        message = "Importacion de ventas de clientes completada."
        if replace_existing:
            message = f"{message} Modo correccion aplicado."
        if warnings_count:
            message = f"{message} Con {warnings_count} advertencias de tarifa o calculo."
        return SalesOpResult(
            True,
            message,
            imported=len(rows),
            incidencias=skipped + warnings_count,
            warnings=warning_messages,
        )

    def preview_clientes_excel(self, file_path: Path) -> ClientesImportPreview:
        return self._build_clientes_import_preview(file_path)
        parsed_rows, year = self._parse_clientes_workbook(file_path)
        if not parsed_rows or year <= 0:
            return ClientesImportPreview(
                total_rows=len(parsed_rows),
                valid_rows=0,
                invalid_rows=len(parsed_rows),
                preview_rows=[],
                issues=["No se encontraron filas validas para previsualizar."],
            )

        preview_rows: list[dict[str, object]] = []
        issues: list[str] = []
        valid_rows = 0

        with Session(engine) as session:
            indirect_clients = {
                str(row.cliente_id or "").strip(): row
                for row in session.exec(select(Cliente)).all()
                if self._is_indirect_client(row)
            }
            product_refs = self._build_clientes_product_reference_lookup(session)
            product_ids = sorted({product_id for product_id in product_refs.values() if product_id})
            products = {}
            if product_ids:
                products = {
                    str(row.articulo_id or "").strip(): row
                    for row in session.exec(select(IngredienteIreks).where(col(IngredienteIreks.articulo_id).in_(product_ids))).all()
                    if str(row.articulo_id or "").strip()
                }

            for item in parsed_rows:
                cliente = indirect_clients.get(item.cliente_id)
                if cliente is None:
                    message = f"Cliente no valido o no indirecto ({item.cliente_id})."
                    issues.append(f"Fila {item.source_row}: {message}")
                    preview_rows.append(
                        {
                            "source_row": item.source_row,
                            "cliente_id": item.cliente_id,
                            "cliente_codigo": item.cliente_codigo,
                            "cliente_nombre": item.cliente_nombre,
                            "articulo_codigo": item.articulo_id,
                            "articulo_id": "",
                            "articulo_descripcion": item.articulo_descripcion,
                            "envase": 0.0,
                            "unidades": item.unidades,
                            "kg": 0.0,
                            "precio_kg": 0.0,
                            "euros": 0.0,
                            "status": "error",
                            "issue_text": message,
                            "can_force_import": False,
                        }
                    )
                    continue
                product_id = self._resolve_clientes_product_id(item.articulo_id, product_refs)
                if not product_id:
                    message = f"Articulo sin referencia IREKS para codigo distribuidor {item.articulo_id}."
                    issues.append(f"Fila {item.source_row}: {message}")
                    preview_rows.append(
                        {
                            "source_row": item.source_row,
                            "cliente_id": item.cliente_id,
                            "cliente_codigo": item.cliente_codigo,
                            "cliente_nombre": item.cliente_nombre,
                            "articulo_codigo": item.articulo_id,
                            "articulo_id": "",
                            "articulo_descripcion": item.articulo_descripcion,
                            "envase": 0.0,
                            "unidades": item.unidades,
                            "kg": 0.0,
                            "precio_kg": 0.0,
                            "euros": 0.0,
                            "status": "error",
                            "issue_text": message,
                            "can_force_import": False,
                        }
                    )
                    continue

                product = products.get(product_id)
                product_weight = float(getattr(product, "articulo_envase_peso", 0.0) or 0.0)
                if product_weight <= 0:
                    message = f"Producto sin peso de envase en la ficha IREKS ({product_id})."
                    issues.append(f"Fila {item.source_row}: {message}")
                    preview_rows.append(
                        {
                            "source_row": item.source_row,
                            "cliente_id": item.cliente_id,
                            "cliente_codigo": item.cliente_codigo,
                            "cliente_nombre": item.cliente_nombre,
                            "articulo_codigo": item.articulo_id,
                            "articulo_id": product_id,
                            "articulo_descripcion": str(getattr(product, "articulo_descripcion", "") or item.articulo_descripcion),
                            "envase": 0.0,
                            "unidades": item.unidades,
                            "kg": 0.0,
                            "precio_kg": 0.0,
                            "euros": 0.0,
                            "status": "error",
                            "issue_text": message,
                            "can_force_import": False,
                        }
                    )
                    continue

                row_year = int(item.anio or year or 0)
                precio_kg = self._resolve_tarifa_precio_kg(session, product_id, row_year, envase_peso=product_weight)
                kg_calc = self._to_float(item.unidades) * product_weight
                issue_bits: list[str] = []
                if precio_kg <= 0:
                    issue_bits.append(f"sin tarifa valida para el año {row_year}")
                    issues.append(f"Fila {item.source_row}: sin tarifa valida para el año {row_year} del producto IREKS {product_id}.")
                if kg_calc <= 0:
                    issue_bits.append("sin cantidad valida en unidades")
                    issues.append(f"Fila {item.source_row}: sin cantidad valida en unidades.")
                    preview_rows.append(
                        {
                            "source_row": item.source_row,
                            "cliente_id": item.cliente_id,
                            "cliente_codigo": item.cliente_codigo,
                            "cliente_nombre": item.cliente_nombre,
                            "articulo_codigo": item.articulo_id,
                            "articulo_id": product_id,
                            "articulo_descripcion": str(getattr(product, "articulo_descripcion", "") or item.articulo_descripcion),
                            "envase": product_weight,
                            "unidades": item.unidades,
                            "kg": kg_calc,
                            "precio_kg": precio_kg,
                            "euros": 0.0,
                            "status": "error",
                            "issue_text": "; ".join(issue_bits),
                            "can_force_import": False,
                        }
                    )
                    continue

                euros = kg_calc * precio_kg if precio_kg > 0 else 0.0
                status = "warning" if issue_bits else "ok"
                valid_rows += 1
                preview_rows.append(
                    {
                        "source_row": item.source_row,
                        "cliente_id": item.cliente_id,
                        "cliente_codigo": item.cliente_codigo,
                        "cliente_nombre": item.cliente_nombre,
                        "articulo_codigo": item.articulo_id,
                        "articulo_id": product_id,
                        "articulo_descripcion": str(getattr(product, "articulo_descripcion", "") or item.articulo_descripcion),
                        "envase": product_weight,
                        "unidades": item.unidades,
                        "kg": kg_calc,
                        "precio_kg": precio_kg,
                        "euros": euros,
                        "status": status,
                        "issue_text": "; ".join(issue_bits),
                        "can_force_import": False,
                    }
                )

        return ClientesImportPreview(
            total_rows=len(parsed_rows),
            valid_rows=valid_rows,
            invalid_rows=max(len(parsed_rows) - valid_rows, 0),
            preview_rows=preview_rows,
            issues=issues,
        )

    def _build_clientes_import_preview(self, file_path: Path) -> ClientesImportPreview:
        parsed_rows, year = self._parse_clientes_workbook(file_path)
        if not parsed_rows or year <= 0:
            return ClientesImportPreview(
                total_rows=len(parsed_rows),
                valid_rows=0,
                invalid_rows=len(parsed_rows),
                preview_rows=[],
                issues=["No se encontraron filas validas para previsualizar."],
                anio=year,
                duplicate_rows=0,
                import_rows=[],
            )

        preview_rows: list[dict[str, object]] = []
        import_rows: list[dict[str, object]] = []
        issues: list[str] = []
        valid_rows = 0
        invalid_rows = 0
        duplicate_rows = 0

        def append_row(
            *,
            item: ClientesWorkbookParsedLine,
            cliente_nombre: str,
            cliente_codigo: str,
            articulo_codigo: str,
            articulo_id: str,
            articulo_codigo_corto: str,
            articulo_descripcion: str,
            articulo_label: str,
            envase: float,
            unidades: float,
            kg: float,
            precio_kg: float,
            euros: float,
            status: str,
            issue_text: str,
            can_import: bool,
        ) -> dict[str, object]:
            row = {
                "source_row": item.source_row,
                "anio": int(item.anio or year or 0),
                "cliente_id": item.cliente_id,
                "cliente_codigo": cliente_codigo,
                "cliente_nombre": cliente_nombre,
                "articulo_codigo": articulo_codigo,
                "articulo_id": articulo_id,
                "articulo_codigo_corto": articulo_codigo_corto,
                "articulo_descripcion": articulo_descripcion,
                "articulo_label": articulo_label,
                "envase": float(envase or 0.0),
                "unidades": float(unidades or 0.0),
                "kg": float(kg or 0.0),
                "precio_kg": float(precio_kg or 0.0),
                "euros": float(euros or 0.0),
                "status": status,
                "issue_text": issue_text,
                "can_import": can_import,
            }
            preview_rows.append(row)
            if can_import:
                import_rows.append(row)
            return row

        with Session(engine) as session:
            indirect_clients = {
                str(row.cliente_id or "").strip(): row
                for row in session.exec(select(Cliente)).all()
                if self._is_indirect_client(row)
            }
            product_refs = self._build_clientes_product_reference_lookup(session)
            product_ids = sorted({product_id for product_id in product_refs.values() if product_id})
            products = {}
            if product_ids:
                products = {
                    str(row.articulo_id or "").strip(): row
                    for row in session.exec(select(IngredienteIreks).where(col(IngredienteIreks.articulo_id).in_(product_ids))).all()
                    if str(row.articulo_id or "").strip()
                }

            existing_signatures = self._load_clientes_import_signatures(session)
            seen_signatures = set(existing_signatures)

            for item in parsed_rows:
                cliente = indirect_clients.get(item.cliente_id)
                cliente_nombre = str(item.cliente_nombre or "").strip()
                if not cliente_nombre and cliente is not None:
                    cliente_nombre = str(
                        getattr(cliente, "cliente_nombre_comercial", "") or getattr(cliente, "cliente_nombre_fiscal", "") or ""
                    ).strip()
                if not cliente_nombre:
                    cliente_nombre = item.cliente_id
                cliente_codigo = str(item.cliente_codigo or "").strip()

                if cliente is None:
                    message = f"Cliente no valido o no indirecto ({item.cliente_id})."
                    issues.append(f"Fila {item.source_row} - {cliente_nombre} - {item.cliente_id}: {message}")
                    append_row(
                        item=item,
                        cliente_nombre=cliente_nombre,
                        cliente_codigo=cliente_codigo,
                        articulo_codigo=item.articulo_id,
                        articulo_id="",
                        articulo_codigo_corto="",
                        articulo_descripcion=item.articulo_descripcion,
                        articulo_label=item.articulo_descripcion or item.articulo_id,
                        envase=0.0,
                        unidades=item.unidades,
                        kg=0.0,
                        precio_kg=0.0,
                        euros=0.0,
                        status="error",
                        issue_text=message,
                        can_import=False,
                    )
                    invalid_rows += 1
                    continue

                product_id = self._resolve_clientes_product_id(item.articulo_id, product_refs)
                if not product_id:
                    message = f"Articulo sin referencia IREKS para codigo distribuidor {item.articulo_id}."
                    issues.append(f"Fila {item.source_row} - {cliente_nombre} - {item.articulo_id}: {message}")
                    append_row(
                        item=item,
                        cliente_nombre=cliente_nombre,
                        cliente_codigo=cliente_codigo,
                        articulo_codigo=item.articulo_id,
                        articulo_id="",
                        articulo_codigo_corto="",
                        articulo_descripcion=item.articulo_descripcion,
                        articulo_label=item.articulo_descripcion or item.articulo_id,
                        envase=0.0,
                        unidades=item.unidades,
                        kg=0.0,
                        precio_kg=0.0,
                        euros=0.0,
                        status="error",
                        issue_text=message,
                        can_import=False,
                    )
                    invalid_rows += 1
                    continue

                product = products.get(product_id)
                short_code, product_name, product_label = self._clientes_product_label(product, item.articulo_descripcion)
                product_weight = float(getattr(product, "articulo_envase_peso", 0.0) or 0.0)
                if product_weight <= 0:
                    message = f"Producto sin peso de envase en la ficha IREKS {product_label or product_id}."
                    issues.append(f"Fila {item.source_row} - {cliente_nombre} - {short_code or product_id}: {message}")
                    append_row(
                        item=item,
                        cliente_nombre=cliente_nombre,
                        cliente_codigo=cliente_codigo,
                        articulo_codigo=item.articulo_id,
                        articulo_id=product_id,
                        articulo_codigo_corto=short_code,
                        articulo_descripcion=product_name,
                        articulo_label=product_label or product_id,
                        envase=0.0,
                        unidades=item.unidades,
                        kg=0.0,
                        precio_kg=0.0,
                        euros=0.0,
                        status="error",
                        issue_text=message,
                        can_import=False,
                    )
                    invalid_rows += 1
                    continue

                row_year = int(item.anio or year or 0)
                precio_kg = self._resolve_tarifa_precio_kg(session, product_id, row_year, envase_peso=product_weight)
                kg_calc = self._to_float(item.unidades) * product_weight
                if kg_calc <= 0:
                    message = "sin cantidad valida en unidades; no se pudo calcular kg con el peso del envase."
                    issues.append(f"Fila {item.source_row} - {cliente_nombre} - {short_code or product_id}: {message}")
                    append_row(
                        item=item,
                        cliente_nombre=cliente_nombre,
                        cliente_codigo=cliente_codigo,
                        articulo_codigo=item.articulo_id,
                        articulo_id=product_id,
                        articulo_codigo_corto=short_code,
                        articulo_descripcion=product_name,
                        articulo_label=product_label or product_id,
                        envase=product_weight,
                        unidades=item.unidades,
                        kg=0.0,
                        precio_kg=precio_kg,
                        euros=0.0,
                        status="error",
                        issue_text=message,
                        can_import=False,
                    )
                    invalid_rows += 1
                    continue

                euros = kg_calc * precio_kg if precio_kg > 0 else 0.0
                status = "warning" if precio_kg <= 0 else "ok"
                issue_text = ""
                if status == "warning":
                    issue_text = (
                        f"sin tarifa valida para el ano {row_year} del producto IREKS {product_label or product_id}; "
                        "se importara con precio 0."
                    )

                signature = self._clientes_row_signature(
                    item.cliente_id,
                    row_year,
                    product_id,
                    item.unidades,
                    product_weight,
                    precio_kg,
                    euros,
                )
                if signature in seen_signatures:
                    duplicate_rows += 1
                    issues.append(
                        f"Fila {item.source_row} - {cliente_nombre} - {short_code or item.articulo_id}: "
                        "fila duplicada exacta respecto a una importacion existente; omitida."
                    )
                    continue
                seen_signatures.add(signature)

                append_row(
                    item=item,
                    cliente_nombre=cliente_nombre,
                    cliente_codigo=cliente_codigo,
                    articulo_codigo=item.articulo_id,
                    articulo_id=product_id,
                    articulo_codigo_corto=short_code,
                    articulo_descripcion=product_name,
                    articulo_label=product_label or product_id,
                    envase=product_weight,
                    unidades=item.unidades,
                    kg=kg_calc,
                    precio_kg=precio_kg,
                    euros=euros,
                    status=status,
                    issue_text=issue_text,
                    can_import=True,
                )
                valid_rows += 1
                if issue_text:
                    issues.append(
                        f"Fila {item.source_row} - {cliente_nombre} - {short_code or product_id}: {issue_text}"
                    )

        return ClientesImportPreview(
            total_rows=len(parsed_rows),
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            preview_rows=preview_rows,
            issues=issues,
            anio=year,
            duplicate_rows=duplicate_rows,
            import_rows=import_rows,
        )

    def _import_clientes_from_preview(
        self,
        file_path: Path,
        preview: ClientesImportPreview,
        *,
        replace_existing: bool = False,
    ) -> SalesOpResult:
        file_hash = self._file_hash(file_path)
        preview_rows = [
            dict(row)
            for row in list(getattr(preview, "import_rows", []) or [])
            if str(row.get("status") or "").strip().lower() in {"ok", "warning"} or bool(row.get("can_import"))
        ]
        issue_lines = [str(item).strip() for item in list(getattr(preview, "issues", []) or []) if str(item).strip()]
        if not preview_rows:
            return SalesOpResult(
                False,
                "No se pudo importar ninguna fila valida.",
                imported=0,
                incidencias=int(getattr(preview, "invalid_rows", 0) or 0) + int(getattr(preview, "duplicate_rows", 0) or 0),
                warnings=issue_lines,
            )

        lote_year = int(getattr(preview, "anio", 0) or 0)
        if lote_year <= 0:
            lote_year = next((int(item.get("anio") or 0) for item in preview_rows if int(item.get("anio") or 0) > 0), 0)
        warning_rows = sum(1 for row in preview_rows if str(row.get("status") or "").strip().lower() == "warning")
        omitted = int(getattr(preview, "invalid_rows", 0) or 0) + int(getattr(preview, "duplicate_rows", 0) or 0)

        with Session(engine) as session:
            if not replace_existing:
                existing = session.exec(
                    select(VentaClientesImportLote).where(
                        VentaClientesImportLote.fuente == "clientes",
                        VentaClientesImportLote.archivo_hash == file_hash,
                    )
                ).first()
                if existing is not None:
                    return SalesOpResult(True, "El archivo ya estaba importado.", imported=0, incidencias=0)

            replacement_keys: set[tuple[str, int, str]] = set()
            if replace_existing:
                for item in preview_rows:
                    cliente_id = str(item.get("cliente_id") or "").strip()
                    articulo_id = str(item.get("articulo_id") or "").strip()
                    anio = int(item.get("anio") or lote_year or 0)
                    if not cliente_id or not articulo_id or anio <= 0:
                        continue
                    replacement_keys.add((cliente_id, anio, articulo_id))
                for cliente_id, anio, articulo_id in replacement_keys:
                    for raw_row in session.exec(
                        select(VentaClientesRaw).where(
                            VentaClientesRaw.anio == anio,
                            VentaClientesRaw.cliente_id == cliente_id,
                            VentaClientesRaw.articulo_id == articulo_id,
                        )
                    ).all():
                        session.delete(raw_row)

            lote = VentaClientesImportLote(
                lote_id=str(uuid4()),
                fuente="clientes",
                anio=lote_year,
                archivo_nombre=file_path.name,
                archivo_hash=file_hash,
                estado="procesado",
            )
            session.add(lote)
            session.flush()

            rows: list[VentaClientesRaw] = []
            for item in preview_rows:
                status = str(item.get("status") or "").strip().lower()
                if status not in {"ok", "warning"}:
                    continue
                row_year = int(item.get("anio") or lote_year or 0)
                row = VentaClientesRaw(
                    raw_id=str(uuid4()),
                    lote_id=lote.lote_id,
                    cliente_id=str(item.get("cliente_id") or "").strip(),
                    anio=row_year,
                    articulo_codigo_origen=str(item.get("articulo_codigo") or "").strip(),
                    articulo_id=str(item.get("articulo_id") or "").strip(),
                    articulo_descripcion_origen=str(item.get("articulo_descripcion") or "").strip(),
                    envase=float(item.get("envase") or 0.0),
                    unidades=float(item.get("unidades") or 0.0),
                    kg=float(item.get("kg") or 0.0),
                    precio_kg=float(item.get("precio_kg") or 0.0),
                    euros=float(item.get("euros") or 0.0),
                    payload_json=json.dumps(
                        {
                            "source_row": item.get("source_row"),
                            "cliente_id": str(item.get("cliente_id") or "").strip(),
                            "cliente_codigo": str(item.get("cliente_codigo") or "").strip(),
                            "cliente_nombre": str(item.get("cliente_nombre") or "").strip(),
                            "articulo_id": str(item.get("articulo_codigo") or "").strip(),
                            "articulo_id_interno": str(item.get("articulo_id") or "").strip(),
                            "articulo_codigo_corto": str(item.get("articulo_codigo_corto") or "").strip(),
                            "articulo_descripcion": str(item.get("articulo_descripcion") or "").strip(),
                            "anio": row_year,
                            "articulo_envase_peso": float(item.get("envase") or 0.0),
                            "unidades": float(item.get("unidades") or 0.0),
                            "precio_kg": float(item.get("precio_kg") or 0.0),
                            "euros": float(item.get("euros") or 0.0),
                        },
                        ensure_ascii=False,
                    ),
                )
                rows.append(row)
                session.add(row)

            if not rows:
                session.rollback()
                return SalesOpResult(
                    False,
                    "No se pudo importar ninguna fila valida.",
                    imported=0,
                    incidencias=int(getattr(preview, "invalid_rows", 0) or 0) + int(getattr(preview, "duplicate_rows", 0) or 0),
                    warnings=issue_lines,
                )

            session.commit()

        message = "Importacion de ventas de clientes completada."
        if replace_existing:
            message = f"{message} Modo correccion aplicado."
        if warning_rows:
            message = f"{message} Con {warning_rows} advertencias de tarifa."
        if omitted:
            message = f"{message} Se omitieron {omitted} filas no importables."
        return SalesOpResult(True, message, imported=len(rows), incidencias=len(issue_lines), warnings=issue_lines)

    def _clientes_row_signature(
        self,
        cliente_id: object,
        anio: object,
        articulo_id: object,
        unidades: object,
        envase: object,
        precio_kg: object,
        euros: object,
    ) -> tuple[str, int, str, float, float, float, float]:
        return (
            str(cliente_id or "").strip(),
            self._to_int(anio),
            str(articulo_id or "").strip(),
            round(self._to_float(unidades), 6),
            round(self._to_float(envase), 6),
            round(self._to_float(precio_kg), 6),
            round(self._to_float(euros), 6),
        )

    def _load_clientes_import_signatures(self, session: Session) -> set[tuple[str, int, str, float, float, float, float]]:
        signatures: set[tuple[str, int, str, float, float, float, float]] = set()
        rows = list(session.exec(select(VentaClientesRaw)).all())
        for row in rows:
            payload = self._safe_json_dict(str(getattr(row, "payload_json", "") or ""))
            cliente_id = str(payload.get("cliente_id") or getattr(row, "cliente_id", "") or "").strip()
            anio = self._to_int(payload.get("anio") or getattr(row, "anio", 0))
            articulo_id = str(payload.get("articulo_id_interno") or getattr(row, "articulo_id", "") or "").strip()
            unidades = payload.get("unidades", getattr(row, "unidades", 0.0))
            envase = payload.get("articulo_envase_peso", getattr(row, "envase", 0.0))
            precio_kg = payload.get("precio_kg", getattr(row, "precio_kg", 0.0))
            euros = payload.get("euros", getattr(row, "euros", 0.0))
            signatures.add(self._clientes_row_signature(cliente_id, anio, articulo_id, unidades, envase, precio_kg, euros))
        return signatures

    def _clientes_product_label(
        self,
        product: IngredienteIreks | None,
        fallback_descripcion: object = "",
    ) -> tuple[str, str, str]:
        short_code = ""
        product_name = ""
        if product is not None:
            short_code = str(
                getattr(product, "articulo_referencia_corta", "") or getattr(product, "articulo_referencia", "") or ""
            ).strip()
            product_name = str(getattr(product, "articulo_descripcion", "") or "").strip()
        if not product_name:
            product_name = str(fallback_descripcion or "").strip()
        if not product_name:
            product_name = short_code
        product_label = f"{short_code} - {product_name}" if short_code else product_name
        return short_code, product_name, product_label

    def get_clientes_import_warning_details(self, archivo_nombre: str) -> list[str]:
        clean_name = str(archivo_nombre or "").strip()
        if not clean_name:
            return []

        with Session(engine) as session:
            lote = session.exec(
                select(VentaClientesImportLote)
                .where(
                    VentaClientesImportLote.fuente == "clientes",
                    VentaClientesImportLote.archivo_nombre == clean_name,
                )
                .order_by(VentaClientesImportLote.creado_en.desc())
            ).first()
            if lote is None:
                return []

            rows = list(
                session.exec(
                    select(VentaClientesRaw).where(VentaClientesRaw.lote_id == lote.lote_id)
                ).all()
            )
            if not rows:
                return []

            product_ids = {
                str(self._safe_json_dict(row.payload_json).get("articulo_id_interno", "") or row.articulo_id).strip()
                for row in rows
                if str(self._safe_json_dict(row.payload_json).get("articulo_id_interno", "") or row.articulo_id).strip()
            }
            product_labels = {
                str(product.articulo_id): (
                    str(getattr(product, "articulo_referencia_corta", "") or getattr(product, "articulo_referencia", "") or "").strip(),
                    str(getattr(product, "articulo_descripcion", "") or "").strip(),
                )
                for product in session.exec(select(IngredienteIreks).where(IngredienteIreks.articulo_id.in_(list(product_ids)))).all()
            }

            warnings: list[str] = []
            for fallback_row_number, row in enumerate(rows, start=1):
                payload = self._safe_json_dict(row.payload_json)
                source_row = int(self._to_float(payload.get("source_row", 0)) or 0) or fallback_row_number
                cliente_nombre = str(payload.get("cliente_nombre", "") or "").strip() or row.cliente_id
                original_kg = self._to_float(payload.get("kg", row.kg))
                envase = self._to_float(row.envase)
                unidades = self._to_float(row.unidades)
                kg_calc = envase * unidades
                product_id = str(payload.get("articulo_id_interno", "") or row.articulo_id).strip()
                product_code, product_name = product_labels.get(product_id, ("", ""))
                product_code = str(payload.get("articulo_codigo_corto", "") or product_code or "").strip()
                product_name = product_name or str(payload.get("articulo_descripcion", "") or "").strip() or product_id
                product_label = f"{product_code} - {product_name}" if product_code else product_name
                if row.precio_kg <= 0:
                    prefix = f"Fila {source_row}" if source_row else "Fila desconocida"
                    warnings.append(
                        f"{prefix} - {cliente_nombre} - {product_code}: sin tarifa valida para el producto IREKS {product_label}."
                    )
                if original_kg > 0 and abs(kg_calc - original_kg) > 0.01:
                    prefix = f"Fila {source_row}" if source_row else "Fila desconocida"
                    warnings.append(
                        f"{prefix} - {cliente_nombre} - {product_code}: kg calculado ({kg_calc:.3f}) difiere del archivo ({original_kg:.3f}); se usara el valor del archivo."
                    )
            return warnings

    def list_clientes_import_lotes(self, limit: int | None = None) -> list[ClientesImportLoteRow]:
        safe_limit = 200 if limit is None else max(1, min(int(limit), 500))
        with Session(engine) as session:
            lotes = list(
                session.exec(
                    select(VentaClientesImportLote)
                    .where(VentaClientesImportLote.fuente == "clientes")
                    .order_by(VentaClientesImportLote.creado_en.desc())
                    .limit(safe_limit)
                ).all()
            )
            if not lotes:
                return []
            lote_ids = [str(lote.lote_id or "").strip() for lote in lotes if str(lote.lote_id or "").strip()]
            row_counts: dict[str, int] = {}
            if lote_ids:
                count_rows = session.exec(
                    select(VentaClientesRaw.lote_id, func.count(VentaClientesRaw.raw_id))
                    .where(VentaClientesRaw.lote_id.in_(lote_ids))
                    .group_by(VentaClientesRaw.lote_id)
                ).all()
                row_counts = {str(row[0] or "").strip(): int(row[1] or 0) for row in count_rows}
        return [
            ClientesImportLoteRow(
                lote_id=str(lote.lote_id or ""),
                creado_en=lote.creado_en.isoformat(timespec="seconds") if getattr(lote, "creado_en", None) else "",
                archivo_nombre=str(lote.archivo_nombre or ""),
                anio=int(lote.anio or 0),
                estado=str(lote.estado or ""),
                archivo_hash=str(lote.archivo_hash or ""),
                filas=int(row_counts.get(str(lote.lote_id or "").strip(), 0)),
            )
            for lote in lotes
        ]

    def delete_clientes_import_lote(self, lote_id: str) -> SalesOpResult:
        clean_lote_id = str(lote_id or "").strip()
        if not clean_lote_id:
            return SalesOpResult(False, "No se indicó un lote de importación válido.")

        with Session(engine) as session:
            lote = session.get(VentaClientesImportLote, clean_lote_id)
            if lote is None or str(getattr(lote, "fuente", "") or "") != "clientes":
                return SalesOpResult(False, "No se encontró el lote de importación de clientes.")
            rows = list(session.exec(select(VentaClientesRaw).where(VentaClientesRaw.lote_id == clean_lote_id)).all())
            for row in rows:
                session.delete(row)
            session.delete(lote)
            session.commit()

        return SalesOpResult(
            True,
            f"Lote de clientes revertido: {str(getattr(lote, 'archivo_nombre', '') or clean_lote_id)}.",
            imported=len(rows),
            incidencias=0,
        )

    def delete_all_clientes_imports(self) -> SalesOpResult:
        with Session(engine) as session:
            lotes = list(
                session.exec(
                    select(VentaClientesImportLote).where(VentaClientesImportLote.fuente == "clientes")
                ).all()
            )
            if not lotes:
                return SalesOpResult(True, "No hay importaciones de clientes para eliminar.", imported=0, incidencias=0)
            lote_ids = [str(lote.lote_id or "").strip() for lote in lotes if str(lote.lote_id or "").strip()]
            rows = list(
                session.exec(select(VentaClientesRaw).where(VentaClientesRaw.lote_id.in_(lote_ids))).all()
            )
            for row in rows:
                session.delete(row)
            for lote in lotes:
                session.delete(lote)
            session.commit()

        return SalesOpResult(
            True,
            f"Importaciones de clientes eliminadas: {len(lotes)} lotes y {len(rows)} filas.",
            imported=len(rows),
            incidencias=0,
        )

    def rebuild_igsa_warehouse_movements(self, periodo: str = "") -> SalesOpResult:
        clean_periodo = str(periodo or "").strip()
        if clean_periodo and not re.fullmatch(r"\d{4}-\d{2}", clean_periodo):
            return SalesOpResult(False, "Periodo inválido. Usa formato AAAA-MM o vacío para todos.")

        with Session(engine) as session:
            stmt = select(VentaMensualRaw).where(col(VentaMensualRaw.fuente).in_(["igsa", "igsa_pdf"]))
            if clean_periodo:
                stmt = stmt.where(col(VentaMensualRaw.periodo) == clean_periodo)
            rows = list(session.exec(stmt))
            if not rows:
                return SalesOpResult(True, "No hay filas IGSA para regenerar.", imported=0, incidencias=0)
            self._sync_igsa_sales_to_warehouse(session, rows)
            session.commit()
        return SalesOpResult(
            True,
            f"Regeneración IGSA completada{' para ' + clean_periodo if clean_periodo else ''}.",
            imported=len(rows),
            incidencias=0,
        )

    def list_years(self) -> list[int]:
        return self._sales_annual_comparison_service.list_years()

    def list_years_igsa(self) -> list[int]:
        return self._sales_annual_comparison_service.list_years_igsa()

    def list_years_clientes(self) -> list[int]:
        return self._sales_annual_comparison_service.list_years_clientes()

    def list_filter_clients(self) -> list[Cliente]:
        return self._sales_annual_comparison_service.list_filter_clients()

    def list_filter_clients_indirect(self) -> list[Cliente]:
        return self._sales_annual_comparison_service.list_filter_clients_indirect()

    def list_filter_products(self) -> list[IngredienteIreks]:
        return self._sales_annual_comparison_service.list_filter_products()

    def list_filter_manufacturers(self) -> list[Fabricante]:
        return self._sales_annual_comparison_service.list_filter_manufacturers()

    def list_filter_manufacturers_igsa(self) -> list[Fabricante]:
        return self._sales_annual_comparison_service.list_filter_manufacturers_igsa()

    def list_filter_families(self, fabricante_id: str = "") -> list[Familia]:
        return self._sales_annual_comparison_service.list_filter_families(fabricante_id)

    def list_filter_families_igsa(self, fabricante_id: str = "") -> list[Familia]:
        return self._sales_annual_comparison_service.list_filter_families_igsa(fabricante_id)

    def list_filter_subfamilies(self, familia_id: str = "") -> list[Subfamilia]:
        return self._sales_annual_comparison_service.list_filter_subfamilies(familia_id)

    def list_filter_subfamilies_igsa(self, familia_id: str = "") -> list[Subfamilia]:
        return self._sales_annual_comparison_service.list_filter_subfamilies_igsa(familia_id)

    def listar_resumen_anual_igsa(
        self,
        year: int,
        month: int = 0,
        acumulado: bool = False,
        producto_texto: str = "",
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
    ) -> list[SalesComparisonRow]:
        return self._sales_annual_comparison_service.listar_resumen_anual_igsa(
            year=year,
            month=month,
            acumulado=acumulado,
            producto_texto=producto_texto,
            fabricante_id=fabricante_id,
            familia_id=familia_id,
            subfamilia_id=subfamilia_id,
        )

    def listar_resumen_anual(
        self,
        year: int,
        month: int = 0,
        acumulado: bool = False,
        cliente_id: str = "",
        articulo_id: str = "",
        producto_texto: str = "",
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
    ) -> list[SalesComparisonRow]:
        return self._sales_annual_comparison_service.listar_resumen_anual(
            year=year,
            month=month,
            acumulado=acumulado,
            cliente_id=cliente_id,
            articulo_id=articulo_id,
            producto_texto=producto_texto,
            fabricante_id=fabricante_id,
            familia_id=familia_id,
            subfamilia_id=subfamilia_id,
        )

    def listar_resumen_anual_clientes(
        self,
        year: int,
        cliente_id: str = "",
        producto_texto: str = "",
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
    ):
        return self._sales_annual_comparison_service.listar_resumen_anual_clientes(
            year=year,
            cliente_id=cliente_id,
            producto_texto=producto_texto,
            fabricante_id=fabricante_id,
            familia_id=familia_id,
            subfamilia_id=subfamilia_id,
        )

    def _parse_clientes_workbook(self, file_path: Path) -> tuple[list[ClientesWorkbookParsedLine], int]:
        try:
            workbook = load_workbook(file_path, read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"No se pudo abrir el Excel de ventas de clientes: {exc}") from exc
        if not workbook.sheetnames:
            raise ValueError("El Excel de ventas de clientes no contiene hojas.")

        sheet = workbook[workbook.sheetnames[0]]
        rows = list(sheet.iter_rows(values_only=True))
        if len(rows) < 2:
            return [], 0

        header = [str(cell or "").strip().lower() for cell in rows[0]]
        year = 0
        for cell in rows[0]:
            if isinstance(cell, int) and 1900 <= cell <= 2100:
                year = int(cell)
                break
            if isinstance(cell, float) and cell.is_integer() and 1900 <= int(cell) <= 2100:
                year = int(cell)
                break
            text = str(cell or "").strip()
            if text.isdigit() and 1900 <= int(text) <= 2100:
                year = int(text)
                break
        if year <= 0:
            match = re.search(r"(19|20)\d{2}", str(sheet.title or ""))
            if match:
                year = int(match.group(0))
        if year <= 0:
            raise ValueError("No se pudo determinar el año del Excel de ventas de clientes.")

        def find_index(*names: str) -> int:
            norm_names = {self._normalize_key(name) for name in names}
            for idx, cell in enumerate(header):
                if self._normalize_key(cell) in norm_names:
                    return idx
            return -1

        idx_anio = find_index("año", "anio", "year")
        idx_cliente_id = find_index("cliente_id")
        idx_cliente_codigo = find_index("codigo")
        idx_cliente_nombre = find_index("cliente")
        idx_articulo = find_index("articulo")
        idx_descripcion = find_index("descripcion art.")
        idx_unidades = find_index("unidades")
        if idx_unidades < 0:
            idx_unidades = find_index(str(year))
        if min(idx_anio, idx_cliente_id, idx_cliente_codigo, idx_cliente_nombre, idx_articulo, idx_descripcion, idx_unidades) < 0:
            raise ValueError("El Excel de ventas de clientes no tiene el formato esperado.")

        parsed_rows: list[ClientesWorkbookParsedLine] = []
        for source_row, row in enumerate(rows[1:], start=2):
            row_year = self._to_int(row[idx_anio])
            cliente_id = str(row[idx_cliente_id] or "").strip()
            articulo_id = self._normalize_code(row[idx_articulo])
            unidades = self._to_float(row[idx_unidades])
            if row_year <= 0 or not cliente_id or not articulo_id or unidades <= 0:
                continue
            cliente_nombre = str(row[idx_cliente_nombre] or "").strip()
            cliente_codigo = str(row[idx_cliente_codigo] or "").strip()
            articulo_descripcion = str(row[idx_descripcion] or "").strip()
            parsed_rows.append(
                ClientesWorkbookParsedLine(
                    source_row=source_row,
                    anio=row_year,
                    cliente_id=cliente_id,
                    cliente_codigo=cliente_codigo,
                    cliente_nombre=cliente_nombre,
                    articulo_id=articulo_id,
                    articulo_descripcion=articulo_descripcion,
                    unidades=unidades,
                )
            )
        return parsed_rows, parsed_rows[0].anio if parsed_rows else year

    def _resolve_tarifa_precio_kg(
        self,
        session: Session,
        articulo_id: str,
        year: int,
        *,
        envase_peso: float = 0.0,
    ) -> float:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id or year <= 0:
            return 0.0
        tarifa = session.exec(
            select(TarifaPrecioIreks)
            .where(TarifaPrecioIreks.articulo_id == clean_articulo_id, TarifaPrecioIreks.tarifa_ano == year)
            .order_by(col(TarifaPrecioIreks.id).desc())
        ).first()
        if tarifa is None:
            tarifa = session.exec(
                select(TarifaPrecioIreks)
                .where(TarifaPrecioIreks.articulo_id == clean_articulo_id, TarifaPrecioIreks.tarifa_ano <= year)
                .order_by(col(TarifaPrecioIreks.tarifa_ano).desc(), col(TarifaPrecioIreks.id).desc())
            ).first()
        if tarifa is None:
            tarifa = session.exec(
                select(TarifaPrecioIreks)
                .where(TarifaPrecioIreks.articulo_id == clean_articulo_id)
                .order_by(col(TarifaPrecioIreks.tarifa_ano).desc(), col(TarifaPrecioIreks.id).desc())
            ).first()
        if tarifa is None:
            return 0.0
        precio_envase = float(getattr(tarifa, "precio_distribuidor", 0.0) or 0.0)
        if precio_envase <= 0:
            precio_envase = float(getattr(tarifa, "precio_fabricante", 0.0) or 0.0)
        peso = float(envase_peso or 0.0)
        if precio_envase <= 0:
            return 0.0
        if peso <= 0:
            return precio_envase
        return precio_envase / peso

    def _build_clientes_product_reference_lookup(self, session: Session) -> dict[str, str]:
        lookup: dict[str, str] = {}
        rows = list(session.exec(select(ReferenciaDistribuidor)))
        for row in rows:
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            reference = str(getattr(row, "articulo_referencia_distribuidor", "") or "").strip()
            if not articulo_id or not reference:
                continue
            for candidate in self._code_candidates(reference):
                lookup[candidate] = articulo_id
        return lookup

    def _resolve_clientes_product_id(self, articulo_code: object, lookup: dict[str, str]) -> str:
        for candidate in self._code_candidates(articulo_code):
            product_id = lookup.get(candidate, "")
            if product_id:
                return product_id
        return ""

    def _is_indirect_client(self, client: Cliente) -> bool:
        tipo = str(getattr(client, "cliente_tipo", "") or "").strip().lower()
        return tipo not in SALES_CLIENT_EXCLUDED_TYPES

    def _read_json(self, file_path: Path):
        try:
            raw = self._decode_text(file_path.read_bytes())
            return json.loads(raw)
        except UnicodeDecodeError as exc:
            raise ValueError("No se pudo leer el JSON con una codificacion soportada.") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"El archivo seleccionado no contiene JSON valido: linea {exc.lineno}, columna {exc.colno}.") from exc

    def _decode_text(self, content: bytes) -> str:
        if content.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
            return content.decode("utf-32")
        if content.startswith((b"\xff\xfe", b"\xfe\xff")):
            return content.decode("utf-16")
        if content.startswith(b"\xef\xbb\xbf"):
            return content.decode("utf-8-sig")

        sample = content[:200]
        even_nulls = sample[0::2].count(0)
        odd_nulls = sample[1::2].count(0)
        if odd_nulls > even_nulls and odd_nulls >= max(2, len(sample) // 6):
            return content.decode("utf-16-le")
        if even_nulls > odd_nulls and even_nulls >= max(2, len(sample) // 6):
            return content.decode("utf-16-be")

        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8-sig")

    def _file_hash(self, file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _get_any(self, data: dict, *keys: str):
        for key in keys:
            if key in data:
                return data[key]
        normalized = {self._normalize_key(k): v for k, v in data.items()}
        for key in keys:
            norm = self._normalize_key(key)
            if norm in normalized:
                return normalized[norm]
        return None

    def _normalize_key(self, value) -> str:
        text = str(value or "").strip().lower()
        normalized = unicodedata.normalize("NFD", text)
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return re.sub(r"[^a-z0-9]+", "", normalized)

    def _normalize_search_text(self, value) -> str:
        return normalize_search_text(value)

    def _normalize_code(self, value) -> str:
        text = str(value or "").strip().upper()
        if not text:
            return ""
        if re.fullmatch(r"\d+(\.0+)?", text):
            return str(int(float(text)))
        return text

    def _code_candidates(self, code: object) -> list[str]:
        base = self._normalize_code(code)
        clean = re.sub(r"\s+", "", str(base or "").upper())
        if not clean:
            return []
        out = [clean]
        if clean.startswith("D") and clean[1:].isdigit():
            out.append(clean[1:])
        elif clean.isdigit():
            out.append(f"D{clean}")
        return list(dict.fromkeys(out))

    def _is_total_row(self, code: str) -> bool:
        return self._normalize_code(code) == "TOTAL"

    def _to_int(self, value) -> int:
        try:
            txt = str(value or "").strip()
            if not txt:
                return 0
            return int(float(txt.replace(",", ".")))
        except Exception:
            return 0

    def _to_float(self, value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            try:
                if isinstance(value, float) and math.isnan(value):
                    return 0.0
                return float(value)
            except Exception:
                return 0.0
        text = str(value).strip()
        if not text:
            return 0.0
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?", text)
        if match is None:
            return 0.0
        try:
            return float(match.group(0).replace(",", "."))
        except Exception:
            return 0.0

    def _parse_month(self, value) -> int:
        text = str(value or "").strip().lower()
        if not text:
            return 0
        normalized = unicodedata.normalize("NFD", text)
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        normalized = normalized.replace(".", "")
        month_map = {
            "enero": 1,
            "ene": 1,
            "febrero": 2,
            "feb": 2,
            "marzo": 3,
            "mar": 3,
            "abril": 4,
            "abr": 4,
            "mayo": 5,
            "may": 5,
            "junio": 6,
            "jun": 6,
            "julio": 7,
            "jul": 7,
            "agosto": 8,
            "ago": 8,
            "septiembre": 9,
            "setiembre": 9,
            "sep": 9,
            "set": 9,
            "octubre": 10,
            "oct": 10,
            "noviembre": 11,
            "nov": 11,
            "diciembre": 12,
            "dic": 12,
        }
        if normalized in month_map:
            return month_map[normalized]
        return self._to_int(normalized)

    def _normalize_igsa_tipo(self, value) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return ""
        normalized = unicodedata.normalize("NFD", raw)
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        normalized = normalized.replace(" ", "")
        if normalized in {"venta", "ventas"}:
            return "venta"
        if normalized in {"s/c", "c/s", "sc"}:
            return "s/c"
        if normalized in {"muestra", "muestras"}:
            return "muestras"
        if normalized in {"promocion", "promociones"}:
            return "promociones"
        return normalized

    def _resolve_igsa_cliente_id(
        self,
        distribuidor_uuid: object,
        distribuidor_nombre: object,
        allowed_by_id: dict[str, str],
        allowed_by_name: dict[str, str],
    ) -> str:
        raw_id = str(distribuidor_uuid or "").strip()
        if raw_id and raw_id in allowed_by_id:
            return raw_id
        raw_name = self._normalize_search_text(distribuidor_nombre)
        if raw_name and raw_name in allowed_by_name:
            return allowed_by_name[raw_name]
        return raw_id

    def _normalize_ireks_json_payload(self, data: object) -> tuple[list[dict[str, object]], int, int, str]:
        default_year = 0
        default_month = 0
        default_cliente_id = ""
        rows_source: list[object] | None = None

        if isinstance(data, list):
            rows_source = data
        elif isinstance(data, dict):
            for key in ("articulos", "items", "filas", "rows", "lineas"):
                value = data.get(key)
                if isinstance(value, list):
                    rows_source = value
                    break
            cliente = data.get("cliente")
            if isinstance(cliente, dict):
                default_cliente_id = str(self._get_any(cliente, "id", "cliente_id", "Cliente_ID", "ClienteId") or "").strip()
            if not default_cliente_id:
                default_cliente_id = str(
                    self._get_any(data, "cliente_id", "Cliente_ID", "ClienteId", "distribuidor_uuid") or ""
                ).strip()
            periodo = data.get("periodo")
            if isinstance(periodo, dict):
                default_year = self._to_int(self._get_any(periodo, "anio", "año", "year"))
                default_month = self._parse_month(self._get_any(periodo, "mes", "month"))
                if default_month < 1:
                    default_month = self._to_int(self._get_any(periodo, "mes_numero", "numero_mes"))
            elif isinstance(periodo, str):
                raw_periodo = str(periodo or "").strip()
                match = re.fullmatch(r"(\d{4})[-/](\d{1,2})", raw_periodo)
                if match is not None:
                    default_year = self._to_int(match.group(1))
                    default_month = self._to_int(match.group(2))

        if rows_source is None:
            return [], default_year, default_month, default_cliente_id
        return [item for item in rows_source if isinstance(item, dict)], default_year, default_month, default_cliente_id

    def _sync_igsa_sales_to_warehouse(self, session: Session, raw_rows: list[VentaMensualRaw]) -> None:
        article_ids = sorted(
            {
                str(getattr(r, "articulo_id", "") or "").strip()
                for r in raw_rows
                if str(getattr(r, "articulo_id", "") or "").strip()
            }
        )
        product_weight_by_id: dict[str, float] = {}
        if article_ids:
            products = list(
                session.exec(
                    select(IngredienteIreks).where(col(IngredienteIreks.articulo_id).in_(article_ids))
                )
            )
            for product in products:
                aid = str(getattr(product, "articulo_id", "") or "").strip()
                if not aid:
                    continue
                weight_total = float(getattr(product, "articulo_envase_peso_total", 0.0) or 0.0)
                weight_unit = float(getattr(product, "articulo_envase_peso", 0.0) or 0.0)
                product_weight_by_id[aid] = weight_total if weight_total > 0 else weight_unit

        # Caducidad por articulo+lote desde entradas de almacen ya registradas.
        expiry_by_key: dict[tuple[str, str, str], date | None] = {}
        if article_ids:
            entry_rows = list(
                session.exec(
                    select(AlmacenMovimiento).where(
                        col(AlmacenMovimiento.articulo_id).in_(article_ids),
                        col(AlmacenMovimiento.cantidad) > 0,
                    )
                )
            )
            for mov in entry_rows:
                almacen_id = str(getattr(mov, "almacen_id", "") or "").strip()
                articulo_id = str(getattr(mov, "articulo_id", "") or "").strip()
                lote = str(getattr(mov, "articulo_lote", "") or "").strip().upper()
                cad = getattr(mov, "articulo_caducidad", None)
                if not almacen_id or not articulo_id or not lote or cad is None:
                    continue
                key = (almacen_id, articulo_id, lote)
                prev = expiry_by_key.get(key)
                if prev is None or cad > prev:
                    expiry_by_key[key] = cad

        period_set = {str(r.periodo or "").strip() for r in raw_rows if str(r.periodo or "").strip()}
        for periodo in period_set:
            pedido_numero = f"IGSA-{periodo}"
            delete_stmt = select(AlmacenMovimiento).where(
                col(AlmacenMovimiento.pedido_numero) == pedido_numero
            )
            for mov in session.exec(delete_stmt):
                if str(getattr(mov, "albaran_item_id", "") or "").startswith("igsa:"):
                    session.delete(mov)

        for row in raw_rows:
            periodo = str(row.periodo or "").strip()
            almacen_id = str(row.cliente_id or "").strip()
            articulo_id = str(row.articulo_id or "").strip()
            if not periodo or not almacen_id or not articulo_id:
                continue

            payload = self._safe_json_dict(row.payload_json)
            cantidad_unidades = self._to_float(payload.get("cantidad_documento"))
            kilos_total = float(row.venta_kilos or 0.0) + float(row.venta_kilos_sc or 0.0)
            if cantidad_unidades <= 0 and kilos_total > 0:
                envase_peso = float(product_weight_by_id.get(articulo_id, 0.0) or 0.0)
                if envase_peso <= 0:
                    envase_peso = self._to_float(payload.get("envase_peso_documento"))
                if envase_peso <= 0:
                    envase_peso = self._to_float(payload.get("envase_peso"))
                if envase_peso > 0:
                    cantidad_unidades = kilos_total / envase_peso
            if cantidad_unidades <= 0:
                cantidad_unidades = self._to_float(payload.get("cantidad"))
            if cantidad_unidades <= 0:
                # Fallback: usa kilos cuando no hay cantidad.
                cantidad_unidades = kilos_total
            if cantidad_unidades <= 0:
                continue

            tipo = self._normalize_igsa_tipo(payload.get("tipo"))
            lote = str(payload.get("lote") or "").strip()
            lote_key = lote.strip().upper()
            caducidad = expiry_by_key.get((almacen_id, articulo_id, lote_key)) if lote_key else None
            mes = self._to_int(periodo.split("-")[1] if "-" in periodo else 0)
            anio = self._to_int(periodo.split("-")[0] if "-" in periodo else 0)
            fecha = date(anio if anio > 0 else date.today().year, mes if 1 <= mes <= 12 else 1, 1)
            unique_key = f"igsa:{periodo}:{almacen_id}:{articulo_id}:{lote}:{tipo}:{cantidad_unidades}"
            ref_id = str(uuid5(NAMESPACE_URL, unique_key))

            session.add(
                AlmacenMovimiento(
                    almacen_id=almacen_id,
                    articulo_id=articulo_id,
                    pedido_numero=f"IGSA-{periodo}",
                    pedido_albaran_numero=f"IGSA-{tipo}" if tipo else "IGSA",
                    cantidad=-abs(cantidad_unidades),
                    articulo_lote=lote,
                    articulo_caducidad=caducidad,
                    fecha_pedido=fecha,
                    albaran_item_id=f"igsa:{ref_id}",
                )
            )

    def _safe_json_dict(self, text: str) -> dict:
        raw = str(text or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _igsa_file_path(self) -> Path:
        return BASE_DIR.parent / "Recursos" / "Ventas" / "IGSA - Ventas 01 Enero - 2026.xlsx"

    def _read_igsa_consolidado_rows(self, file_path: Path) -> list[dict[str, object]]:
        if not file_path.exists():
            return []
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Workbook contains no default style, apply openpyxl's default",
                category=UserWarning,
            )
            workbook = load_workbook(file_path, data_only=True)
        if "consolidado" not in workbook.sheetnames:
            return []
        sheet = workbook["consolidado"]
        ws = sheet if isinstance(sheet, Worksheet) else None
        if ws is None:
            return []
        header_cells = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        headers = [str(cell).strip() if cell is not None else "" for cell in header_cells]
        rows: list[dict[str, object]] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(cell not in (None, "") for cell in row):
                continue
            item = {headers[idx]: value for idx, value in enumerate(row) if idx < len(headers) and headers[idx]}
            cantidad = self._to_float(item.get("cantidad"))
            envase_peso = self._to_float(item.get("envase_peso"))
            item["kilos"] = cantidad * envase_peso
            item["anio"] = self._to_int(item.get("anio"))
            item["mes_numero"] = self._to_int(item.get("mes_numero"))
            rows.append(item)
        return rows

    def _load_igsa_rows(self) -> list[dict[str, object]]:
        file_path = self._igsa_file_path()
        if not file_path.exists():
            return []
        stat = file_path.stat()
        mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        if self._igsa_rows_cache is not None and self._igsa_mtime_ns == mtime_ns:
            return self._igsa_rows_cache
        rows = self._read_igsa_consolidado_rows(file_path)
        self._igsa_rows_cache = rows
        self._igsa_mtime_ns = mtime_ns
        return rows


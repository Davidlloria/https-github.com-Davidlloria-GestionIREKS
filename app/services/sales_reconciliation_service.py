from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
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

from app.core.config import BASE_DIR
from app.core.database import engine
from app.models import AlmacenMovimiento, Cliente, Distribuidor, Fabricante, Familia, IngredienteIreks, ReferenciaDistribuidor, Subfamilia, VentaImportLote, VentaMensualRaw
from app.services.igsa_sales_pdf_flow_service import IgsaSalesPdfFlowService
from app.services.igsa_sales_workbook_flow_service import IgsaSalesWorkbookFlowService


SALES_CLIENT_TYPES = {"distribuidor", "directo", "cliente directo", "cliente_directo"}


@dataclass
class SalesOpResult:
    ok: bool
    message: str
    imported: int = 0
    incidencias: int = 0


@dataclass
class SalesComparisonRow:
    articulo_id: str
    fabricante_id: str
    familia_id: str
    subfamilia_id: str
    codigo: str
    nombre: str
    kilos_prev: float
    sc_prev: float
    ventas_prev: float
    kilos_curr: float
    sc_curr: float
    ventas_curr: float
    delta_kg: float
    delta_kg_pct: float
    delta_ventas: float
    delta_ventas_pct: float


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


class SalesReconciliationService:
    def __init__(self) -> None:
        self._igsa_unit_codes = {"LPAO", "LPAOP", "555", "777"}
        self._igsa_rows_cache: list[dict[str, object]] | None = None
        self._igsa_mtime_ns: int | None = None
        self._igsa_pdf_flow_service = IgsaSalesPdfFlowService()
        self._igsa_workbook_flow_service = IgsaSalesWorkbookFlowService()

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
        if not isinstance(data, list):
            return SalesOpResult(False, "El JSON de IREKS debe ser una lista de filas.")
        if not data:
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
            for item in data:
                if not isinstance(item, dict):
                    skipped += 1
                    continue

                year = self._to_int(self._get_any(item, "venta_Anio", "venta_Anio".lower(), "anio", "año"))
                month = self._parse_month(self._get_any(item, "venta_Mes", "mes", "venta_Mes".lower()))
                if year <= 0 or month < 1 or month > 12:
                    skipped += 1
                    continue

                periodo = f"{year:04d}-{month:02d}"
                if not first_period:
                    first_period = periodo
                cliente_id = str(self._get_any(item, "Cliente_ID", "cliente_id", "ClienteId", "clienteid") or "").strip()
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
        with Session(engine) as session:
            periods = list(session.exec(select(VentaMensualRaw.periodo)))
        years = sorted(
            {
                int(str(period or "").split("-")[0])
                for period in periods
                if str(period or "").count("-") == 1 and str(period or "").split("-")[0].isdigit()
            },
            reverse=True,
        )
        return years

    def list_years_igsa(self) -> list[int]:
        with Session(engine) as session:
            periods = list(
                session.exec(
                    select(VentaMensualRaw.periodo).where(col(VentaMensualRaw.fuente).in_(["igsa", "igsa_pdf", "igsa_book"]))
                )
            )
        return sorted(
            {
                int(str(period or "").split("-")[0])
                for period in periods
                if str(period or "").count("-") == 1 and str(period or "").split("-")[0].isdigit()
            },
            reverse=True,
        )

    def list_filter_clients(self) -> list[Cliente]:
        with Session(engine) as session:
            rows = list(session.exec(select(Cliente).order_by(Cliente.cliente_nombre_comercial, Cliente.cliente_nombre_fiscal)))
        result: list[Cliente] = []
        for row in rows:
            tipo = str(getattr(row, "cliente_tipo", "") or "").strip().lower()
            if tipo in SALES_CLIENT_TYPES:
                result.append(row)
        return result

    def list_filter_products(self) -> list[IngredienteIreks]:
        with Session(engine) as session:
            return list(
                session.exec(
                    select(IngredienteIreks).order_by(
                        IngredienteIreks.articulo_referencia_corta,
                        IngredienteIreks.articulo_descripcion,
                    )
                )
            )

    def list_filter_manufacturers(self) -> list[Fabricante]:
        with Session(engine) as session:
            return list(session.exec(select(Fabricante).order_by(Fabricante.fabricante_nombre)))

    def list_filter_manufacturers_igsa(self) -> list[Fabricante]:
        ids = self._igsa_related_family_tree()["manufacturer_ids"]
        with Session(engine) as session:
            if not ids:
                return []
            return list(session.exec(select(Fabricante).where(col(Fabricante.fabricante_id).in_(sorted(ids))).order_by(Fabricante.fabricante_nombre)))

    def list_filter_families(self, fabricante_id: str = "") -> list[Familia]:
        clean_fabricante = str(fabricante_id or "").strip()
        with Session(engine) as session:
            stmt = select(Familia).order_by(Familia.articulo_familia_nombre)
            if clean_fabricante:
                stmt = stmt.where(Familia.fabricante_id == clean_fabricante)
            return list(session.exec(stmt))

    def list_filter_families_igsa(self, fabricante_id: str = "") -> list[Familia]:
        tree = self._igsa_related_family_tree()
        valid_ids = tree["family_ids_by_manufacturer"].get(str(fabricante_id or "").strip()) if str(fabricante_id or "").strip() else tree["family_ids"]
        with Session(engine) as session:
            if not valid_ids:
                return []
            return list(
                session.exec(
                    select(Familia)
                    .where(col(Familia.articulo_familia_id).in_(sorted(valid_ids)))
                    .order_by(Familia.articulo_familia_nombre)
                )
            )

    def list_filter_subfamilies(self, familia_id: str = "") -> list[Subfamilia]:
        clean_familia = str(familia_id or "").strip()
        with Session(engine) as session:
            stmt = select(Subfamilia).order_by(Subfamilia.articulo_subfamilia_nombre)
            if clean_familia:
                stmt = stmt.where(Subfamilia.articulo_familia_id == clean_familia)
            return list(session.exec(stmt))

    def list_filter_subfamilies_igsa(self, familia_id: str = "") -> list[Subfamilia]:
        tree = self._igsa_related_family_tree()
        valid_ids = tree["subfamily_ids_by_family"].get(str(familia_id or "").strip()) if str(familia_id or "").strip() else tree["subfamily_ids"]
        with Session(engine) as session:
            if not valid_ids:
                return []
            return list(
                session.exec(
                    select(Subfamilia)
                    .where(col(Subfamilia.articulo_subfamilia_id).in_(sorted(valid_ids)))
                    .order_by(Subfamilia.articulo_subfamilia_nombre)
                )
            )

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
        current_year = int(year or 0)
        if current_year <= 0:
            return []
        previous_year = current_year - 1
        clean_month = int(month or 0)
        if 1 <= clean_month <= 12:
            months = list(range(1, clean_month + 1)) if bool(acumulado) else [clean_month]
        else:
            months = list(range(1, 13))

        clean_producto_texto = self._normalize_search_text(producto_texto)
        clean_fabricante_id = str(fabricante_id or "").strip()
        clean_familia_id = str(familia_id or "").strip()
        clean_subfamilia_id = str(subfamilia_id or "").strip()

        periods = [f"{previous_year:04d}-{m:02d}" for m in months] + [f"{current_year:04d}-{m:02d}" for m in months]
        with Session(engine) as session:
            igsa_rows = list(
                session.exec(
                    select(VentaMensualRaw).where(
                        col(VentaMensualRaw.fuente).in_(["igsa", "igsa_pdf", "igsa_book"]),
                        col(VentaMensualRaw.periodo).in_(periods),
                    )
                )
            )
            products = list(session.exec(select(IngredienteIreks)))

        product_by_id: dict[str, tuple[str, str, str, str, str, str]] = {}
        product_by_code: dict[str, tuple[str, str, str, str, str, str]] = {}
        for product in products:
            aid = str(product.articulo_id or "").strip()
            short_ref = str(product.articulo_referencia_corta or "").strip()
            full_ref = str(product.articulo_referencia or "").strip()
            display_code = short_ref or full_ref
            display_name = str(product.articulo_descripcion or "").strip()
            fabricante = str(product.fabricante_id or "").strip()
            familia = str(product.articulo_familia_id or "").strip()
            subfamilia = str(product.articulo_subfamilia_id or "").strip()
            if aid:
                product_by_id[aid] = (aid, display_code, display_name, fabricante, familia, subfamilia)
            # Prioridad de mapeo por referencia corta.
            for norm in self._code_candidates(short_ref):
                if norm:
                    product_by_code[norm] = (
                        aid,
                        display_code or str(short_ref or "").strip(),
                        display_name,
                        fabricante,
                        familia,
                        subfamilia,
                    )
            # Fallback por referencia completa, sin pisar mapeo corto.
            for norm in self._code_candidates(full_ref):
                if norm and norm not in product_by_code:
                    product_by_code[norm] = (
                        aid,
                        display_code or str(full_ref or "").strip(),
                        display_name,
                        fabricante,
                        familia,
                        subfamilia,
                    )

        totals: dict[str, dict[str, float | str]] = defaultdict(
            lambda: {
                "codigo": "",
                "nombre": "",
                "articulo_id": "",
                "fabricante_id": "",
                "familia_id": "",
                "subfamilia_id": "",
                "kilos_prev": 0.0,
                "sc_prev": 0.0,
                "ventas_prev": 0.0,
                "kilos_curr": 0.0,
                "sc_curr": 0.0,
                "ventas_curr": 0.0,
            }
        )

        for row in igsa_rows:
            row_year = self._period_year(str(getattr(row, "periodo", "") or ""))
            if row_year not in {previous_year, current_year}:
                continue
            product = product_by_id.get(str(getattr(row, "articulo_id", "") or "").strip())
            if product is None:
                for cand in self._code_candidates(getattr(row, "articulo_codigo_origen", "")):
                    product = product_by_code.get(cand)
                    if product is not None:
                        break
            key = product[0] if product and product[0] else self._normalize_code(getattr(row, "articulo_codigo_origen", ""))
            if not key:
                continue
            product_articulo_id = product[0] if product else str(getattr(row, "articulo_id", "") or "").strip()
            product_fabricante_id = product[3] if product else ""
            product_familia_id = product[4] if product else ""
            product_subfamilia_id = product[5] if product else ""

            if clean_producto_texto:
                searchable = self._normalize_search_text(
                    " ".join(
                        [
                            product[1] if product else self._normalize_code(getattr(row, "articulo_codigo_origen", "")),
                            product[2] if product else str(getattr(row, "articulo_descripcion_origen", "") or ""),
                            str(getattr(row, "articulo_codigo_origen", "") or ""),
                            str(getattr(row, "articulo_descripcion_origen", "") or ""),
                        ]
                    )
                )
                if clean_producto_texto not in searchable:
                    continue
            if clean_fabricante_id and product_fabricante_id != clean_fabricante_id:
                continue
            if clean_familia_id and product_familia_id != clean_familia_id:
                continue
            if clean_subfamilia_id and product_subfamilia_id != clean_subfamilia_id:
                continue

            kilos_venta = self._to_float(getattr(row, "venta_kilos", 0.0))
            kilos_sc = self._to_float(getattr(row, "venta_kilos_sc", 0.0))

            bucket = totals[key]
            if not str(bucket["codigo"]):
                bucket["codigo"] = product[1] if product else self._normalize_code(getattr(row, "articulo_codigo_origen", ""))
            if not str(bucket["nombre"]):
                bucket["nombre"] = product[2] if product else str(getattr(row, "articulo_descripcion_origen", "") or "").strip()
            if not str(bucket["articulo_id"]):
                bucket["articulo_id"] = product_articulo_id
            if not str(bucket["fabricante_id"]):
                bucket["fabricante_id"] = product_fabricante_id
            if not str(bucket["familia_id"]):
                bucket["familia_id"] = product_familia_id
            if not str(bucket["subfamilia_id"]):
                bucket["subfamilia_id"] = product_subfamilia_id

            suffix = "curr" if row_year == current_year else "prev"
            bucket[f"kilos_{suffix}"] = float(bucket[f"kilos_{suffix}"] or 0.0) + kilos_venta
            bucket[f"sc_{suffix}"] = float(bucket[f"sc_{suffix}"] or 0.0) + kilos_sc

        result: list[SalesComparisonRow] = []
        for values in totals.values():
            kilos_prev = float(values["kilos_prev"] or 0.0)
            sc_prev = float(values["sc_prev"] or 0.0)
            ventas_prev = float(values["ventas_prev"] or 0.0)
            kilos_curr = float(values["kilos_curr"] or 0.0)
            sc_curr = float(values["sc_curr"] or 0.0)
            ventas_curr = float(values["ventas_curr"] or 0.0)
            total_prev = kilos_prev + sc_prev
            total_curr = kilos_curr + sc_curr
            delta_kg = total_curr - total_prev
            delta_ventas = ventas_curr - ventas_prev
            result.append(
                SalesComparisonRow(
                    articulo_id=str(values["articulo_id"] or ""),
                    fabricante_id=str(values["fabricante_id"] or ""),
                    familia_id=str(values["familia_id"] or ""),
                    subfamilia_id=str(values["subfamilia_id"] or ""),
                    codigo=str(values["codigo"] or ""),
                    nombre=str(values["nombre"] or ""),
                    kilos_prev=kilos_prev,
                    sc_prev=sc_prev,
                    ventas_prev=ventas_prev,
                    kilos_curr=kilos_curr,
                    sc_curr=sc_curr,
                    ventas_curr=ventas_curr,
                    delta_kg=delta_kg,
                    delta_kg_pct=self._pct(delta_kg, total_prev),
                    delta_ventas=delta_ventas,
                    delta_ventas_pct=self._pct(delta_ventas, ventas_prev),
                )
            )
        result.sort(key=lambda x: (x.nombre.lower(), x.codigo.lower()))
        return result

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
        current_year = int(year or 0)
        if current_year <= 0:
            return []
        previous_year = current_year - 1
        clean_month = int(month or 0)
        if 1 <= clean_month <= 12:
            months = list(range(1, clean_month + 1)) if bool(acumulado) else [clean_month]
        else:
            months = list(range(1, 13))
        periods = [f"{previous_year:04d}-{m:02d}" for m in months] + [f"{current_year:04d}-{m:02d}" for m in months]
        clean_cliente_id = str(cliente_id or "").strip()
        clean_articulo_id = str(articulo_id or "").strip()
        clean_producto_texto = self._normalize_search_text(producto_texto)
        clean_fabricante_id = str(fabricante_id or "").strip()
        clean_familia_id = str(familia_id or "").strip()
        clean_subfamilia_id = str(subfamilia_id or "").strip()

        with Session(engine) as session:
            stmt = select(VentaMensualRaw).where(
                col(VentaMensualRaw.fuente) == "ireks",
                col(VentaMensualRaw.periodo).in_(periods),
            )
            if clean_cliente_id:
                stmt = stmt.where(col(VentaMensualRaw.cliente_id) == clean_cliente_id)
            raw_rows = list(session.exec(stmt))
            products = list(session.exec(select(IngredienteIreks)))

        product_by_id: dict[str, tuple[str, str, str, str, str, str]] = {}
        product_by_code: dict[str, tuple[str, str, str, str, str, str]] = {}
        for product in products:
            aid = str(product.articulo_id or "").strip()
            short_ref = str(product.articulo_referencia_corta or "").strip()
            full_ref = str(product.articulo_referencia or "").strip()
            display_code = short_ref or full_ref
            display_name = str(product.articulo_descripcion or "").strip()
            fabricante = str(product.fabricante_id or "").strip()
            familia = str(product.articulo_familia_id or "").strip()
            subfamilia = str(product.articulo_subfamilia_id or "").strip()
            if aid:
                product_by_id[aid] = (aid, display_code, display_name, fabricante, familia, subfamilia)
            for candidate in (short_ref, full_ref):
                norm = self._normalize_code(candidate)
                if norm:
                    product_by_code[norm] = (
                        aid,
                        display_code or str(candidate or "").strip(),
                        display_name,
                        fabricante,
                        familia,
                        subfamilia,
                    )

        totals: dict[str, dict[str, float | str]] = defaultdict(
            lambda: {
                "codigo": "",
                "nombre": "",
                "articulo_id": "",
                "fabricante_id": "",
                "familia_id": "",
                "subfamilia_id": "",
                "kilos_prev": 0.0,
                "sc_prev": 0.0,
                "ventas_prev": 0.0,
                "kilos_curr": 0.0,
                "sc_curr": 0.0,
                "ventas_curr": 0.0,
            }
        )

        for row in raw_rows:
            row_year = self._period_year(row.periodo)
            if row_year not in {previous_year, current_year}:
                continue
            product = product_by_id.get(str(row.articulo_id or "").strip())
            if product is None:
                product = product_by_code.get(self._normalize_code(row.articulo_codigo_origen))
            key = product[0] if product and product[0] else self._normalize_code(row.articulo_codigo_origen)
            if not key:
                continue
            product_articulo_id = product[0] if product else str(row.articulo_id or "").strip()
            product_fabricante_id = product[3] if product else ""
            product_familia_id = product[4] if product else ""
            product_subfamilia_id = product[5] if product else ""
            if clean_articulo_id and product_articulo_id != clean_articulo_id:
                continue
            if clean_producto_texto:
                searchable = self._normalize_search_text(
                    " ".join(
                        [
                            product[1] if product else self._normalize_code(row.articulo_codigo_origen),
                            product[2] if product else str(row.articulo_descripcion_origen or ""),
                            str(row.articulo_codigo_origen or ""),
                            str(row.articulo_descripcion_origen or ""),
                        ]
                    )
                )
                if clean_producto_texto not in searchable:
                    continue
            if clean_fabricante_id and product_fabricante_id != clean_fabricante_id:
                continue
            if clean_familia_id and product_familia_id != clean_familia_id:
                continue
            if clean_subfamilia_id and product_subfamilia_id != clean_subfamilia_id:
                continue

            bucket = totals[key]
            if not str(bucket["codigo"]):
                bucket["codigo"] = product[1] if product else self._normalize_code(row.articulo_codigo_origen)
            if not str(bucket["nombre"]):
                bucket["nombre"] = product[2] if product else str(row.articulo_descripcion_origen or "").strip()
            if not str(bucket["articulo_id"]):
                bucket["articulo_id"] = product_articulo_id
            if not str(bucket["fabricante_id"]):
                bucket["fabricante_id"] = product_fabricante_id
            if not str(bucket["familia_id"]):
                bucket["familia_id"] = product_familia_id
            if not str(bucket["subfamilia_id"]):
                bucket["subfamilia_id"] = product_subfamilia_id

            suffix = "curr" if row_year == current_year else "prev"
            bucket[f"kilos_{suffix}"] = float(bucket[f"kilos_{suffix}"] or 0.0) + float(row.venta_kilos or 0.0)
            bucket[f"sc_{suffix}"] = float(bucket[f"sc_{suffix}"] or 0.0) + float(row.venta_kilos_sc or 0.0)
            bucket[f"ventas_{suffix}"] = float(bucket[f"ventas_{suffix}"] or 0.0) + float(row.venta_euros or 0.0)

        result: list[SalesComparisonRow] = []
        for values in totals.values():
            kilos_prev = float(values["kilos_prev"] or 0.0)
            sc_prev = float(values["sc_prev"] or 0.0)
            ventas_prev = float(values["ventas_prev"] or 0.0)
            kilos_curr = float(values["kilos_curr"] or 0.0)
            sc_curr = float(values["sc_curr"] or 0.0)
            ventas_curr = float(values["ventas_curr"] or 0.0)
            total_prev = kilos_prev + sc_prev
            total_curr = kilos_curr + sc_curr
            delta_kg = total_curr - total_prev
            delta_ventas = ventas_curr - ventas_prev
            result.append(
                SalesComparisonRow(
                    articulo_id=str(values["articulo_id"] or ""),
                    fabricante_id=str(values["fabricante_id"] or ""),
                    familia_id=str(values["familia_id"] or ""),
                    subfamilia_id=str(values["subfamilia_id"] or ""),
                    codigo=str(values["codigo"] or ""),
                    nombre=str(values["nombre"] or ""),
                    kilos_prev=kilos_prev,
                    sc_prev=sc_prev,
                    ventas_prev=ventas_prev,
                    kilos_curr=kilos_curr,
                    sc_curr=sc_curr,
                    ventas_curr=ventas_curr,
                    delta_kg=delta_kg,
                    delta_kg_pct=self._pct(delta_kg, total_prev),
                    delta_ventas=delta_ventas,
                    delta_ventas_pct=self._pct(delta_ventas, ventas_prev),
                )
            )
        result.sort(key=lambda x: (x.nombre.lower(), x.codigo.lower()))
        return result

    def _period_year(self, periodo: str) -> int:
        text = str(periodo or "").strip()
        if text.count("-") != 1:
            return 0
        year = text.split("-")[0]
        return int(year) if year.isdigit() else 0

    def _pct(self, delta: float, base: float) -> float:
        if abs(base) <= 1e-9:
            return 0.0
        return (float(delta or 0.0) / float(base)) * 100.0

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
        text = str(value or "").strip().lower()
        normalized = unicodedata.normalize("NFD", text)
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return re.sub(r"\s+", " ", normalized)

    def _normalize_code(self, value) -> str:
        text = str(value or "").strip().upper()
        if not text:
            return ""
        if re.fullmatch(r"\d+(\.0+)?", text):
            return str(int(float(text)))
        return text

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

    def _igsa_related_family_tree(self) -> dict[str, object]:
        with Session(engine) as session:
            raw_rows = list(
                session.exec(
                    select(VentaMensualRaw.articulo_id, VentaMensualRaw.articulo_codigo_origen).where(
                        col(VentaMensualRaw.fuente).in_(["igsa", "igsa_pdf", "igsa_book"])
                    )
                )
            )
        product_ids = {str(aid or "").strip() for aid, _code in raw_rows if str(aid or "").strip()}
        product_refs = {self._normalize_code(code) for _aid, code in raw_rows if self._normalize_code(code)}
        with Session(engine) as session:
            products = list(session.exec(select(IngredienteIreks)))

        manufacturer_ids: set[str] = set()
        family_ids: set[str] = set()
        subfamily_ids: set[str] = set()
        family_ids_by_manufacturer: dict[str, set[str]] = defaultdict(set)
        subfamily_ids_by_family: dict[str, set[str]] = defaultdict(set)

        for product in products:
            aid = str(product.articulo_id or "").strip()
            ref_short = self._normalize_code(product.articulo_referencia_corta)
            ref_full = self._normalize_code(product.articulo_referencia)
            if aid not in product_ids and ref_short not in product_refs and ref_full not in product_refs:
                continue
            manufacturer_id = str(product.fabricante_id or "").strip()
            family_id = str(product.articulo_familia_id or "").strip()
            subfamily_id = str(product.articulo_subfamilia_id or "").strip()
            if manufacturer_id:
                manufacturer_ids.add(manufacturer_id)
            if family_id:
                family_ids.add(family_id)
            if subfamily_id:
                subfamily_ids.add(subfamily_id)
            if manufacturer_id and family_id:
                family_ids_by_manufacturer[manufacturer_id].add(family_id)
            if family_id and subfamily_id:
                subfamily_ids_by_family[family_id].add(subfamily_id)

        return {
            "manufacturer_ids": manufacturer_ids,
            "family_ids": family_ids,
            "subfamily_ids": subfamily_ids,
            "family_ids_by_manufacturer": family_ids_by_manufacturer,
            "subfamily_ids_by_family": subfamily_ids_by_family,
        }

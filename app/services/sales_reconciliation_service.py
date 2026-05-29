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
        self._igsa_pdf_line_pattern = re.compile(
            r"(?P<codigo>D?\d{3,7})\s*"
            r"(?P<descripcion>.+?)\s+"
            r"(?P<kilos>\d[\d\.,]*)\s+"
            r"(?P<env>\d[\d\.,]*)\s+"
            r"(?P<precio>\d[\d\.,]*)\s+"
            r"(?P<descuento>\d[\d\.,]*)\s+"
            r"(?P<total>\d[\d\.,]*)\s+"
            r"(?P<emb>\d[\d\.,]*)\s+"
            r"(?P<iva>\d[\d\.,]*)"
            r"Lote:(?P<lote>.*?)"
            r"Cons\.Pref:(?P<cons_pref>\d{2}/\d{2}/\d{2})"
            r"Carga:(?P<carga>.*?)(?=(?:D?\d{3,7}\s*.+?\s+\d[\d\.,]*\s+\d[\d\.,]*\s+\d[\d\.,]*\s+\d[\d\.,]*\s+\d[\d\.,]*\s+\d[\d\.,]*\s+\d[\d\.,]*Lote:)|Operador|Datos transporte|TOTAL BRUTO|IREKS IBERICA|$)",
            re.DOTALL,
        )

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
        if not file_path.exists():
            return [], [f"No existe el archivo: {file_path}"]
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Workbook contains no default style, apply openpyxl's default",
                category=UserWarning,
            )
            workbook = load_workbook(file_path, data_only=True)
        sheetnames = list(workbook.sheetnames or [])
        if not sheetnames:
            return [], ["El libro no contiene hojas."]

        month_map = {
            "enero": 1, "ene": 1, "febrero": 2, "feb": 2, "marzo": 3, "mar": 3, "abril": 4, "abr": 4, "mayo": 5,
            "junio": 6, "jun": 6, "julio": 7, "jul": 7, "agosto": 8, "ago": 8, "septiembre": 9, "setiembre": 9,
            "sep": 9, "set": 9, "octubre": 10, "oct": 10, "noviembre": 11, "nov": 11, "diciembre": 12, "dic": 12,
        }

        def infer_period(ws: Worksheet) -> str:
            scan_lines: list[str] = []
            for row in ws.iter_rows(min_row=1, max_row=min(15, ws.max_row), min_col=1, max_col=4, values_only=True):
                for cell in row:
                    txt = str(cell or "").strip()
                    if txt:
                        scan_lines.append(txt)
            joined = " ".join(scan_lines).lower()
            joined = unicodedata.normalize("NFD", joined)
            joined = "".join(ch for ch in joined if unicodedata.category(ch) != "Mn")
            year_match = re.search(r"(20\d{2})", joined)
            yy_match = re.search(r"\b(\d{2})\b", joined)
            month_num = 0
            for key, val in month_map.items():
                if re.search(rf"\b{re.escape(key)}\b", joined):
                    month_num = val
                    break
            year = 0
            if year_match:
                year = int(year_match.group(1))
            elif yy_match:
                two = int(yy_match.group(1))
                year = 2000 + two if two <= 79 else 1900 + two
            if year > 0 and 1 <= month_num <= 12:
                return f"{year:04d}-{month_num:02d}"
            stem = unicodedata.normalize("NFD", str(file_path.stem or "").lower())
            stem = "".join(ch for ch in stem if unicodedata.category(ch) != "Mn")
            yy_file = re.search(r"\b(\d{2})\b", stem)
            month_file = 0
            for key, val in month_map.items():
                if re.search(rf"\b{re.escape(key)}\b", stem):
                    month_file = val
                    break
            if yy_file and month_file:
                two = int(yy_file.group(1))
                year_file = 2000 + two if two <= 79 else 1900 + two
                return f"{year_file:04d}-{month_file:02d}"
            return ""

        rows_out: list[IgsaWorkbookParsedLine] = []
        errors: list[str] = []
        for sheet_idx, sheet_name in enumerate(sheetnames, start=1):
            ws_obj = workbook[sheet_name]
            ws = ws_obj if isinstance(ws_obj, Worksheet) else None
            if ws is None:
                continue
            if sheet_idx == 1:
                tipo = "venta"
            elif sheet_idx == 2:
                tipo = "promocion"
            else:
                tipo = "muestras"
            es_sc = self._is_sc_tipo(tipo)
            periodo = infer_period(ws)
            if not periodo:
                errors.append(f"{sheet_name}: no se pudo inferir periodo (AAAA-MM).")
                continue
            for row_idx in range(1, ws.max_row + 1):
                ref_distribuidor = str(ws.cell(row=row_idx, column=1).value or "").strip()
                codigo_raw = self._normalize_code(ws.cell(row=row_idx, column=2).value)
                codigo_compact = re.sub(r"\s+", "", str(codigo_raw or "").upper())
                if codigo_compact in {"LPAO", "LPAOP"}:
                    codigo = codigo_compact
                else:
                    code_match = re.match(r"^(D)?(\d+)", codigo_compact)
                    codigo = f"{code_match.group(1) or ''}{code_match.group(2)}" if code_match else codigo_compact
                descripcion = str(ws.cell(row=row_idx, column=3).value or "").strip()
                peso_envase = self._to_float(ws.cell(row=row_idx, column=4).value)
                cantidad_total = self._to_float(ws.cell(row=row_idx, column=5).value)
                if cantidad_total <= 0:
                    # Regla solicitada: filas sin total en E no se importan y no computan error.
                    continue
                # Regla: referencia fabricante solo numerica o con prefijo D.
                if codigo and codigo not in {"LPAO", "LPAOP"} and not re.fullmatch(r"(?:D\d+|\d+)", codigo):
                    errors.append(
                        f"{sheet_name} fila {row_idx}: referencia fabricante invalida '{codigo}' "
                        "(solo se admite numerico o prefijo D al inicio)."
                    )
                    continue
                if not codigo or not descripcion:
                    continue
                lotes: list[tuple[float, str, bool]] = []
                for col_idx in range(6, 14):
                    raw = str(ws.cell(row=row_idx, column=col_idx).value or "").strip()
                    if not raw:
                        continue
                    raw_norm = re.sub(r"\s+", "", raw)
                    match = re.match(r"(?:(\d+(?:[.,]\d+)?)\s*)?L\.?(.+)$", raw_norm, flags=re.IGNORECASE)
                    if not match:
                        # En promociones/muestras, texto distinto de lote se considera comentario y se ignora.
                        if es_sc:
                            continue
                        # En ventas, si llega texto no vacio fuera del patron L/L., se asume lote literal.
                        lotes.append((1.0, raw_norm, True))
                        continue
                    qty_txt = str(match.group(1) or "").strip()
                    lote = str(match.group(2) or "").strip()
                    qty_missing = not bool(qty_txt)
                    qty = self._to_float(qty_txt) if qty_txt else 1.0
                    if qty <= 0:
                        errors.append(f"{sheet_name} fila {row_idx}: cantidad de lote no valida en columna {col_idx}.")
                        continue
                    if not lote:
                        errors.append(f"{sheet_name} fila {row_idx}: lote vacio en columna {col_idx}.")
                        continue
                    lotes.append((qty, lote, qty_missing))
                # Tolerancia solicitada:
                # si hay un único lote y su número no viene informado, usar E como cantidad del lote.
                if len(lotes) == 1 and lotes[0][2] and cantidad_total > 0:
                    lotes = [(float(cantidad_total), lotes[0][1], False)]
                suma_lotes = sum(x[0] for x in lotes)
                # Productos sin lote: no se considera error, se importa una línea sin lote con cantidad E.
                if not lotes:
                    rows_out.append(
                        IgsaWorkbookParsedLine(
                            sheet_name=sheet_name,
                            source_row=row_idx,
                            tipo=tipo,
                            periodo=periodo,
                            ref_distribuidor=ref_distribuidor,
                            codigo=codigo,
                            descripcion=descripcion,
                            peso_envase=peso_envase,
                            cantidad_total=cantidad_total,
                            cantidad_lote=float(cantidad_total),
                            lote="",
                            es_sc=es_sc,
                            suma_cantidad_lotes=float(cantidad_total),
                        )
                    )
                    continue
                if abs(suma_lotes - cantidad_total) > 0.001:
                    errors.append(
                        f"{sheet_name} fila {row_idx}: suma lotes={suma_lotes:.3f} distinta de E={cantidad_total:.3f}."
                    )
                for qty_lote, lote, _qty_missing in lotes:
                    rows_out.append(
                        IgsaWorkbookParsedLine(
                            sheet_name=sheet_name,
                            source_row=row_idx,
                            tipo=tipo,
                            periodo=periodo,
                            ref_distribuidor=ref_distribuidor,
                            codigo=codigo,
                            descripcion=descripcion,
                            peso_envase=peso_envase,
                            cantidad_total=cantidad_total,
                            cantidad_lote=float(qty_lote),
                            lote=lote,
                            es_sc=es_sc,
                            suma_cantidad_lotes=float(suma_lotes),
                        )
                    )
        return rows_out, errors

    def build_igsa_workbook_preview(
        self,
        lines: list[IgsaWorkbookParsedLine],
        cliente_id: str,
    ) -> tuple[list[dict[str, object]], list[str]]:
        if not lines:
            return [], []
        preview_rows: list[dict[str, object]] = []
        errors: list[str] = []
        with Session(engine) as session:
            distribuidor_ids = self._resolve_igsa_distribuidor_ids(session, cliente_id)
            ref_rows = (
                list(
                    session.exec(
                        select(ReferenciaDistribuidor).where(col(ReferenciaDistribuidor.distribuidor_id).in_(sorted(distribuidor_ids)))
                    )
                )
                if distribuidor_ids
                else []
            )
            articulo_ids = {str(getattr(x, "articulo_id", "") or "").strip() for x in ref_rows}
            articulo_ids = {x for x in articulo_ids if x}
            products = (
                list(session.exec(select(IngredienteIreks).where(col(IngredienteIreks.articulo_id).in_(sorted(articulo_ids)))))
                if articulo_ids
                else []
            )
            product_by_id = {str(getattr(x, "articulo_id", "") or "").strip(): x for x in products}
            ref_map: dict[str, str] = {}
            for ref in ref_rows:
                aid = str(getattr(ref, "articulo_id", "") or "").strip()
                raw = str(getattr(ref, "articulo_referencia_distribuidor", "") or "").strip()
                if not aid or not raw:
                    continue
                for cand in self._code_candidates(raw):
                    ref_map[cand] = aid

            for line in lines:
                aid = ""
                for cand in self._code_candidates(line.ref_distribuidor):
                    aid = ref_map.get(cand, "")
                    if aid:
                        break
                if not aid:
                    errors.append(f"{line.sheet_name} fila {line.source_row}: sin ficha por ref. distribuidor '{line.ref_distribuidor}'")
                    continue
                product = product_by_id.get(aid)
                if product is None:
                    errors.append(f"{line.sheet_name} fila {line.source_row}: articulo_id sin ficha '{aid}'")
                    continue
                peso_envase = float(getattr(product, "articulo_envase_peso_total", 0.0) or 0.0)
                if peso_envase <= 0:
                    peso_envase = float(getattr(product, "articulo_envase_peso", 0.0) or 0.0)
                ref_fabricante = str(getattr(product, "articulo_referencia_corta", "") or "").strip() or str(
                    getattr(product, "articulo_referencia", "") or ""
                ).strip()
                descripcion = str(getattr(product, "articulo_descripcion", "") or "").strip() or str(line.descripcion or "").strip()
                num_envases = float(line.cantidad_lote or 0.0)
                preview_rows.append(
                    {
                        "periodo": str(line.periodo or "").strip(),
                        "ref_distribuidor": str(line.ref_distribuidor or "").strip(),
                        "ref_fabricante": ref_fabricante,
                        "descripcion": descripcion,
                        "peso_envase": peso_envase,
                        "num_envases": num_envases,
                        "tot_kg": num_envases * peso_envase,
                        "lote": str(line.lote or "").strip(),
                        "tipo": str(line.tipo or "").strip(),
                        "articulo_id": aid,
                    }
                )
        return preview_rows, errors

    def import_igsa_workbook_lines(
        self,
        lines: list[IgsaWorkbookParsedLine],
        cliente_id: str,
        *,
        force_reimport: bool = False,
    ) -> SalesOpResult:
        clean_cliente_id = str(cliente_id or "").strip()
        if not clean_cliente_id:
            return SalesOpResult(False, "Cliente/Distribuidor IGSA no valido.")
        if not lines:
            return SalesOpResult(False, "No hay lineas para importar.")
        periodos = sorted({str(x.periodo or "").strip() for x in lines if str(x.periodo or "").strip()})
        if not periodos:
            return SalesOpResult(False, "No se detecto periodo valido en las lineas.")

        payload_hash = hashlib.sha256(
            "|".join(
                sorted(
                    [
                        f"{x.periodo}|{x.sheet_name}|{x.source_row}|{x.codigo}|{x.cantidad_lote}|{x.lote}|{x.tipo}"
                        for x in lines
                    ]
                )
            ).encode("utf-8")
        ).hexdigest()

        with Session(engine) as session:
            distribuidor_ids = self._resolve_igsa_distribuidor_ids(session, clean_cliente_id)
            existing = session.exec(
                select(VentaImportLote).where(
                    VentaImportLote.fuente == "igsa_book",
                    VentaImportLote.archivo_hash == payload_hash,
                )
            ).first()
            if existing is not None and not force_reimport:
                return SalesOpResult(True, "El libro ya estaba importado.", imported=0, incidencias=0)
            if existing is not None and force_reimport:
                old_rows = list(session.exec(select(VentaMensualRaw).where(VentaMensualRaw.lote_id == existing.lote_id)))
                for old_row in old_rows:
                    session.delete(old_row)
                session.delete(existing)

            for periodo in periodos:
                stmt = select(VentaMensualRaw).where(
                    col(VentaMensualRaw.fuente) == "igsa_book",
                    col(VentaMensualRaw.periodo) == periodo,
                )
                for old_row in session.exec(stmt):
                    session.delete(old_row)

            lote = VentaImportLote(
                lote_id=str(uuid4()),
                fuente="igsa_book",
                cliente_id=clean_cliente_id,
                periodo=periodos[0],
                archivo_nombre="IGSA workbook sheets",
                archivo_hash=payload_hash,
                estado="procesado",
            )
            session.add(lote)
            session.flush()

            ref_rows = (
                list(
                    session.exec(
                        select(ReferenciaDistribuidor).where(col(ReferenciaDistribuidor.distribuidor_id).in_(sorted(distribuidor_ids)))
                    )
                )
                if distribuidor_ids
                else []
            )
            articulo_ids = {str(getattr(x, "articulo_id", "") or "").strip() for x in ref_rows}
            articulo_ids = {x for x in articulo_ids if x}
            products = (
                list(session.exec(select(IngredienteIreks).where(col(IngredienteIreks.articulo_id).in_(sorted(articulo_ids)))))
                if articulo_ids
                else []
            )
            product_by_id = {str(getattr(x, "articulo_id", "") or "").strip(): x for x in products}
            ref_map: dict[str, str] = {}
            for ref in ref_rows:
                aid = str(getattr(ref, "articulo_id", "") or "").strip()
                raw = str(getattr(ref, "articulo_referencia_distribuidor", "") or "").strip()
                if not aid or not raw:
                    continue
                for cand in self._code_candidates(raw):
                    ref_map[cand] = aid

            skipped = 0
            skipped_details: list[str] = []
            inserted_rows: list[VentaMensualRaw] = []
            for line in lines:
                code = self._normalize_code(line.codigo)
                ref_dist = self._normalize_code(line.ref_distribuidor)
                articulo_id = ""
                for cand in self._code_candidates(ref_dist):
                    articulo_id = ref_map.get(cand, "")
                    if articulo_id:
                        break
                if not articulo_id:
                    skipped += 1
                    skipped_details.append(
                        f"{line.sheet_name} fila {line.source_row} ({code}): sin mapeo por ref distribuidor '{line.ref_distribuidor}'"
                    )
                    continue
                product = product_by_id.get(articulo_id)
                if product is None:
                    skipped += 1
                    skipped_details.append(
                        f"{line.sheet_name} fila {line.source_row} ({code}): articulo_id {articulo_id} sin ficha"
                    )
                    continue
                descripcion = str(getattr(product, "articulo_descripcion", "") or "").strip() or str(line.descripcion or "").strip()
                peso_master = float(getattr(product, "articulo_envase_peso_total", 0.0) or 0.0)
                if peso_master <= 0:
                    peso_master = float(getattr(product, "articulo_envase_peso", 0.0) or 0.0)
                peso_fuente = peso_master if peso_master > 0 else float(line.peso_envase or 0.0)
                kilos = float(line.cantidad_lote or 0.0) * float(peso_fuente or 0.0)
                is_unit_article = code in self._igsa_unit_codes
                if kilos <= 0:
                    if is_unit_article and float(line.cantidad_lote or 0.0) > 0:
                        # Artículos medidos por unidades: se permite importar sin kg.
                        # Se usa cantidad_lote para mantener magnitud de venta en el resumen.
                        kilos = float(line.cantidad_lote or 0.0)
                    else:
                        skipped += 1
                        skipped_details.append(
                            f"{line.sheet_name} fila {line.source_row} ({code}): kilos no validos (cantidad={line.cantidad_lote}, peso_ficha={peso_master}, peso_excel={line.peso_envase})"
                        )
                        continue
                tipo_norm = self._normalize_igsa_tipo(line.tipo)
                venta_kilos = 0.0 if self._is_sc_tipo(tipo_norm) else kilos
                venta_kilos_sc = kilos if self._is_sc_tipo(tipo_norm) else 0.0
                payload = {
                    "anio": int(str(line.periodo).split("-")[0]) if "-" in str(line.periodo) else 0,
                    "mes": int(str(line.periodo).split("-")[1]) if "-" in str(line.periodo) else 0,
                    "tipo": tipo_norm,
                    "ref_distribuidor": str(line.ref_distribuidor or "").strip(),
                    "cantidad_lote": float(line.cantidad_lote),
                    "lote": str(line.lote or "").strip(),
                    "articulo_id": articulo_id,
                }
                row = VentaMensualRaw(
                    raw_id=str(uuid4()),
                    lote_id=str(lote.lote_id or "").strip(),
                    fuente="igsa_book",
                    cliente_id=clean_cliente_id,
                    periodo=str(line.periodo or "").strip(),
                    articulo_codigo_origen=code,
                    articulo_id=articulo_id,
                    articulo_descripcion_origen=descripcion,
                    venta_kilos=venta_kilos,
                    venta_kilos_sc=venta_kilos_sc,
                    venta_euros=0.0,
                    payload_json=json.dumps(payload, ensure_ascii=False),
                )
                session.add(row)
                inserted_rows.append(row)

            session.commit()
            if not inserted_rows:
                return SalesOpResult(False, "No se pudo importar ninguna fila valida.", imported=0, incidencias=skipped)
            self._sync_igsa_sales_to_warehouse(session, inserted_rows)
            session.commit()
        msg = "Importacion IGSA (libro por hojas) completada."
        if skipped_details:
            preview = " | ".join(skipped_details[:6])
            extra = "" if len(skipped_details) <= 6 else f" | ... y {len(skipped_details) - 6} mas."
            msg += f"\nOmitidas: {preview}{extra}"
        return SalesOpResult(True, msg, imported=len(inserted_rows), incidencias=skipped)

    def parse_igsa_pdf_files(self, file_paths: list[Path]) -> tuple[list[IgsaPdfParsedLine], list[str]]:
        rows: list[IgsaPdfParsedLine] = []
        errors: list[str] = []
        for file_path in file_paths:
            if not file_path.exists():
                errors.append(f"No existe el archivo: {file_path}")
                continue
            try:
                raw_text = self._read_pdf_text(file_path)
                fecha, ref_pedido = self._extract_pdf_header(raw_text)
                doc_type = self._infer_pdf_doc_type_from_ref_pedido(raw_text)
                if not doc_type:
                    doc_type = self._infer_pdf_doc_type(file_path.name)
                lines = self._extract_pdf_lines(raw_text, file_path.name, doc_type, fecha, ref_pedido)
                rows.extend(lines)
                if not lines:
                    errors.append(f"Sin lineas detectadas en: {file_path.name}")
            except Exception as exc:
                errors.append(f"Error procesando {file_path.name}: {exc}")
        return rows, errors

    def import_igsa_pdf_lines(self, lines: list[IgsaPdfParsedLine], cliente_id: str = "") -> SalesOpResult:
        if not lines:
            return SalesOpResult(False, "No hay lineas para importar.")

        periodos = sorted({self._period_from_ddmmyy(line.fecha) for line in lines if self._period_from_ddmmyy(line.fecha)})
        if not periodos:
            return SalesOpResult(False, "No se detecto ninguna fecha valida (dd/mm/aa) en los PDFs.")

        payload_hash = hashlib.sha256(
            "|".join(
                sorted(
                    [
                        f"{line.source_file}|{line.ref_pedido}|{line.codigo}|{line.kilos}|{line.total}|{line.lote}"
                        for line in lines
                    ]
                )
            ).encode("utf-8")
        ).hexdigest()

        clean_cliente_id = str(cliente_id or "").strip()
        with Session(engine) as session:
            existing = session.exec(
                select(VentaImportLote).where(
                    VentaImportLote.fuente == "igsa_pdf",
                    VentaImportLote.archivo_hash == payload_hash,
                )
            ).first()
            if existing is not None:
                old_rows = list(session.exec(select(VentaMensualRaw).where(VentaMensualRaw.lote_id == existing.lote_id)))
                for old_row in old_rows:
                    session.delete(old_row)
                session.delete(existing)
                session.commit()

            source_files = {str(line.source_file or "").strip() for line in lines if str(line.source_file or "").strip()}
            if source_files:
                stmt = select(VentaMensualRaw).where(
                    col(VentaMensualRaw.fuente) == "igsa_pdf",
                    col(VentaMensualRaw.periodo).in_(periodos),
                )
                for old_row in session.exec(stmt):
                    payload = self._safe_json_dict(getattr(old_row, "payload_json", ""))
                    origin_name = str(payload.get("origen_archivo") or "").strip()
                    if origin_name and origin_name in source_files:
                        session.delete(old_row)

            lote = VentaImportLote(
                lote_id=str(uuid4()),
                fuente="igsa_pdf",
                cliente_id=clean_cliente_id,
                periodo=periodos[0],
                archivo_nombre=", ".join(sorted({line.source_file for line in lines})),
                archivo_hash=payload_hash,
                estado="procesado",
            )
            session.add(lote)
            session.flush()

            product_by_code: dict[str, dict[str, object]] = {}
            for product in session.exec(select(IngredienteIreks)):
                articulo_id = str(product.articulo_id or "").strip()
                if not articulo_id:
                    continue
                product_data = {
                    "articulo_id": articulo_id,
                    "descripcion": str(product.articulo_descripcion or "").strip(),
                    "envase_cantidad": float(product.articulo_envase_cantidad or 0.0),
                    "envase_peso": float(product.articulo_envase_peso or 0.0),
                    "envase_peso_total": float(product.articulo_envase_peso_total or 0.0),
                }
                for code in (product.articulo_referencia_corta, product.articulo_referencia):
                    clean = self._normalize_code(code)
                    if clean:
                        product_by_code[clean] = product_data

            skipped = 0
            inserted_rows: list[VentaMensualRaw] = []
            product_weight_updates: dict[str, float] = {}
            for line in lines:
                periodo = self._period_from_ddmmyy(line.fecha)
                if not periodo:
                    skipped += 1
                    continue
                code = self._normalize_code(line.codigo)
                product_data = product_by_code.get(code, {})
                articulo_id = str(product_data.get("articulo_id") or "").strip()
                descripcion = str(product_data.get("descripcion") or "").strip() or line.descripcion
                envase_cantidad_master = float(product_data.get("envase_cantidad") or 0.0)
                envase_peso_master = float(product_data.get("envase_peso") or 0.0)
                envase_peso_total_master = float(product_data.get("envase_peso_total") or 0.0)
                envase_cantidad = envase_cantidad_master if envase_cantidad_master > 0 else line.envases
                envase_peso = envase_peso_master if envase_peso_master > 0 else line.emb
                if articulo_id and line.emb > 0 and (envase_peso_total_master <= 0 or abs(envase_peso_total_master - line.emb) > 0.0001):
                    product_weight_updates[articulo_id] = float(line.emb)
                tipo_norm = self._normalize_igsa_tipo(line.doc_type)
                payload = {
                    "codigo": line.codigo,
                    "descripcion": descripcion,
                    "kilos": line.kilos,
                    "cantidad": line.envases,
                    "envase_peso": line.emb,
                    "cantidad_documento": line.envases,
                    "envase_peso_documento": line.emb,
                    "cantidad_maestro": envase_cantidad,
                    "envase_peso_maestro": envase_peso,
                    "precio": line.precio,
                    "descuento_pct": line.descuento_pct,
                    "total": line.total,
                    "iva": line.iva,
                    "lote": line.lote,
                    "carga": line.carga,
                    "cons_pref": line.cons_pref,
                    "fecha": line.fecha,
                    "ref_pedido": line.ref_pedido,
                    "tipo": tipo_norm or line.doc_type,
                    "origen_archivo": line.source_file,
                }
                inserted = VentaMensualRaw(
                    raw_id=str(uuid4()),
                    lote_id=lote.lote_id,
                    fuente="igsa_pdf",
                    cliente_id=clean_cliente_id,
                    periodo=periodo,
                    articulo_codigo_origen=code,
                    articulo_id=articulo_id,
                    articulo_descripcion_origen=descripcion,
                    venta_kilos=line.kilos if tipo_norm == "venta" else 0.0,
                    venta_kilos_sc=line.kilos if tipo_norm in {"muestras", "promociones", "s/c"} else 0.0,
                    venta_euros=line.total if tipo_norm == "venta" else 0.0,
                    payload_json=json.dumps(payload, ensure_ascii=False),
                )
                inserted_rows.append(inserted)
                session.add(inserted)

            if product_weight_updates:
                products_to_update = list(
                    session.exec(
                        select(IngredienteIreks).where(col(IngredienteIreks.articulo_id).in_(sorted(product_weight_updates.keys())))
                    )
                )
                for product in products_to_update:
                    aid = str(getattr(product, "articulo_id", "") or "").strip()
                    if not aid:
                        continue
                    detected_weight = float(product_weight_updates.get(aid, 0.0) or 0.0)
                    if detected_weight <= 0:
                        continue
                    current_total = float(getattr(product, "articulo_envase_peso_total", 0.0) or 0.0)
                    if current_total <= 0 or abs(current_total - detected_weight) > 0.0001:
                        product.articulo_envase_peso_total = detected_weight
                    if float(getattr(product, "articulo_envase_peso", 0.0) or 0.0) <= 0:
                        product.articulo_envase_peso = detected_weight
                    session.add(product)

            session.commit()
            sync_rows = list(
                session.exec(
                    select(VentaMensualRaw).where(
                        col(VentaMensualRaw.fuente) == "igsa_pdf",
                        col(VentaMensualRaw.periodo).in_(periodos),
                    )
                )
            )
            self._sync_igsa_sales_to_warehouse(session, sync_rows)
            session.commit()

        self._igsa_rows_cache = None
        self._igsa_mtime_ns = None
        return SalesOpResult(True, "Importacion PDF IGSA completada.", imported=len(lines) - skipped, incidencias=skipped)

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

    def _read_pdf_text(self, file_path: Path) -> str:
        try:
            from pypdf import PdfReader
        except Exception as exc:
            raise ValueError(f"No se pudo cargar pypdf: {exc}") from exc
        reader = PdfReader(str(file_path))
        return "".join(str(page.extract_text() or "") for page in reader.pages)

    def _extract_pdf_header(self, text: str) -> tuple[str, str]:
        match = re.search(r"Ref\.\s*pedido:\s*([A-Z0-9]+)\s+(\d{2}/\d{2}/\d{2})", str(text or ""), re.IGNORECASE)
        if match:
            return match.group(2).strip(), match.group(1).strip()
        return "", ""

    def _infer_pdf_doc_type(self, name: str) -> str:
        raw = self._normalize_search_text(name)
        if "muestra" in raw:
            return "muestras"
        if "promocion" in raw:
            return "promociones"
        return "venta"

    def _infer_pdf_doc_type_from_ref_pedido(self, text: str) -> str:
        lines = [str(x or "").strip() for x in str(text or "").splitlines() if str(x or "").strip()]
        if not lines:
            return ""
        for idx, line in enumerate(lines):
            if not re.search(r"Ref\.\s*pedido\s*:", line, re.IGNORECASE):
                continue
            window = " ".join(lines[idx : min(idx + 10, len(lines))])
            normalized = self._normalize_search_text(window)
            if "promo" in normalized or "promocion" in normalized or "promos" in normalized:
                return "promociones"
            if "muestra" in normalized or "muestras" in normalized:
                return "muestras"
            if "venta" in normalized or "ventas" in normalized:
                return "venta"
        return ""

    def _extract_pdf_lines(
        self,
        text: str,
        source_file: str,
        doc_type: str,
        fecha: str,
        ref_pedido: str,
    ) -> list[IgsaPdfParsedLine]:
        parsed: list[IgsaPdfParsedLine] = []
        raw_text = str(text or "")
        idx = raw_text.find("Fecha entrega:")
        scan_text = raw_text[idx + len("Fecha entrega:") :] if idx >= 0 else raw_text
        for match in self._igsa_pdf_line_pattern.finditer(scan_text):
            row = IgsaPdfParsedLine(
                source_file=source_file,
                doc_type=doc_type,
                fecha=fecha,
                ref_pedido=ref_pedido,
                codigo=str(match.group("codigo") or "").strip(),
                descripcion=re.sub(r"\s+", " ", str(match.group("descripcion") or "")).strip(),
                kilos=self._parse_es_number(match.group("kilos")),
                envases=self._parse_es_number(match.group("env")),
                emb=self._parse_es_number(match.group("emb")),
                precio=self._parse_es_number(match.group("precio")),
                descuento_pct=self._parse_es_number(match.group("descuento")),
                total=self._parse_es_number(match.group("total")),
                iva=self._parse_es_number(match.group("iva")),
                lote=str(match.group("lote") or "").strip(),
                carga=re.sub(r"\s+", " ", str(match.group("carga") or "")).strip(),
                cons_pref=str(match.group("cons_pref") or "").strip(),
            )
            if self._is_valid_igsa_pdf_line(row):
                parsed.append(row)
        return parsed

    def _is_valid_igsa_pdf_line(self, row: IgsaPdfParsedLine) -> bool:
        code = self._normalize_code(row.codigo)
        if not re.fullmatch(r"(?:D\d{6,7}|\d{4,6})", code):
            return False
        if row.kilos <= 0 or row.envases <= 0 or row.emb <= 0:
            return False
        description = self._normalize_search_text(row.descripcion)
        if not description or len(description) > 180:
            return False
        banned_fragments = [
            "reglamento (ue)",
            "responsable del tratamiento",
            "www.agpd.es",
            "parc tecnologic",
            "camino de la villa",
            "nif:",
            "fecha pedido:",
            "n pedido:",
            "datos transporte",
            "observaciones",
            "total bruto",
        ]
        return not any(fragment in description for fragment in banned_fragments)

    def _parse_es_number(self, value: object) -> float:
        text = str(value or "").strip()
        if not text:
            return 0.0
        clean = text.replace(".", "").replace(",", ".")
        try:
            return float(clean)
        except Exception:
            return 0.0

    def _period_from_ddmmyy(self, value: str) -> str:
        raw = str(value or "").strip()
        if not re.fullmatch(r"\d{2}/\d{2}/\d{2}", raw):
            return ""
        _day, month, year = raw.split("/")
        yy = int(year)
        yyyy = 2000 + yy if yy <= 79 else 1900 + yy
        mm = int(month)
        if mm < 1 or mm > 12:
            return ""
        return f"{yyyy:04d}-{mm:02d}"

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

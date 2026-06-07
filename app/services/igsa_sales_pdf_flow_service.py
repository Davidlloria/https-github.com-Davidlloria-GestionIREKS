from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Callable
from uuid import uuid4

from sqlmodel import Session, col, select

from app.core.database import engine
from app.models import IngredienteIreks, VentaImportLote, VentaMensualRaw

if TYPE_CHECKING:
    from app.services.sales_reconciliation_service import IgsaPdfParsedLine, SalesOpResult


class IgsaSalesPdfFlowService:
    def __init__(self) -> None:
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

    def import_igsa_pdf_lines(
        self,
        lines: list[IgsaPdfParsedLine],
        cliente_id: str = "",
        *,
        sync_warehouse_callback: Callable[[Session, list[VentaMensualRaw]], None] | None = None,
    ) -> SalesOpResult:
        from app.services.sales_reconciliation_service import SalesOpResult

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
            if sync_warehouse_callback is not None:
                sync_warehouse_callback(session, sync_rows)
            session.commit()

        return SalesOpResult(True, "Importacion PDF IGSA completada.", imported=len(lines) - skipped, incidencias=skipped)

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
            row = self._build_parsed_line(
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

    def _build_parsed_line(self, **kwargs: object):
        from app.services.sales_reconciliation_service import IgsaPdfParsedLine

        return IgsaPdfParsedLine(**kwargs)

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

    def _safe_json_dict(self, text: str) -> dict:
        raw = str(text or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _normalize_code(self, value) -> str:
        text = str(value or "").strip().upper()
        if not text:
            return ""
        if re.fullmatch(r"\d+(\.0+)?", text):
            return str(int(float(text)))
        return text

    def _normalize_search_text(self, value) -> str:
        text = str(value or "").strip().lower()
        normalized = unicodedata.normalize("NFD", text)
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return re.sub(r"\s+", " ", normalized)

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

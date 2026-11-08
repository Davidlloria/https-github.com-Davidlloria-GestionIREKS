"""Read-only comparison using the IGSA distributor and IREKS product catalog."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import unicodedata
from typing import Mapping

from openpyxl import load_workbook
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.services.igsa_monthly_catalog_service import load_igsa_monthly_catalog
from app.services.igsa_sales_pdf_flow_service import IgsaSalesPdfFlowService
from app.services.igsa_sales_workbook_flow_service import IgsaSalesWorkbookFlowService


@dataclass(frozen=True)
class SourceLocation:
    file: str
    sheet: str = ""
    row: int | None = None
    page: int | None = None
    item: int | None = None


@dataclass(frozen=True)
class ReviewIssue:
    code: str
    message: str
    location: SourceLocation | None = None


@dataclass(frozen=True)
class ReviewLine:
    source: str
    kind: str
    reference: str
    product: str
    description: str
    quantity: Decimal | None
    lot: str
    location: SourceLocation
    issue_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Balance:
    kind: str
    product: str
    lot: str | None
    igsa: Decimal | None
    ireks: Decimal | None
    difference: Decimal | None
    status: str
    locations: tuple[SourceLocation, ...]


@dataclass
class MonthlyReview:
    year: int
    month: int
    products: list[Balance] = field(default_factory=list)
    lots: list[Balance] = field(default_factory=list)
    issues: list[ReviewIssue] = field(default_factory=list)
    lines: list[ReviewLine] = field(default_factory=list)
    references: dict[str, str] = field(default_factory=dict)
    product_names: dict[str, str] = field(default_factory=dict)


def _text(value: object) -> str:
    return str(value if value is not None else "").strip()


def _key(value: object) -> str:
    return _text(value).upper()


def _sheet_kind(name: str) -> str | None:
    value = unicodedata.normalize("NFKD", name.casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    if "venta" in value:
        return "venta"
    if "promocion" in value or value.strip() in {"s/c", "sc"}:
        return "promocion"
    if "muestra" in value:
        return "muestra"
    return None


def _quantity(value: object) -> Decimal | None:
    try:
        result = Decimal(_text(value).replace(",", "."))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def _sample_metadata(value: object, *, first_lot: bool) -> bool:
    """Exclude sample dates and recipient names without hiding lot entries."""
    if isinstance(value, (date, datetime)):
        return True
    text = _text(value)
    if re.match(r"^(?:CAD(?:UCIDAD)?\b[.:\s-]*)", text, re.IGNORECASE):
        return True
    date_patterns = (
        r"\d{1,2}[/.-](?:0?[1-9]|1[0-2])[/.-](?:19|20)?\d{2}",
        r"(?:19|20)\d{2}[/.-](?:0?[1-9]|1[0-2])[/.-]\d{1,2}",
        r"(?:0?[1-9]|1[0-2])[/.-](?:19|20)\d{2}",
    )
    if any(re.fullmatch(pattern + r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?", text) for pattern in date_patterns):
        return True
    return not first_lot and bool(text) and all(c.isalpha() or c.isspace() for c in text)


class IgsaMonthlyReviewService:
    """Compare files using a read-only catalog snapshot, without importing data."""

    def __init__(self, *, catalog_provider=None):
        self._catalog_provider = catalog_provider or load_igsa_monthly_catalog

    def compare(
        self,
        workbook: Path,
        pdfs: Mapping[str, Path],
        *,
        year: int,
        month: int,
        aliases: Mapping[str, str] | None = None,
    ) -> MonthlyReview:
        if not 1 <= month <= 12 or not 1 <= year <= 9999:
            raise ValueError("El año o mes no es válido")
        allowed = {"venta", "promocion", "muestra"}
        if set(pdfs) - allowed:
            raise ValueError("Tipo de PDF no válido")
        alias_map = {_key(k): _key(v) for k, v in (aliases or {}).items()}
        if any(not k or not v for k, v in alias_map.items()):
            raise ValueError("Las equivalencias no pueden estar vacías")
        result = MonthlyReview(year=year, month=month)
        catalog = self._catalog_provider()
        result.references = {key: product.reference for key, product in catalog.products.items()}
        result.product_names = {key: product.description for key, product in catalog.products.items()}
        product_totals: list[ReviewLine] = []
        incomplete = self._read_workbook(Path(workbook), year, month, catalog, result, product_totals)
        for kind in sorted(allowed):
            if kind not in pdfs:
                result.issues.append(ReviewIssue("pdf_ausente", f"Falta PDF de {kind}"))
                incomplete.add(kind)
                continue
            if not self._read_pdf(Path(pdfs[kind]), kind, year, month, alias_map, catalog, result, product_totals):
                incomplete.add(kind)
        duplicates: dict[tuple, list[ReviewLine]] = defaultdict(list)
        for line in result.lines:
            duplicates[(line.source, line.kind, line.reference, line.lot, line.quantity)].append(line)
        duplicate_locations = set()
        for rows in duplicates.values():
            if len(rows) > 1:
                duplicate_locations.update(row.location for row in rows)
                for row in rows:
                    result.issues.append(ReviewIssue("posible_duplicado", "Líneas idénticas; comprobar antes de sumar", row.location))
        result.lines = [replace(row, issue_codes=row.issue_codes + ("posible_duplicado",)) if row.location in duplicate_locations else row for row in result.lines]
        product_totals = [replace(row, issue_codes=row.issue_codes + ("posible_duplicado",)) if row.location in duplicate_locations else row for row in product_totals]
        result.products = self._balances(product_totals, by_lot=False)
        result.lots = self._balances(result.lines, by_lot=True)
        result.products = [replace(row, status="fuente_incompleta") if row.kind in incomplete else row for row in result.products]
        result.lots = [replace(row, status="fuente_incompleta") if row.kind in incomplete else row for row in result.lots]
        return result

    def _read_workbook(self, path, year, month, catalog, result, totals):
        book = load_workbook(path, read_only=True, data_only=True)
        seen = set()
        incomplete = set()
        try:
            for sheet in book:
                kind = _sheet_kind(sheet.title)
                if not kind:
                    continue
                if kind in seen:
                    result.issues.append(ReviewIssue("hoja_duplicada", f"Varias hojas de {kind}", SourceLocation(path.name, sheet.title)))
                    incomplete.add(kind)
                    continue
                seen.add(kind)
                period = IgsaSalesWorkbookFlowService()._infer_period(sheet, path)
                if period and period != f"{year:04d}-{month:02d}":
                    result.issues.append(ReviewIssue("periodo", f"Hoja indica {period}; seleccionado {year:04d}-{month:02d}", SourceLocation(path.name, sheet.title)))
                    incomplete.add(kind)
                elif not period:
                    result.issues.append(ReviewIssue("periodo_excel_desconocido", "No se detectó el período de la hoja", SourceLocation(path.name, sheet.title)))
                    incomplete.add(kind)
                for number, row in enumerate(sheet.iter_rows(values_only=True), 1):
                    if len(row) < 5:
                        continue
                    qty = _quantity(row[4])
                    if qty is None:
                        label = _key(row[4])
                        if label and label not in {"COLUMNA5", "CANTIDAD", "TOTAL_UNIDADES", "UNIDADES"} and _text(row[0]) and _text(row[2]):
                            result.issues.append(ReviewIssue("cantidad_excel", f"Cantidad no reconocida: {_text(row[4])}", SourceLocation(path.name, sheet.title, number)))
                            incomplete.add(kind)
                        continue
                    if qty < 0:
                        result.issues.append(ReviewIssue("cantidad_excel", f"Cantidad negativa: {qty}", SourceLocation(path.name, sheet.title, number)))
                        incomplete.add(kind)
                        continue
                    if qty == 0:
                        continue
                    ref, description = _key(row[0]), _text(row[2])
                    loc = SourceLocation(path.name, sheet.title, number)
                    if not description:
                        result.issues.append(ReviewIssue("linea_incompleta", "Falta descripción", loc))
                        incomplete.add(kind)
                        continue
                    resolved, problem = catalog.distributor_product(ref)
                    if problem:
                        result.issues.append(ReviewIssue(problem, f"Referencia IGSA '{ref or 'vacía'}': {problem.replace('_', ' ')}", loc))
                    product = resolved.product_id if resolved else f"IGSA_SIN:{ref or f'{sheet.title}:{number}'}"
                    ref_flags = (problem,) if problem else ()
                    total = ReviewLine("igsa", kind, ref, product, description, qty, "", loc, ref_flags)
                    totals.append(total)
                    raw_lots = [
                        _text(value) for index, value in enumerate(row[5:])
                        if _text(value) and (kind != "muestra" or not _sample_metadata(value, first_lot=index == 0))
                    ]
                    parsed = []
                    for raw in raw_lots:
                        match = re.fullmatch(r"(?:(\d+(?:[.,]\d+)?)\s*)?[Ll]\s*\.?\s*([A-Za-z0-9][A-Za-z0-9-]*)", raw)
                        if match:
                            parsed.append((_quantity(match.group(1)) if match.group(1) else None, match.group(2), ()))
                        elif re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", raw):
                            parsed.append((None, raw, ()))
                        else:
                            parsed.append((None, raw, ("lote_no_reconocido",)))
                            result.issues.append(ReviewIssue("lote_no_reconocido", f"Lote no reconocido: {raw}", loc))
                    if len(parsed) == 1 and parsed[0][0] is None and not parsed[0][2]:
                        parsed[0] = (qty, parsed[0][1], ())
                    if not parsed:
                        parsed = [(None, "", ("sin_lote",))]
                        result.issues.append(ReviewIssue("sin_lote", "Línea sin lote", loc))
                    elif any(q is None for q, _, _ in parsed):
                        result.issues.append(ReviewIssue("reparto_desconocido", "No se puede determinar el reparto por lote", loc))
                        parsed = [(q, lot, flags + ("reparto_desconocido",)) for q, lot, flags in parsed]
                    elif sum((q for q, _, _ in parsed), Decimal(0)) != qty:
                        result.issues.append(ReviewIssue("reparto", f"Total {qty}; suma de lotes {sum(q for q, _, _ in parsed)}", loc))
                        parsed = [(q, lot, flags + ("reparto",)) for q, lot, flags in parsed]
                    if any(flags for _, _, flags in parsed) or any(q is None for q, _, _ in parsed):
                        totals[-1] = ReviewLine("igsa", kind, ref, product, description, qty, "", loc, ref_flags + ("reparto",))
                    for part, lot, flags in parsed:
                        result.lines.append(ReviewLine("igsa", kind, ref, product, description, part, lot, loc, ref_flags + flags))
            for kind in {"venta", "promocion", "muestra"} - seen:
                result.issues.append(ReviewIssue("hoja_ausente", f"Falta hoja de {kind}"))
                incomplete.add(kind)
        finally:
            book.close()
        return incomplete

    def _read_pdf(self, path, kind, year, month, aliases, catalog, result, totals):
        try:
            reader = PdfReader(str(path))
        except (OSError, ValueError, PdfReadError) as exc:
            result.issues.append(ReviewIssue("pdf_error", f"No se pudo abrir el PDF: {exc}", SourceLocation(path.name)))
            return False
        parser = IgsaSalesPdfFlowService()
        pattern = re.compile(parser._igsa_pdf_line_pattern.pattern.replace(
            r"(?P<cons_pref>\d{2}/\d{2}/\d{2})", r"(?P<cons_pref>\d{2}/\d{2}/\d{2})?"
        ), re.DOTALL)
        count = 0
        extracted = Decimal(0)
        expected = None
        missing_text = False
        invalid_period_or_type = False
        for page_number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            if not text.strip():
                missing_text = True
                result.issues.append(ReviewIssue("pdf_sin_texto", "Página sin texto extraíble", SourceLocation(path.name, page=page_number)))
                continue
            footer = re.search(r"Bultos:\s*Peso:\s*Portes:\s*([\d.]+)", text, re.I)
            if footer:
                expected = Decimal(footer.group(1).replace(".", ""))
            if page_number == 1:
                header = text.split("Fecha entrega:", 1)[0].upper()
                header = re.split(r"N[º°O.]?\s*PEDIDO", header, maxsplit=1)[0]
                detected = "muestra" if "MUESTRA" in header else "promocion" if "PROMOC" in header else "venta" if "VENTA" in header else ""
                if detected and detected != kind:
                    invalid_period_or_type = True
                    result.issues.append(ReviewIssue("tipo_pdf", f"PDF indica {detected}; seleccionado {kind}", SourceLocation(path.name, page=page_number)))
                dates = re.search(r"Ref\.\s*pedido:.*?(\d{2}/\d{2}/\d{2})", text, re.I | re.S)
                if dates:
                    try:
                        date = datetime.strptime(dates.group(1), "%d/%m/%y")
                    except ValueError:
                        invalid_period_or_type = True
                        result.issues.append(ReviewIssue("periodo_pdf_invalido", f"Fecha PDF inválida: {dates.group(1)}", SourceLocation(path.name, page=page_number)))
                    else:
                        if (date.year, date.month) != (year, month):
                            invalid_period_or_type = True
                            result.issues.append(ReviewIssue("periodo", f"PDF indica {date:%Y-%m}; seleccionado {year:04d}-{month:02d}", SourceLocation(path.name, page=page_number)))
                else:
                    result.issues.append(ReviewIssue("periodo_pdf_desconocido", "No se detectó la fecha del PDF", SourceLocation(path.name, page=page_number)))
                    invalid_period_or_type = True
            start = text.find("Fecha entrega:")
            body = text[start + len("Fecha entrega:"):] if start >= 0 else text
            matches = list(pattern.finditer(body))
            lot_markers = len(re.findall(r"Lote\s*:", body, re.I))
            if lot_markers != len(matches):
                missing_text = True
                result.issues.append(ReviewIssue(
                    "lineas_pdf_incompletas",
                    f"Página con {lot_markers} lotes y {len(matches)} líneas reconocidas",
                    SourceLocation(path.name, page=page_number),
                ))
            for index, match in enumerate(matches, 1):
                count += 1
                ref = _key(match.group("codigo"))
                loc = SourceLocation(path.name, page=page_number, item=index)
                quantity = _quantity(match.group("env").replace(".", ""))
                if quantity is None:
                    result.issues.append(ReviewIssue("cantidad_pdf", "Cantidad PDF no reconocida", loc))
                    missing_text = True
                    continue
                extracted += quantity
                resolved, problem = catalog.ireks_product(aliases.get(ref, ref))
                if problem:
                    result.issues.append(ReviewIssue(problem, f"Referencia IREKS '{ref}': {problem.replace('_', ' ')}", loc))
                elif catalog.is_ireks_zero_normalized(aliases.get(ref, ref)):
                    result.issues.append(ReviewIssue(
                        "referencia_normalizada",
                        f"Referencia PDF '{ref}' coincide con '{resolved.reference}' al quitar ceros iniciales; coincidencia única en catálogo",
                        loc,
                    ))
                product = resolved.product_id if resolved else f"IREKS_SIN:{ref}"
                row = ReviewLine("ireks", kind, ref, product, _text(match.group("descripcion")), quantity, _text(match.group("lote")), loc, (problem,) if problem else ())
                if not match.group("cons_pref"):
                    result.issues.append(ReviewIssue("caducidad_pdf_ausente", "Línea PDF sin fecha de consumo preferente", loc))
                result.lines.append(row)
                totals.append(row)
        if not count:
            result.issues.append(ReviewIssue("pdf_sin_lineas", "No se detectaron líneas en el PDF", SourceLocation(path.name)))
        if expected is None:
            result.issues.append(ReviewIssue("total_pdf_desconocido", "No se pudo comprobar el total de bultos del PDF", SourceLocation(path.name)))
        elif expected != extracted:
            result.issues.append(ReviewIssue("total_pdf", f"Bultos PDF: {expected}; líneas extraídas: {extracted}", SourceLocation(path.name)))
        return count > 0 and not missing_text and not invalid_period_or_type and expected is not None and expected == extracted

    @staticmethod
    def _balances(lines: list[ReviewLine], *, by_lot: bool) -> list[Balance]:
        groups: dict[tuple[str, str, str | None], list[ReviewLine]] = defaultdict(list)
        for line in lines:
            groups[(line.kind, line.product, line.lot if by_lot else None)].append(line)
        output = []
        for (kind, product, lot), rows in sorted(groups.items()):
            sides = {source: [r for r in rows if r.source == source] for source in ("igsa", "ireks")}
            def amount(items):
                return sum((r.quantity for r in items), Decimal(0)) if items and all(r.quantity is not None for r in items) else None
            left, right = amount(sides["igsa"]), amount(sides["ireks"])
            delta = left - right if left is not None and right is not None else None
            if any("referencia_ambigua" in r.issue_codes or "referencia_compartida" in r.issue_codes for r in rows):
                status = "referencia_ambigua"
            elif any(any(flag in r.issue_codes for flag in ("referencia_no_encontrada", "producto_sin_referencia")) for r in rows):
                status = "sin_correspondencia"
            elif any("posible_duplicado" in r.issue_codes for r in rows):
                status = "posible_duplicado"
            elif any(r.issue_codes for r in rows):
                status = "revisar_reparto"
            elif delta is None:
                status = "sin_correspondencia"
            else:
                status = "correcto" if delta == 0 else "diferencia"
            output.append(Balance(kind, product, lot, left, right, delta, status, tuple(r.location for r in rows)))
        return output

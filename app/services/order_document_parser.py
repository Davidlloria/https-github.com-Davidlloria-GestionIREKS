from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import fitz
from pypdf import PdfReader

from app.services.order_document_factura_sidecar_service import OrderDocumentFacturaSidecarService
from app.services.order_document_ocr_runtime_service import OrderDocumentOcrRuntimeService


class OrderDocumentParser:
    """Parsing helpers for order, delivery-note and invoice documents.

    This service is intentionally UI-free so it can later be reused from
    FastAPI endpoints or background jobs.
    """

    @staticmethod
    def normalize_invoice_number_token(value: str) -> str:
        return re.sub(r"\s+", "", str(value or "").strip())

    @staticmethod
    def parse_decimal_es(value: object, default: float = 0.0) -> float:
        text_value = OrderDocumentParser.normalize_invoice_number_token(str(value or ""))
        if not text_value:
            return default
        if "," not in text_value and "." in text_value:
            parts = text_value.split(".")
            if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
                try:
                    return float(text_value)
                except Exception:
                    return default
        try:
            return float(text_value.replace(".", "").replace(",", "."))
        except Exception:
            return default

    @staticmethod
    def format_number_es(value: float, decimals: int = 2, suffix: str = "") -> str:
        base = f"{float(value):,.{decimals}f}"
        base = base.replace(",", "_").replace(".", ",").replace("_", ".")
        return f"{base}{suffix}"

    @staticmethod
    def _normalize_invoice_number_token(value: str) -> str:
        return OrderDocumentParser.normalize_invoice_number_token(value)

    @staticmethod
    def _parse_decimal_es_static(value: object, default: float = 0.0) -> float:
        return OrderDocumentParser.parse_decimal_es(value, default)

    @staticmethod
    def _format_number_es_static(value: float, decimals: int = 2, suffix: str = "") -> str:
        return OrderDocumentParser.format_number_es(value, decimals, suffix)

    @staticmethod
    def article_code_candidates(codigo: str) -> list[str]:
        clean = str(codigo or "").strip().upper()
        if not clean:
            return []
        candidates = [clean]
        if clean.isdigit():
            no_leading_zeros = clean.lstrip("0") or "0"
            candidates.append(no_leading_zeros)
            candidates.append(no_leading_zeros.zfill(5))
            candidates.append(no_leading_zeros.zfill(6))
        return list(dict.fromkeys(candidates))

    @staticmethod
    def parse_albaran_pdf(file_path: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
        lines: list[str] = []
        try:
            doc = fitz.open(str(file_path))
            for page in doc:
                page_text = page.get_text() or ""
                lines.extend([str(x or "").strip() for x in page_text.splitlines() if str(x or "").strip()])
        except Exception:
            reader = PdfReader(str(file_path))
            full_text = "\n".join((page.extract_text() or "") for page in reader.pages)
            lines = [str(x or "").strip() for x in full_text.splitlines() if str(x or "").strip()]

        if not lines:
            raise ValueError("No se pudo extraer texto del PDF.")

        def next_match(start_idx: int, regex: str, lookahead: int = 8) -> str:
            rx = re.compile(regex, flags=re.IGNORECASE)
            for pos in range(start_idx + 1, min(start_idx + 1 + lookahead, len(lines))):
                match = rx.search(lines[pos])
                if match:
                    return str(match.group(1) or "").strip()
            return ""

        def next_dates(start_idx: int, lookahead: int = 12) -> list[str]:
            out: list[str] = []
            rx = re.compile(r"([0-9]{2}/[0-9]{2}/[0-9]{2,4})")
            for pos in range(start_idx + 1, min(start_idx + 1 + lookahead, len(lines))):
                match = rx.search(lines[pos])
                if match:
                    out.append(str(match.group(1) or "").strip())
            return out

        idx_numero = next((idx for idx, line in enumerate(lines) if re.search(r"N[úu]mero\s*:", line, re.IGNORECASE)), -1)
        idx_fecha = next((idx for idx, line in enumerate(lines) if re.search(r"^Fecha\s*:", line, re.IGNORECASE)), -1)
        idx_fecha_pedido = next(
            (idx for idx, line in enumerate(lines) if re.search(r"Fecha\s+pedido\s*:", line, re.IGNORECASE)), -1
        )
        idx_pedido = next((idx for idx, line in enumerate(lines) if re.search(r"N[ºo]\s*Pedido\s*:", line, re.IGNORECASE)), -1)

        header = {
            "albaran_numero": next_match(idx_numero, r"([0-9]{6,})") if idx_numero >= 0 else "",
            "albaran_fecha": next_match(idx_fecha, r"([0-9]{2}/[0-9]{2}/[0-9]{2,4})") if idx_fecha >= 0 else "",
            "fecha_pedido": "",
            "pedido_numero": next_match(idx_pedido, r"([0-9]+)") if idx_pedido >= 0 else "",
        }
        if idx_fecha_pedido >= 0:
            dates_after_fecha_pedido = next_dates(idx_fecha_pedido, lookahead=14)
            if dates_after_fecha_pedido:
                header["fecha_pedido"] = dates_after_fecha_pedido[-1]
        if not header["albaran_numero"]:
            raise ValueError("No se encontró el número de albarán en el PDF.")
        if not header["albaran_fecha"]:
            raise ValueError("No se encontró la fecha del albarán en el PDF.")

        item_source_lines: list[str] = []
        try:
            doc = fitz.open(str(file_path))
            for page in doc:
                page_text = page.get_text() or ""
                page_lines = [str(x or "").strip() for x in page_text.splitlines() if str(x or "").strip()]
                table_start = next(
                    (
                        pos
                        for pos, line in enumerate(page_lines)
                        if re.search(r"^C[oó]d\.?\s*Art\.?$", line, re.IGNORECASE)
                    ),
                    -1,
                )
                if table_start < 0:
                    continue
                body_start = table_start + 1
                idx_fecha_entrega = next(
                    (
                        pos
                        for pos in range(table_start + 1, len(page_lines))
                        if re.search(r"^Fecha\s+entrega\s*:", page_lines[pos], re.IGNORECASE)
                    ),
                    -1,
                )
                if idx_fecha_entrega >= 0:
                    body_start = idx_fecha_entrega + 1
                    if body_start < len(page_lines) and re.fullmatch(r"\d{2}/\d{2}/\d{2,4}", page_lines[body_start]):
                        body_start += 1
                for line in page_lines[body_start:]:
                    clean_line = re.sub(r"\s+", " ", line).strip()
                    if re.search(
                        r"^(Datos\s+transporte|Observaciones|DIRECCI[OÓ]N\s+DE\s+ENV[IÍ]O|IREKS\s+IBERICA|IREKS\s+IB[ÉE]RICA|personales,|tal\s+fin,|datos@|Operador\s+CT/)",
                        clean_line,
                        re.IGNORECASE,
                    ):
                        break
                    item_source_lines.append(clean_line)
        except Exception:
            item_source_lines = lines

        item_rows: list[dict[str, Any]] = []
        idx = 0
        code_rx = re.compile(r"^(?:\d{3,8}|[A-Z]{1,2}\d{4,8})$")
        kilos_rx = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d{2}$")
        envases_rx = re.compile(r"^\d+(?:,\d+)?$")

        def looks_like_item_start(pos: int) -> bool:
            if pos + 3 >= len(item_source_lines):
                return False
            return bool(
                code_rx.match(item_source_lines[pos])
                and kilos_rx.match(item_source_lines[pos + 2].strip())
                and envases_rx.match(item_source_lines[pos + 3].strip())
            )

        while idx < len(item_source_lines):
            if not code_rx.match(item_source_lines[idx]):
                idx += 1
                continue
            codigo = item_source_lines[idx]
            if idx + 3 >= len(item_source_lines):
                idx += 1
                continue
            descripcion = item_source_lines[idx + 1]
            kilos = item_source_lines[idx + 2].strip()
            envases = item_source_lines[idx + 3].strip()
            if not kilos_rx.match(kilos) or not envases_rx.match(envases):
                idx += 1
                continue
            lote = ""
            cad = ""
            scan_to = min(idx + 14, len(item_source_lines))
            scan_pos = idx + 4
            while scan_pos < scan_to:
                token = item_source_lines[scan_pos]
                token_norm = re.sub(r"\s+", "", token).lower()
                if looks_like_item_start(scan_pos):
                    break
                if "lote" in token_norm:
                    if scan_pos + 1 < scan_to:
                        lote = item_source_lines[scan_pos + 1].strip()
                if "cons.pref" in token_norm or "conspref" in token_norm:
                    if scan_pos + 1 < scan_to:
                        cad = item_source_lines[scan_pos + 1].strip()
                scan_pos += 1
            item_rows.append(
                {
                    "albaran_numero": header["albaran_numero"],
                    "albaran_fecha": header["albaran_fecha"],
                    "pedido_numero": header["pedido_numero"],
                    "articulo_codigo": codigo,
                    "articulo_descripcion": descripcion,
                    "articulo_kilos": kilos,
                    "articulo_cantidad": envases,
                    "articulo_lote": lote,
                    "articulo_caducidad": cad,
                }
            )
            idx = scan_pos if scan_pos > idx else idx + 1
        if not item_rows:
            raise ValueError("No se encontraron líneas de artículos en el PDF.")
        return header, item_rows

    @staticmethod
    def parse_factura_pdf(file_path: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
        return OrderDocumentParser._parse_factura_pdf(None, file_path)

    @staticmethod
    def _line_value_after_label(lines: list[str], label_regex: str, value_regex: str, lookahead: int = 4) -> str:
        label_rx = re.compile(label_regex, flags=re.IGNORECASE)
        value_rx = re.compile(value_regex, flags=re.IGNORECASE)
        for idx, line in enumerate(lines):
            label_match = label_rx.search(line)
            if not label_match:
                continue
            after_label = line[label_match.end() :].strip()
            value_match = value_rx.search(after_label)
            if value_match:
                return str(value_match.group(1) or "").strip()
            for pos in range(idx + 1, min(idx + 1 + lookahead, len(lines))):
                value_match = value_rx.search(lines[pos])
                if value_match:
                    return str(value_match.group(1) or "").strip()
        return ""

    @staticmethod
    def _extract_factura_numero_from_header_words(doc: Any) -> str:
        for page in doc:
            candidates: list[tuple[float, str]] = []
            for word in page.get_text("words"):
                x0, y0, _x1, _y1, text = word[:5]
                value = str(text or "").strip()
                if 75 <= float(x0) <= 135 and 150 <= float(y0) <= 210 and re.fullmatch(r"[0-9]{4,}", value):
                    candidates.append((float(y0), value))
            if candidates:
                return sorted(candidates, key=lambda item: item[0])[0][1]
        return ""

    @staticmethod
    def _extract_factura_fecha_from_header_words(doc: Any) -> str:
        for page in doc:
            candidates: list[tuple[float, str]] = []
            for word in page.get_text("words"):
                x0, y0, _x1, _y1, text = word[:5]
                value = str(text or "").strip()
                if 75 <= float(x0) <= 145 and 160 <= float(y0) <= 220 and re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{2,4}", value):
                    candidates.append((float(y0), value))
            if candidates:
                return sorted(candidates, key=lambda item: item[0])[0][1]
        return ""

    @staticmethod
    def _extract_factura_referencia_from_header_words(doc: Any) -> str:
        for page in doc:
            candidates = [
                word
                for word in page.get_text("words")
                if 320 <= float(word[0]) <= 470 and 192 <= float(word[1]) <= 210
            ]
            if candidates:
                return " ".join(str(word[4] or "").strip() for word in sorted(candidates, key=lambda item: float(item[0]))).strip()
        return ""

    @staticmethod
    def _extract_factura_albaran_from_header_words(doc: Any) -> str:
        for page in doc:
            candidates: list[tuple[float, str]] = []
            for word in page.get_text("words"):
                x0, y0, _x1, _y1, text = word[:5]
                value = str(text or "").strip()
                if 300 <= float(x0) <= 470 and 150 <= float(y0) <= 230 and re.fullmatch(r"[0-9]{6,}", value):
                    candidates.append((float(y0), value))
            if candidates:
                return sorted(candidates, key=lambda item: item[0])[-1][1]
        return ""

    @staticmethod
    def _words_to_factura_lines(words: list[Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for word in sorted(words, key=lambda x: (float(x[1]), float(x[0]))):
            x0, y0, _x1, _y1, text = word[:5]
            if float(y0) < 100 or float(y0) > 760:
                continue
            placed = False
            for line in out:
                if abs(float(line["y"]) - float(y0)) < 3.0:
                    line["words"].append(word)
                    line["y"] = (float(line["y"]) * int(line["n"]) + float(y0)) / (int(line["n"]) + 1)
                    line["n"] = int(line["n"]) + 1
                    placed = True
                    break
            if not placed:
                out.append({"y": float(y0), "n": 1, "words": [word]})
        return sorted(out, key=lambda line: float(line["y"]))

    @staticmethod
    def _factura_line_text(line: dict[str, Any]) -> str:
        return " ".join(str(w[4] or "") for w in sorted(line["words"], key=lambda x: float(x[0]))).strip()

    @staticmethod
    def _factura_column_text(line: dict[str, Any], left: float, right: float) -> str:
        values = [
            str(w[4] or "")
            for w in sorted(line["words"], key=lambda x: float(x[0]))
            if left <= float(w[0]) < right
        ]
        return OrderDocumentParser._normalize_invoice_number_token("".join(values)) if left >= 420 else " ".join(values).strip()

    @staticmethod
    def _factura_value_at(line: dict[str, Any], left: float, right: float) -> str:
        return OrderDocumentParser._normalize_invoice_number_token(OrderDocumentParser._factura_column_text(line, left, right))

    @staticmethod
    def _factura_line_has_article_code(line: dict[str, Any], code_rx: re.Pattern[str]) -> bool:
        return any(float(w[0]) < 65 and code_rx.fullmatch(str(w[4] or "").strip()) for w in line["words"])

    @staticmethod
    def _extract_factura_lote_from_follow_line(line: dict[str, Any]) -> str:
        text = OrderDocumentParser._factura_line_text(line)
        lote_match = re.search(r"Lote:\s*([A-Z0-9./-]+)", text, flags=re.IGNORECASE)
        if lote_match:
            return str(lote_match.group(1) or "").strip()

        date_rx = re.compile(r"^[0-9]{2}/[0-9]{2}/[0-9]{2,4}$")
        candidates = [
            str(w[4] or "").strip()
            for w in sorted(line["words"], key=lambda x: float(x[0]))
            if 95 <= float(w[0]) <= 170
        ]
        for token in candidates:
            clean = token.strip("~ ")
            if date_rx.fullmatch(clean):
                continue
            if re.fullmatch(r"[A-Z0-9][A-Z0-9./-]{5,}", clean):
                return clean
        return ""

    @staticmethod
    def _extract_factura_caducidad_from_follow_line(line: dict[str, Any]) -> str:
        text = OrderDocumentParser._factura_line_text(line)
        cad_match = re.search(r"\bCad\S{0,12}:\s*([0-9]{2}/[0-9]{2}/[0-9]{2,4})", text, flags=re.IGNORECASE)
        if cad_match:
            return str(cad_match.group(1) or "").strip()
        words = sorted(line["words"], key=lambda x: float(x[0]))
        loose_date = next(
            (
                str(w[4] or "").strip()
                for w in words
                if 105 <= float(w[0]) <= 170
                and re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{2,4}", str(w[4] or "").strip())
            ),
            "",
        )
        if loose_date:
            return loose_date
        split_date_parts = [
            str(w[4] or "").strip()
            for w in words
            if 105 <= float(w[0]) <= 170
        ]
        for pos in range(len(split_date_parts) - 1):
            joined = f"{split_date_parts[pos]}{split_date_parts[pos + 1]}".strip()
            if re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{2,4}", joined):
                return joined
        has_cad_label = any(
            60 <= float(w[0]) <= 105 and str(w[4] or "").strip().lower().startswith("cad")
            for w in words
        )
        if not has_cad_label:
            return ""
        date_match = re.search(r"([0-9]{2}/[0-9]{2}/[0-9]{2,4})", text)
        return str(date_match.group(1) or "").strip() if date_match else ""

    @staticmethod
    def _merge_factura_sidecar_rows(file_path: Path, header: dict[str, str], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sidecar_rows = OrderDocumentFacturaSidecarService().load_rows(file_path, header.get("factura_numero") or "", header)
        if not sidecar_rows:
            return rows
        parsed_by_lote = {str(row.get("articulo_lote") or "").strip(): row for row in rows if str(row.get("articulo_lote") or "").strip()}
        merged: list[dict[str, Any]] = []
        used_lotes: set[str] = set()
        for sidecar in sidecar_rows:
            lote = str(sidecar.get("articulo_lote") or "").strip()
            parsed = parsed_by_lote.get(lote) if lote else None
            if parsed is None and lote:
                parsed = OrderDocumentParser._recover_factura_sidecar_row_with_ocr(file_path, sidecar)
            if lote and lote in parsed_by_lote:
                merged.append(parsed_by_lote[lote])
                used_lotes.add(lote)
            elif parsed is not None:
                merged.append(parsed)
                used_lotes.add(lote)
            else:
                merged.append(sidecar)
        for row in rows:
            lote = str(row.get("articulo_lote") or "").strip()
            if not lote or lote not in used_lotes:
                merged.append(row)
        return merged

    @staticmethod
    def _recover_factura_sidecar_row_with_ocr(file_path: Path, sidecar: dict[str, Any]) -> dict[str, Any] | None:
        lote = str(sidecar.get("articulo_lote") or "").strip()
        if not lote:
            return None
        try:
            doc = fitz.open(str(file_path))
        except Exception:
            return None
        try:
            for page in doc:
                for word in page.get_text("words"):
                    if str(word[4] or "").strip() != lote:
                        continue
                    row = OrderDocumentParser._ocr_factura_article_line(
                        page,
                        float(word[1]),
                        {
                            "factura_numero": str(sidecar.get("factura_numero") or "").strip(),
                            "factura_fecha": str(sidecar.get("factura_fecha") or "").strip(),
                            "albaran_numero": str(sidecar.get("albaran_numero") or "").strip(),
                            "factura_referencia": str(sidecar.get("factura_referencia") or "").strip(),
                        },
                        lote,
                        str(sidecar.get("articulo_caducidad") or "").strip(),
                    )
                    if row is not None:
                        row["_source_y"] = float(word[1]) - 20.0
                    return row
        finally:
            doc.close()
        return None

    @staticmethod
    def _parse_factura_ocr_article_line(text: str, header: dict[str, str], lote: str, caducidad: str) -> dict[str, Any] | None:
        return OrderDocumentParser.parse_factura_ocr_article_line(text, header, lote, caducidad)

    @staticmethod
    def _ocr_factura_article_line(page: Any, lote_line_y: float, header: dict[str, str], lote: str, caducidad: str) -> dict[str, Any] | None:
        runtime_service = OrderDocumentOcrRuntimeService()
        runtime_state = runtime_service.resolve_runtime()
        if not runtime_state.configured:
            return None
        try:
            import pytesseract
            from PIL import Image, ImageOps
        except Exception:
            return None
        try:
            lang = runtime_state.ocr_lang
            for top_offset, bottom_offset in ((20.0, 2.0), (28.0, 2.0), (30.0, 10.0), (25.0, -3.0)):
                top = max(100.0, float(lote_line_y) - top_offset)
                bottom = max(top + 12.0, float(lote_line_y) + bottom_offset)
                clip = fitz.Rect(18, top, 575, min(float(page.rect.height), bottom))
                pix = page.get_pixmap(matrix=fitz.Matrix(5, 5), clip=clip, alpha=False)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                image = ImageOps.grayscale(image)
                image = ImageOps.autocontrast(image)
                image = image.point(lambda px: 255 if px > 170 else 0)
                if lang:
                    text = pytesseract.image_to_string(image, lang=lang, config="--psm 6")
                else:
                    text = pytesseract.image_to_string(image, config="--psm 6")
                row = OrderDocumentParser._parse_factura_ocr_article_line(text, header, lote, caducidad)
                if row is not None:
                    return row
        except Exception:
            return None
        return None

    @staticmethod
    def _recover_factura_orphan_rows_with_ocr(
        doc: Any,
        header: dict[str, str],
        all_item_lines: list[dict[str, Any]],
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        def has_core_fields(row: dict[str, Any]) -> bool:
            return all(
                str(row.get(field) or "").strip()
                for field in (
                    "articulo_codigo",
                    "articulo_descripcion",
                    "articulo_cantidad",
                    "articulo_envase",
                    "articulo_kilos",
                    "precio_unitario",
                    "total_linea",
                )
            )

        parsed_lotes = {
            str(row.get("articulo_lote") or "").strip()
            for row in rows
            if str(row.get("articulo_lote") or "").strip() and has_core_fields(row)
        }
        recovered: list[dict[str, Any]] = []
        for line_idx, line in enumerate(all_item_lines):
            text = str(line.get("text") or "")
            normalized_text = re.sub(r"\s+", "", text).lower()
            lote = ""
            words = sorted(line.get("words", []), key=lambda x: float(x[0]))
            candidates = [str(w[4] or "").strip() for w in words if 95 <= float(w[0]) <= 170]
            for token in candidates:
                if re.fullmatch(r"[A-Z0-9][A-Z0-9./-]{4,}", token):
                    lote = token
                    break
            if not lote or ("lote" not in normalized_text and "carga" not in normalized_text):
                if not lote:
                    continue
            if not lote or lote in parsed_lotes:
                continue
            caducidad = ""
            for follow in all_item_lines[line_idx + 1 : line_idx + 4]:
                follow_text = " ".join(str(w[4] or "") for w in sorted(follow.get("words", []), key=lambda x: float(x[0])))
                normalized_follow_text = re.sub(r"\s*/\s*", "/", follow_text)
                match = re.search(r"([0-9]{2}/[0-9]{2}/[0-9]{2,4})", normalized_follow_text)
                if match:
                    caducidad = str(match.group(1) or "").strip()
                    break
            page_idx = int(float(line.get("global_y", 0.0)) // 10000.0)
            if page_idx < 0 or page_idx >= len(doc):
                continue
            row = OrderDocumentParser._ocr_factura_article_line(doc[page_idx], float(line.get("y", 0.0)), header, lote, caducidad)
            if row is not None:
                row["_source_y"] = float(line.get("global_y", 0.0)) - 20.0
                recovered.append(row)
                parsed_lotes.add(lote)
        if not recovered:
            return rows
        by_lote = {str(row.get("articulo_lote") or "").strip(): row for row in recovered if str(row.get("articulo_lote") or "").strip()}
        merged: list[dict[str, Any]] = []
        inserted_lotes: set[str] = set()
        for row in rows:
            lote = str(row.get("articulo_lote") or "").strip()
            if lote and lote in by_lote:
                if lote not in inserted_lotes:
                    merged.append(by_lote[lote])
                    inserted_lotes.add(lote)
                continue
            merged.append(row)
        for line in all_item_lines:
            lote = ""
            words = sorted(line.get("words", []), key=lambda x: float(x[0]))
            normalized_text = re.sub(r"\s+", "", str(line.get("text") or "")).lower()
            if "lote" in normalized_text or "carga" in normalized_text:
                for token in [str(w[4] or "").strip() for w in words if 95 <= float(w[0]) <= 170]:
                    if re.fullmatch(r"[A-Z0-9][A-Z0-9./-]{4,}", token):
                        lote = token
                        break
            if lote and lote in by_lote and lote not in inserted_lotes:
                merged.append(by_lote[lote])
                inserted_lotes.add(lote)
        return merged

    def _parse_factura_pdf(self, file_path: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
        try:
            doc = fitz.open(str(file_path))
        except Exception as exc:
            raise ValueError(f"No se pudo abrir el PDF: {exc}") from exc

        page_texts = [page.get_text() or "" for page in doc]
        full_text = "\n".join(page_texts)
        lines = [str(x or "").strip() for x in full_text.splitlines() if str(x or "").strip()]
        if not lines:
            raise ValueError("No se pudo extraer texto del PDF.")

        header = {
            "factura_numero": OrderDocumentParser._line_value_after_label(lines, r"N[úu]mero\s*:", r"([0-9]{4,})"),
            "factura_fecha": OrderDocumentParser._line_value_after_label(lines, r"^Fecha\s*:", r"([0-9]{2}/[0-9]{2}/[0-9]{2,4})"),
            "albaran_numero": OrderDocumentParser._line_value_after_label(lines, r"Alba\S*[:n]\s*:", r"([0-9]{6,})"),
            "factura_referencia": OrderDocumentParser._line_value_after_label(lines, r"Referencia\s*:", r"(.+)", lookahead=2),
            "total_kilos": OrderDocumentParser._line_value_after_label(lines, r"TOTAL\s+KILOS\s*:", r"([0-9.]+,[0-9]{2})"),
            "importe_neto": OrderDocumentParser._line_value_after_label(lines, r"IMPORTE\s+NETO\s*:", r"([0-9.]+,[0-9]{2})"),
            "total_factura": OrderDocumentParser._line_value_after_label(lines, r"TOTAL\s*:", r"([0-9.]+,[0-9]{2})"),
        }
        if not header["factura_numero"]:
            header["factura_numero"] = OrderDocumentParser._extract_factura_numero_from_header_words(doc)
        if not header["factura_fecha"]:
            header["factura_fecha"] = OrderDocumentParser._extract_factura_fecha_from_header_words(doc)
        if not header["albaran_numero"]:
            header["albaran_numero"] = OrderDocumentParser._extract_factura_albaran_from_header_words(doc)
        if not header["factura_referencia"] or "albar" in header["factura_referencia"].lower():
            header["factura_referencia"] = OrderDocumentParser._extract_factura_referencia_from_header_words(doc)
        if not header["total_factura"]:
            header["total_factura"] = header["importe_neto"]
        if not header["factura_numero"]:
            raise ValueError("No se encontró el número de factura en el PDF.")
        if not header["factura_fecha"]:
            raise ValueError("No se encontró la fecha de factura en el PDF.")

        code_rx = re.compile(r"^(?:\d{3,8}|[A-Z]{1,2}\d{4,8})$")
        item_rows: list[dict[str, Any]] = []
        all_item_lines: list[dict[str, Any]] = []
        for page_idx, page in enumerate(doc):
            page_lines = OrderDocumentParser._words_to_factura_lines(page.get_text("words"))
            table_header_y = next(
                (
                    float(line["y"])
                    for line in page_lines
                    if any(str(w[4] or "").strip().lower().startswith("código") for w in line["words"])
                    and any(str(w[4] or "").strip().lower().startswith("descripción") for w in line["words"])
                ),
                235.0,
            )
            for line in page_lines:
                if float(line["y"]) <= table_header_y + 5:
                    continue
                text = " ".join(str(w[4] or "") for w in sorted(line["words"], key=lambda x: float(x[0]))).strip()
                if not text:
                    continue
                if re.search(
                    r"^(IREKS|Tel\.|IVA$|TOTAL\s+KILOS|CONDICIO|IMPORTE|DESCUENTO|Base\s+|FORMA\s+DE\s+PAGO|TOTAL:|TIPO\s+ENVASE|BU\s*TOS|Operador\s+CT/)",
                    text,
                    flags=re.IGNORECASE,
                ):
                    continue
                row = dict(line)
                row["global_y"] = float(page_idx) * 10000.0 + float(line["y"])
                row["text"] = text
                all_item_lines.append(row)

        all_item_lines.sort(key=lambda line: float(line["global_y"]))
        for line_idx, line in enumerate(all_item_lines):
                words = sorted(line["words"], key=lambda x: float(x[0]))
                code = next(
                    (
                        str(w[4] or "").strip()
                        for w in words
                        if float(w[0]) < 65 and code_rx.fullmatch(str(w[4] or "").strip())
                    ),
                    "",
                )
                if not code:
                    continue
                description = OrderDocumentParser._factura_column_text(line, 65, 245)
                if not description or description.upper().startswith("TIPO ENVASE"):
                    continue
                lote = ""
                caducidad = ""
                for follow in all_item_lines[line_idx + 1 : line_idx + 12]:
                    if OrderDocumentParser._factura_line_has_article_code(follow, code_rx):
                        break
                    if not lote:
                        lote = OrderDocumentParser._extract_factura_lote_from_follow_line(follow)
                    if not caducidad:
                        caducidad = OrderDocumentParser._extract_factura_caducidad_from_follow_line(follow)
                    if lote and caducidad:
                        break
                uds_raw = OrderDocumentParser._factura_value_at(line, 285, 322)
                env_raw = OrderDocumentParser._factura_value_at(line, 322, 362)
                kilos_raw = OrderDocumentParser._factura_value_at(line, 362, 418)
                uds_value = OrderDocumentParser._parse_decimal_es_static(uds_raw, 0.0)
                env_value = OrderDocumentParser._parse_decimal_es_static(env_raw, 0.0)
                kilos_value = OrderDocumentParser._parse_decimal_es_static(kilos_raw, 0.0)
                if not uds_raw and env_value > 0 and kilos_value > 0:
                    uds_raw = OrderDocumentParser._format_number_es_static(kilos_value / env_value, 0)
                if not kilos_raw:
                    if uds_value > 0 and env_value > 0:
                        kilos_raw = OrderDocumentParser._format_number_es_static(uds_value * env_value, 2)
                item_rows.append(
                    {
                        "factura_numero": header["factura_numero"],
                        "factura_fecha": header["factura_fecha"],
                        "albaran_numero": header["albaran_numero"],
                        "factura_referencia": header["factura_referencia"],
                        "articulo_codigo": code,
                        "articulo_descripcion": description,
                        "articulo_cantidad": uds_raw,
                        "articulo_envase": env_raw,
                        "articulo_kilos": kilos_raw,
                        "articulo_lote": lote,
                        "articulo_caducidad": caducidad,
                        "precio_unitario": OrderDocumentParser._factura_value_at(line, 420, 460),
                        "dto_pct": OrderDocumentParser._factura_value_at(line, 460, 492) or "20",
                        "iva_pct": OrderDocumentParser._factura_value_at(line, 545, 575),
                        "total_linea": OrderDocumentParser._factura_value_at(line, 492, 545),
                        "_source_y": float(line.get("global_y", 0.0)),
                    }
                )

        item_rows = OrderDocumentParser._recover_factura_orphan_rows_with_ocr(doc, header, all_item_lines, item_rows)
        item_rows = OrderDocumentParser._merge_factura_sidecar_rows(file_path, header, item_rows)
        item_rows.sort(key=lambda row: float(row.get("_source_y", 1_000_000_000.0)))
        if not item_rows:
            raise ValueError("No se encontraron líneas de artículos en el PDF.")
        return header, item_rows


    @staticmethod
    def parse_factura_ocr_article_line(
        text: str,
        header: dict[str, str],
        lote: str,
        caducidad: str,
    ) -> dict[str, Any] | None:
        clean = re.sub(r"\s+", " ", str(text or "")).strip()
        if not clean:
            return None
        code_match = re.search(r"\b(?:\d{3,8}|[A-Z]{1,2}\d{4,8})\b", clean)
        if not code_match:
            return None
        code = str(code_match.group(0) or "").strip()
        tail = clean[code_match.end() :].strip()
        um_match = re.search(r"\b(?:KG|K6|KQ|KC|UN|LUN)\b", tail, flags=re.IGNORECASE)
        if not um_match:
            return None
        description = tail[: um_match.start()].replace("|", " ").strip(" -:;")
        numeric_tail = tail[um_match.end() :]
        numbers = re.findall(r"\d+(?:[.,]\d{3})*[.,]\d{1,2}|\d+", numeric_tail)
        if len(numbers) < 6 or not description:
            return None
        if len(numbers) == 6:
            possible_dto = OrderDocumentParser.parse_decimal_es(numbers[3], default=-1.0)
            possible_iva = OrderDocumentParser.parse_decimal_es(numbers[5], default=-1.0)
            kilos = OrderDocumentParser.parse_decimal_es(numbers[2], default=0.0)
            total = OrderDocumentParser.parse_decimal_es(numbers[4], default=0.0)
            if abs(possible_dto - 20.0) <= 0.2 and 0 <= possible_iva <= 21 and kilos > 0 and total > 0:
                price = total / (kilos * (1 - (possible_dto / 100.0)))
                numbers = [numbers[0], numbers[1], numbers[2], f"{price:.2f}", numbers[3], numbers[4], numbers[5]]
        kilos = OrderDocumentParser.parse_decimal_es(numbers[2], default=0.0)
        price = OrderDocumentParser.parse_decimal_es(numbers[3], default=0.0)
        dto = OrderDocumentParser.parse_decimal_es(numbers[4], default=0.0)
        total = OrderDocumentParser.parse_decimal_es(numbers[5], default=0.0)
        if kilos > 0 and total > 0 and 0 <= dto < 100:
            expected_total = price * kilos * (1 - (dto / 100.0))
            if abs(expected_total - total) > max(0.05, total * 0.05):
                numbers[3] = f"{total / (kilos * (1 - (dto / 100.0))):.2f}"
        return {
            "factura_numero": str(header.get("factura_numero") or "").strip(),
            "factura_fecha": str(header.get("factura_fecha") or "").strip(),
            "albaran_numero": str(header.get("albaran_numero") or "").strip(),
            "factura_referencia": str(header.get("factura_referencia") or "").strip(),
            "articulo_codigo": code,
            "articulo_descripcion": description,
            "articulo_cantidad": numbers[0],
            "articulo_envase": numbers[1],
            "articulo_kilos": numbers[2],
            "articulo_lote": lote,
            "articulo_caducidad": caducidad,
            "precio_unitario": numbers[3],
            "dto_pct": numbers[4],
            "iva_pct": numbers[6] if len(numbers) > 6 else "",
            "total_linea": numbers[5],
        }

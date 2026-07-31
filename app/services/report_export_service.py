from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import DATA_DIR


class ReportExportService:
    def default_path(self, title: str, suffix: str, folder: str = "listados_clientes") -> Path:
        reports_dir = DATA_DIR / "exports" / folder
        reports_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch if ch.isalnum() else "_" for ch in str(title or "listado").lower()).strip("_")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return reports_dir / f"{safe[:40] or 'listado'}_{stamp}.{suffix.lstrip('.')}"

    def export_excel(self, path: str | Path, title: str, headers: list[str], rows: list[list[Any]], sheet_title: str = "Listado clientes") -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_title[:31]
        ws.append([title])
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(1, len(headers)))
        ws.cell(1, 1).font = Font(bold=True, size=14)
        ws.append(headers)
        for cell in ws[2]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="3A78CF")
        for row in rows:
            ws.append(row)
        for col_idx in range(1, max(1, len(headers)) + 1):
            max_len = max(len(str(ws.cell(row=row_idx, column=col_idx).value or "")) for row_idx in range(2, ws.max_row + 1))
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 2, 10), 45)
        ws.freeze_panes = "A3"
        wb.save(out)
        return out

    def export_pdf(self, path: str | Path, title: str, headers: list[str], rows: list[list[Any]]) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(str(out), pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ListingTitleLeft",
            parent=styles["Title"],
            alignment=0,
        )
        story = [Paragraph(str(title or "Listado de clientes"), title_style), Spacer(1, 10)]
        table_data = [headers] + [[str(value) for value in row] for row in rows]
        column_count = max(1, len(headers))
        content_widths = [0] * column_count
        for row in table_data:
            for index in range(column_count):
                value = row[index] if index < len(row) else ""
                text = str(value or "")
                content_widths[index] = max(content_widths[index], len(text))
        min_widths = [24] * column_count
        max_widths = [max(40, min(220, width * 4 + 24)) for width in content_widths]
        available_width = doc.width
        scale = available_width / sum(max_widths)
        if scale < 1:
            col_widths = [max(min_widths[idx], width * scale) for idx, width in enumerate(max_widths)]
        else:
            col_widths = max_widths[:]
        width_delta = available_width - sum(col_widths)
        if width_delta != 0 and column_count:
            col_widths[-1] = max(min_widths[-1], col_widths[-1] + width_delta)
        table = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3A78CF")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        return out

    def export_customer_sales_comparison_pdf(
        self,
        path: str | Path,
        *,
        customer_name: str,
        year: int,
        rows: list[Any],
    ) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        current_year = int(year)
        previous_year = current_year - 1
        doc = SimpleDocTemplate(
            str(out),
            pagesize=landscape(A4),
            leftMargin=10 * mm,
            rightMargin=10 * mm,
            topMargin=10 * mm,
            bottomMargin=12 * mm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("SalesComparisonTitle", parent=styles["Title"], alignment=0, fontSize=15, leading=18)
        subtitle_style = ParagraphStyle(
            "SalesComparisonSubtitle",
            parent=styles["Normal"],
            textColor=colors.HexColor("#475467"),
            fontSize=9,
            leading=11,
        )
        cell_style = ParagraphStyle("SalesComparisonCell", parent=styles["BodyText"], fontSize=6.6, leading=8)

        def number(value: Any) -> str:
            return f"{float(value or 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        table_data: list[list[Any]] = [
            ["", "", str(previous_year), "", "", str(current_year), "", "", "Diferencia", "", ""],
            ["Referencia", "Descripción", "Unid.", "Kg", "€", "Unid.", "Kg", "€", "Δ Unid.", "Δ Kg", "Δ €"],
        ]
        totals = [0.0] * 9
        delta_color_commands = []
        for row in rows:
            values = [
                row.unidades_prev,
                row.kg_prev,
                row.euros_prev,
                row.unidades_curr,
                row.kg_curr,
                row.euros_curr,
                row.delta_unidades,
                row.delta_kg,
                row.delta_euros,
            ]
            totals = [total + float(value or 0.0) for total, value in zip(totals, values)]
            table_row = len(table_data)
            for column, value in enumerate(values[6:], start=8):
                color = "#067647" if float(value or 0.0) > 0 else "#B42318" if float(value or 0.0) < 0 else "#111827"
                delta_color_commands.append(("TEXTCOLOR", (column, table_row), (column, table_row), colors.HexColor(color)))
            table_data.append(
                [
                    str(row.codigo or "").strip(),
                    Paragraph(str(row.nombre or "").strip(), cell_style),
                    *[number(value) for value in values],
                ]
            )
        table_data.append(["TOTALES", "", *[number(value) for value in totals]])

        table = Table(
            table_data,
            colWidths=[20 * mm, 47 * mm, 18 * mm, 20 * mm, 23 * mm, 18 * mm, 20 * mm, 23 * mm, 19 * mm, 21 * mm, 24 * mm],
            repeatRows=2,
            hAlign="LEFT",
        )
        last_row = len(table_data) - 1
        table.setStyle(
            TableStyle(
                [
                    ("SPAN", (2, 0), (4, 0)),
                    ("SPAN", (5, 0), (7, 0)),
                    ("SPAN", (8, 0), (10, 0)),
                    ("SPAN", (0, last_row), (1, last_row)),
                    ("BACKGROUND", (0, 0), (1, 1), colors.HexColor("#E8EEF7")),
                    ("BACKGROUND", (2, 0), (4, 0), colors.HexColor("#475467")),
                    ("BACKGROUND", (5, 0), (7, 0), colors.HexColor("#0F766E")),
                    ("BACKGROUND", (8, 0), (10, 0), colors.HexColor("#E8EEF7")),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F2F4F7")),
                    ("BACKGROUND", (0, last_row), (-1, last_row), colors.HexColor("#E8EEF7")),
                    ("TEXTCOLOR", (2, 0), (7, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
                    ("FONTNAME", (0, last_row), (-1, last_row), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, 1), "CENTER"),
                    ("ALIGN", (2, 2), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, last_row), (0, last_row), "LEFT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 6.6),
                    ("LEADING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D0D5DD")),
                    ("ROWBACKGROUNDS", (0, 2), (-1, last_row - 1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    *delta_color_commands,
                ]
            )
        )
        for column, value in enumerate(totals[6:], start=8):
            color = "#067647" if value > 0 else "#B42318" if value < 0 else "#111827"
            table.setStyle(TableStyle([("TEXTCOLOR", (column, last_row), (column, last_row), colors.HexColor(color))]))

        def add_page_number(canvas, document) -> None:
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#667085"))
            canvas.drawRightString(document.pagesize[0] - 10 * mm, 6 * mm, f"Página {document.page}")
            canvas.restoreState()

        story = [
            Paragraph("Comparativa de ventas", title_style),
            Paragraph(
                f"{customer_name} · {previous_year} vs {current_year} · Generado {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                subtitle_style,
            ),
            Spacer(1, 5 * mm),
            table,
        ]
        doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
        return out

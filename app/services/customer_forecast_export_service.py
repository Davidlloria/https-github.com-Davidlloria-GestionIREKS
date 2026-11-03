"""Export the current forecast as a formatted, static Excel snapshot."""
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def export_forecast_excel(path, customer_name, tariff, year, rows):
    if not rows:
        raise ValueError("La previsión no contiene artículos.")
    wb = Workbook()
    ws = wb.active
    ws.title = "Previsión"
    ws.append([f"Previsión · {customer_name}"])
    ws.merge_cells("A1:H1")
    ws["A1"].font = Font(size=16, bold=True, color="17365C")
    ws.append([f"Tarifa {tariff} · {year} · Importes sin impuestos ni transporte"])
    ws.merge_cells("A2:H2")
    ws.append(["Producto", "Lote", "Envases", "Tarifa €/envase", "Importe €", "Entrega prevista", "Caducidad", "Estado"])
    for cell in ws[3]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2563EB")
    total = Decimal("0.00")
    missing = 0
    for source in rows:
        row = list(source)
        if row[4] is None:
            missing += 1
            row[7] = " · ".join(filter(None, [row[7], "Sin tarifa; importe pendiente"]))
        else:
            total += Decimal(str(row[4]))
        row[5] = row[5] or "Pendiente"
        row[6] = row[6] or "Pendiente"
        ws.append(row)
        index = ws.max_row
        ws.cell(index, 3).number_format = "0"
        ws.cell(index, 4).number_format = '#,##0.00#### "€"'
        ws.cell(index, 5).number_format = '#,##0.00 "€"'
        for column in (6, 7):
            ws.cell(index, column).number_format = "dd/mm/yyyy"
        for cell in ws[index]:
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.row_dimensions[index].height = 32
    last_data_row = ws.max_row
    ws.append(["Subtotal valorado (incompleto)" if missing else "Total", None, None, None, total])
    ws.cell(ws.max_row, 5).number_format = '#,##0.00 "€"'
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True, color="17365C")
    ws.append(["Stock informativo; esta previsión no reserva existencias."])
    ws.merge_cells(start_row=ws.max_row, start_column=1, end_row=ws.max_row, end_column=8)
    # User/catalogue text must remain literal even when it begins with '='.
    for row in ws:
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    for column, width in enumerate((42, 19, 12, 19, 18, 20, 20, 42), 1):
        ws.column_dimensions[get_column_letter(column)].width = width
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:H{last_data_row}"
    ws.sheet_view.showGridLines = False
    ws.print_options.horizontalCentered = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "1:3"
    ws.print_area = ws.dimensions
    out = Path(path)
    wb.save(out)
    return out

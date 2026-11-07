"""Read-only preview of a monthly IGSA / IREKS document comparison."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
)

from app.services.igsa_monthly_review_service import IgsaMonthlyReviewService


MONTHS = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")
KINDS = {"venta": "Venta", "muestra": "Muestra", "promocion": "S/C"}
KIND_ORDER = {"venta": 0, "muestra": 1, "promocion": 2}
STATUSES = {
    "correcto": "Correcto", "diferencia": "Diferencia", "sin_correspondencia": "Sin correspondencia",
    "revisar_reparto": "Revisar reparto", "posible_duplicado": "Posible duplicado",
    "fuente_incompleta": "Fuente incompleta",
}


def _location(loc) -> str:
    if loc is None:
        return "—"
    parts = [loc.file]
    if loc.sheet:
        parts.append(loc.sheet)
    if loc.row is not None:
        parts.append(f"fila {loc.row}")
    if loc.page is not None:
        parts.append(f"página {loc.page}")
    if loc.item is not None:
        parts.append(f"artículo {loc.item}")
    return " · ".join(parts)


def _quantity(value) -> str:
    return "—" if value is None else format(value, "f").replace(".", ",")


class IgsaMonthlyReviewDialog(QDialog):
    def __init__(self, parent=None, *, service=None):
        super().__init__(parent)
        self._service = service if service is not None else IgsaMonthlyReviewService()
        self._result = None
        self.setWindowTitle("Revisión mensual IGSA / IREKS")
        self.resize(1120, 760)
        root = QVBoxLayout(self)
        intro = QLabel("Compara los documentos seleccionados. La vista es temporal y no importa ni modifica datos.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        period = QHBoxLayout()
        period.addWidget(QLabel("Año"))
        self.year = QSpinBox()
        self.year.setRange(1900, 9999)
        self.year.setValue(date.today().year)
        period.addWidget(self.year)
        period.addWidget(QLabel("Mes"))
        self.month = QComboBox()
        for index, name in enumerate(MONTHS, 1):
            self.month.addItem(name, index)
        self.month.setCurrentIndex(date.today().month - 1)
        period.addWidget(self.month)
        period.addStretch(1)
        root.addLayout(period)

        form = QFormLayout()
        self.paths = {}
        for key, label, file_filter in (
            ("excel", "Excel IGSA", "Excel (*.xlsx *.xlsm)"),
            ("venta", "PDF ventas", "PDF (*.pdf)"),
            ("muestra", "PDF muestras", "PDF (*.pdf)"),
            ("promocion", "PDF promociones / S/C", "PDF (*.pdf)"),
        ):
            row = QHBoxLayout()
            edit = QLineEdit()
            edit.setReadOnly(True)
            edit.setPlaceholderText("Sin seleccionar" if key != "excel" else "Selecciona el Excel de IGSA")
            button = QPushButton("Seleccionar…")
            button.clicked.connect(lambda _checked=False, k=key, f=file_filter: self._select_file(k, f))
            row.addWidget(edit, 1)
            row.addWidget(button)
            if key != "excel":
                clear = QPushButton("Quitar")
                clear.clicked.connect(edit.clear)
                row.addWidget(clear)
            form.addRow(label, row)
            self.paths[key] = edit
            edit.textChanged.connect(self._clear_result)
        root.addLayout(form)
        actions = QHBoxLayout()
        self.compare_button = QPushButton("Comparar documentos")
        self.compare_button.clicked.connect(self._compare)
        actions.addWidget(self.compare_button)
        self.only_differences = QCheckBox("Solo pendientes")
        self.only_differences.toggled.connect(self._render_balances)
        actions.addWidget(self.only_differences)
        actions.addStretch(1)
        root.addLayout(actions)
        self.message = QLabel("Selecciona el Excel y los PDF disponibles para iniciar la revisión.")
        self.message.setWordWrap(True)
        root.addWidget(self.message)
        self.tabs = QTabWidget()
        self.product_table = self._table(["Tipo", "Producto", "Referencia", "IGSA", "IREKS", "Diferencia", "Estado", "Origen"])
        self.lot_table = self._table(["Tipo", "Producto", "Referencia", "Lote", "IGSA", "IREKS", "Diferencia", "Estado", "Origen"])
        self.issue_table = self._table(["Incidencia", "Detalle", "Origen"])
        self.tabs.addTab(self.product_table, "Por producto")
        self.tabs.addTab(self.lot_table, "Por lote")
        self.tabs.addTab(self.issue_table, "Incidencias")
        root.addWidget(self.tabs, 1)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.reject)
        root.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        self.year.valueChanged.connect(self._clear_result)
        self.month.currentIndexChanged.connect(self._clear_result)

    @staticmethod
    def _table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _select_file(self, key, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar documento", "", file_filter)
        if path:
            self.paths[key].setText(path)

    def _clear_result(self, *_args):
        self._result = None
        for table in (self.product_table, self.lot_table, self.issue_table):
            table.setRowCount(0)
        self.tabs.setTabText(2, "Incidencias")
        self.message.setText("Los documentos o el período han cambiado. Ejecuta de nuevo la comparación.")

    def _compare(self):
        self._clear_result()
        workbook = self.paths["excel"].text().strip()
        if not workbook:
            self.message.setText("Selecciona el Excel de IGSA antes de comparar.")
            return
        pdfs = {key: Path(self.paths[key].text()) for key in KINDS if self.paths[key].text().strip()}
        try:
            result = self._service.compare(Path(workbook), pdfs, year=self.year.value(), month=self.month.currentData())
        except Exception as exc:  # noqa: BLE001 - show file/parser errors without retaining stale results
            self.message.setText(f"No se pudo completar la comparación: {exc}")
            return
        self._result = result
        self.message.setText(f"Período: {result.month:02d}/{result.year} · Productos: {len(result.products)} · Lotes: {len(result.lots)} · Incidencias: {len(result.issues)}")
        self._render_balances()
        self._fill_table(self.issue_table, [[issue.code.replace("_", " ").capitalize(), issue.message, _location(issue.location)] for issue in result.issues])
        self.tabs.setTabText(2, f"Incidencias ({len(result.issues)})")

    def _render_balances(self, *_args):
        if self._result is None:
            return
        names = {}
        for line in self._result.lines:
            if line.product not in names or line.source == "igsa":
                names[line.product] = line.description
        for table, rows, by_lot in ((self.product_table, self._result.products, False), (self.lot_table, self._result.lots, True)):
            ordered = sorted(rows, key=lambda row: (KIND_ORDER.get(row.kind, 9), names.get(row.product, row.product).casefold(), row.product, row.lot or ""))
            values = []
            for row in ordered:
                if self.only_differences.isChecked() and row.status == "correcto":
                    continue
                cells = [KINDS.get(row.kind, row.kind), names.get(row.product, row.product), row.product]
                if by_lot:
                    cells.append(row.lot or "—")
                cells.extend([_quantity(row.igsa), _quantity(row.ireks), _quantity(row.difference), STATUSES.get(row.status, row.status), "\n".join(_location(loc) for loc in row.locations)])
                values.append(cells)
            self._fill_table(table, values)

    @staticmethod
    def _fill_table(table, rows):
        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                table.setItem(row_index, column, item)
        table.resizeColumnsToContents()
        for column in range(table.columnCount()):
            table.setColumnWidth(column, min(280, max(85, table.columnWidth(column))))

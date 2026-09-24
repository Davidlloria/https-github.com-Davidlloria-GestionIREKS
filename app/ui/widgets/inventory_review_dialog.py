from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QDateEdit, QDialog, QDialogButtonBox,
                              QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                              QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from app.services.inventory_review_service import InventoryReviewService


class InventoryReviewDialog(QDialog):
    def __init__(self, warehouse, parent=None, service=None):
        super().__init__(parent)
        self.warehouse = warehouse
        self.service = service or InventoryReviewService()
        self.rows = []
        self.setWindowTitle("Revisión histórica de inventario · Solo lectura")
        self.resize(1400, 760)
        layout = QVBoxLayout(self)
        info = QLabel("Conteo físico de la hoja INVENTARIO, incluidos los caducados pendientes de destruir. "
                      "Se compara con los movimientos hasta el cierre indicado. No se vuelve a descontar ventas, muestras ni promociones. "
                      "Esta revisión no modifica el stock.")
        info.setWordWrap(True)
        layout.addWidget(info)
        top = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setReadOnly(True)
        self.path.setPlaceholderText("Selecciona el libro de inventario")
        top.addWidget(self.path, 1)
        choose = QPushButton("Seleccionar Excel")
        choose.clicked.connect(self._choose)
        top.addWidget(choose)
        top.addWidget(QLabel("Cierre:"))
        self.cutoff = QDateEdit(QDate(2026, 5, 29))
        self.cutoff.setCalendarPopup(True)
        self.cutoff.setDisplayFormat("dd/MM/yyyy")
        self.cutoff.dateChanged.connect(self._invalidate)
        top.addWidget(self.cutoff)
        compare = QPushButton("Comparar")
        compare.clicked.connect(self._compare)
        top.addWidget(compare)
        layout.addLayout(top)
        self.summary = QLabel("Mayo 2026: sin actividad el 30 y 31; seguimiento desde el 01/06. Los conteos vacíos quedan pendientes.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        search = QLineEdit()
        search.setPlaceholderText("Buscar producto, lote o incidencia…")
        search.textChanged.connect(self._filter)
        self.search = search
        layout.addWidget(search)
        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels(["Fila Excel", "Código", "Producto", "Lote", "Cons. pref.",
                                             "Teórico uds", "Conteo uds", "Ajuste uds", "Ajuste kg", "Estado", "Comentarios", "Origen"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.setStyleSheet("QTableWidget::item:selected { background:#DBF3F2; color:#173653; }")
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate([90, 100, 230, 115, 100, 100, 100, 100, 100, 290, 230, 100]):
            self.table.setColumnWidth(column, width)
        layout.addWidget(self.table, 1)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    def _invalidate(self, *_):
        self.rows = []
        self.table.setRowCount(0)
        self.summary.setText("Pulsa Comparar para calcular los resultados con el archivo y la fecha seleccionados.")

    def _choose(self):
        path, _ = QFileDialog.getOpenFileName(self, "Inventario físico", "", "Excel (*.xlsx)")
        if path:
            self.path.setText(path)
            self._invalidate()

    def _compare(self):
        if not self.path.text():
            QMessageBox.information(self, "Inventario", "Selecciona el archivo Excel.")
            return
        self._invalidate()
        try:
            qdate = self.cutoff.date()
            self.rows = self.service.compare(self.path.text(), self.warehouse, date(qdate.year(), qdate.month(), qdate.day()))
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo comparar", str(exc))
            return
        self.table.setRowCount(len(self.rows))
        keys = ["row", "code", "name", "lot", "expiry", "theoretical", "count", "delta", "kg", "status", "notes"]
        for i, row in enumerate(self.rows):
            values = [row[k] for k in keys] + ["INVENTARIO" if row["row"] else "Almacén"]
            for j, value in enumerate(values):
                text = "—" if value is None else str(value)
                if j in {5, 6, 7, 8} and value is not None:
                    text = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if j in {5, 6, 7, 8}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if value is not None and value < 0:
                        item.setForeground(QColor("#B42318"))
                if row["delta"] is None:
                    item.setBackground(QColor("#FEF3C7"))
                self.table.setItem(i, j, item)
        pending = sum(r["delta"] is None for r in self.rows)
        differences = sum(r["delta"] is not None and abs(r["delta"]) > 1e-6 for r in self.rows)
        self.summary.setText(f"Cierre {qdate.toString('dd/MM/yyyy')} · {len(self.rows)} líneas · "
                             f"{differences} diferencias · {pending} pendientes/excluidas. "
                             "Ajuste propuesto = conteo − teórico. No se ha aplicado ningún ajuste.")
        self._filter(self.search.text())

    def _filter(self, text):
        for i, row in enumerate(self.rows):
            self.table.setRowHidden(i, text.casefold() not in " ".join(str(v) for v in row.values()).casefold())

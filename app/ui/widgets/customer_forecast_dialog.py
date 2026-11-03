from datetime import date
from decimal import Decimal
from pathlib import Path
import unicodedata

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QDateEdit, QDialog, QHBoxLayout, QListWidget, QListWidgetItem,
    QFileDialog, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.services.customer_forecast_service import CustomerForecastService
from app.services.customer_forecast_export_service import export_forecast_excel


FORECAST_STYLE = """
QDialog { background: #f4f6f9; color: #243247; }
QLabel { color: #475569; }
QPushButton { background: white; color: #334155; border: 1px solid #cbd5e1;
    border-radius: 6px; padding: 7px 14px; min-height: 20px; }
QPushButton:hover { background: #eaf0f8; }
QPushButton:disabled { color: #94a3b8; background: #f1f5f9; }
QPushButton#forecastPrimary { background: #2563eb; color: white; border-color: #2563eb; }
QPushButton#forecastPrimary:disabled { background: #cbd5e1; border-color: #cbd5e1; }
QLineEdit, QDateEdit { background: white; color: #243247;
    border: 1px solid #cbd5e1; border-radius: 5px; padding: 5px; min-height: 22px; }
QDateEdit:disabled { color: #334155; background: #f1f5f9; }
QTableWidget, QListWidget { background: white; alternate-background-color: #f8fafc;
    border: 1px solid #dbe3ed; border-radius: 6px; color: #243247;
    selection-background-color: #dbeafe; selection-color: #1e3a5f; }
QTableWidget::item, QListWidget::item { padding: 6px; }
QHeaderView::section { background: #edf2f7; color: #334155; border: none;
    border-bottom: 1px solid #dbe3ed; padding: 9px 6px; font-weight: 600; }
QLabel#forecastTotal { font-size: 20px; font-weight: 600; color: #17365c; }
"""


class ForecastIntegerEdit(QLineEdit):
    """Keyboard/paste input scoped to forecasts, with no stepping controls."""

    def __init__(self, minimum, maximum, value):
        super().__init__(str(value))
        self.setValidator(QIntValidator(minimum, maximum, self))
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setToolTip(f"Introduce un entero entre {minimum} y {maximum}")

    def value(self):
        return int(self.text()) if self.text().isdecimal() and self.hasAcceptableInput() else None

    def setValue(self, value):
        self.setText(str(value))


class ForecastArticleDialog(QDialog):
    """Choose a product and explicitly confirm one stock lot."""

    def __init__(self, products, service, parent=None):
        super().__init__(parent)
        self.setObjectName("forecastArticleDialog")
        self.setWindowTitle("Añadir artículo")
        self.setStyleSheet(FORECAST_STYLE)
        self.resize(900, 620)
        self.selection = None
        self._catalog = products
        self.service = service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por referencia o nombre (cualquier fragmento)…")
        self.search.setClearButtonEnabled(True)
        self.search.setObjectName("forecastProductSearch")
        layout.addWidget(self.search)
        self.matches = QLabel()
        layout.addWidget(self.matches)
        self.products = QListWidget()
        self.products.setMaximumHeight(165)
        layout.addWidget(self.products)
        layout.addWidget(QLabel("Lotes disponibles · Selecciona una fila y pulsa Añadir, o haz doble clic"))
        self.lots = QTableWidget(0, 3)
        self.lots.setHorizontalHeaderLabels(["Lote", "Caducidad", "Stock (envases)"])
        self.lots.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lots.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lots.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lots.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.lots.verticalHeader().hide()
        self.lots.verticalHeader().setDefaultSectionSize(38)
        self.lots.setShowGrid(False)
        self.lots.setAlternatingRowColors(True)
        layout.addWidget(self.lots, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        self.unconfirmed = QPushButton("Añadir sin lote confirmado")
        self.unconfirmed.clicked.connect(self._without_lot)
        actions.addWidget(self.unconfirmed)
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        self.add_button = QPushButton("Añadir lote seleccionado")
        self.add_button.setObjectName("forecastPrimary")
        self.add_button.clicked.connect(self._confirm_lot)
        actions.addWidget(self.add_button)
        layout.addLayout(actions)
        self.search.textChanged.connect(self._filter_products)
        self.products.currentItemChanged.connect(self._load_lots)
        self.lots.itemSelectionChanged.connect(self._update_add)
        self.lots.cellDoubleClicked.connect(self._confirm_lot)
        self._filter_products()
        self.search.setFocus()

    @staticmethod
    def _search_text(text):
        return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if not unicodedata.combining(c))

    def _filter_products(self):
        words = self._search_text(self.search.text()).split()
        matches = [p for p in self._catalog if all(w in self._search_text(p.label) for w in words)]
        self.products.blockSignals(True)
        self.products.clear()
        for product in matches:
            item = QListWidgetItem(product.label + (" · Sin tarifa" if product.price is None else ""))
            item.setData(Qt.ItemDataRole.UserRole, product)
            self.products.addItem(item)
        self.products.blockSignals(False)
        self.matches.setText(f"{len(matches)} artículos encontrados" if matches else "Sin coincidencias")
        if matches:
            self.products.setCurrentRow(0)
        else:
            self._load_lots()

    def _product(self):
        item = self.products.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _load_lots(self):
        self.lots.setRowCount(0)
        self.message.clear()
        product = self._product()
        self.unconfirmed.setEnabled(product is not None)
        self.add_button.setEnabled(False)
        if product is None:
            return
        try:
            lots = self.service.lots(product.article_id)
        except Exception as exc:
            self.message.setText(f"No se pudo consultar el stock: {exc}")
            return
        self.lots.setRowCount(len(lots))
        for row, lot in enumerate(lots):
            values = [lot.lot or "Sin número", lot.expiry.strftime("%d/%m/%Y") if lot.expiry else "Pendiente",
                      f"{lot.available:g}"]
            for column, value in enumerate(values):
                self.lots.setItem(row, column, QTableWidgetItem(value))
            self.lots.item(row, 0).setData(Qt.ItemDataRole.UserRole, lot)
        self.message.setText("Stock informativo; no se reserva." if lots else "Este artículo no tiene lotes con stock disponible.")

    def _update_add(self):
        self.add_button.setEnabled(bool(self.lots.selectedItems()))

    def _confirm_lot(self, *_):
        row = self.lots.currentRow()
        if row >= 0 and self.lots.selectedItems() and self._product() is not None:
            self.selection = (self._product(), self.lots.item(row, 0).data(Qt.ItemDataRole.UserRole))
            self.accept()

    def _without_lot(self):
        if self._product() is not None:
            self.selection = (self._product(), None)
            self.accept()


class CustomerForecastDialog(QDialog):
    def __init__(self, customer, parent=None, *, service=None):
        super().__init__(parent)
        self.service = service or CustomerForecastService()
        self.customer_id = customer.cliente_id
        self.customer_name = customer.cliente_nombre_comercial
        self.setObjectName("customerForecastDialog")
        self.setWindowTitle(f"Previsión · {customer.cliente_nombre_comercial}")
        self.resize(1180, 640)
        self.setStyleSheet(FORECAST_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        controls = QHBoxLayout()
        self.distributor = QLabel()
        controls.addWidget(self.distributor)
        controls.addStretch()
        controls.addWidget(QLabel("Año de tarifa:"))
        self.year = ForecastIntegerEdit(2000, 9999, date.today().year)
        self.year.setFixedWidth(90)
        controls.addWidget(self.year)
        layout.addLayout(controls)
        actions = QHBoxLayout()
        self.add_button = QPushButton("Añadir artículo")
        self.add_button.setObjectName("forecastPrimary")
        self.add_button.clicked.connect(self._choose_article)
        actions.addWidget(self.add_button)
        self.remove_button = QPushButton("Quitar línea")
        self.remove_button.clicked.connect(self._remove_line)
        actions.addWidget(self.remove_button)
        self.excel_button = QPushButton("Exportar a Excel")
        self.excel_button.clicked.connect(self._export_excel)
        actions.addWidget(self.excel_button)
        actions.addStretch()
        self.line_count = QLabel("Sin artículos")
        actions.addWidget(self.line_count)
        layout.addLayout(actions)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Producto", "Envases", "Tarifa €/envase", "Importe €",
            "Entrega prevista", "Caducidad", "Estado", "Lote", "Stock consultado",
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 260)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setColumnHidden(6, True)
        self.table.setColumnHidden(8, True)
        self.table.horizontalHeader().moveSection(7, 1)
        self.table.setColumnWidth(0, 230)
        for column, width in ((1, 85), (2, 115), (3, 105), (4, 150), (5, 150), (7, 170)):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(column, width)
        layout.addWidget(self.table, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.total = QLabel()
        self.total.setObjectName("forecastTotal")
        layout.addWidget(self.total, alignment=Qt.AlignmentFlag.AlignRight)
        note = QLabel(
            "Previsión temporal · No reserva stock · Importes sin impuestos ni transporte"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.reject)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.year.textChanged.connect(self._load_catalog)
        self._load_catalog()

    def _load_catalog(self):
        if self.year.value() is None:
            self._catalog = []
            self.add_button.setEnabled(False)
            self.distributor.setText("Introduce un año válido entre 2000 y 9999.")
            self._recalculate()
            return
        try:
            name, products = self.service.catalog(self.customer_id, self.year.value())
        except Exception as exc:
            self.distributor.setText(f"No se pudo cargar la tarifa: {exc}")
            products = []
        else:
            self.tariff_name = name
            self.distributor.setText(f"Tarifa aplicada: {name}")
        self._catalog = products
        self.add_button.setEnabled(bool(products))
        if not products and not self.distributor.text().startswith("No se pudo"):
            self.distributor.setText(self.distributor.text() + " · Sin productos activos")
        self._recalculate()

    def _choose_article(self):
        picker = ForecastArticleDialog(self._catalog, self.service, self)
        if picker.exec() == QDialog.DialogCode.Accepted and picker.selection is not None:
            self._add_line(*picker.selection)

    @staticmethod
    def _date_editor():
        editor = QDateEdit()
        editor.setCalendarPopup(True)
        editor.setMinimumWidth(140)
        editor.setDisplayFormat("dd/MM/yyyy")
        editor.setMinimumDate(QDate(1900, 1, 1))
        editor.setSpecialValueText("Pendiente")
        editor.setDate(editor.minimumDate())
        today = QDate.currentDate()
        editor.calendarWidget().setCurrentPage(today.year(), today.month())
        return editor

    def _add_line(self, product, lot=None):
        if product is None:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        item = QTableWidgetItem(product.label)
        item.setData(Qt.ItemDataRole.UserRole, product)
        item.setData(Qt.ItemDataRole.UserRole + 1, lot)
        self.table.setItem(row, 0, item)
        self.table.setItem(row, 7, QTableWidgetItem(
            lot.lot or "Sin número" if lot else "Sin confirmar"
        ))
        self.table.setItem(row, 8, QTableWidgetItem(f"{lot.available:g}" if lot else "—"))
        if lot:
            self.table.item(row, 7).setToolTip(f"Stock consultado: {lot.available:g} envases")
        quantity = ForecastIntegerEdit(1, 1000000, 1)
        self.table.setCellWidget(row, 1, quantity)
        quantity.textChanged.connect(self._recalculate)
        for column in (4, 5):
            editor = self._date_editor()
            self.table.setCellWidget(row, column, editor)
            if column == 5 and lot is not None:
                if lot.expiry:
                    editor.setDate(QDate(lot.expiry.year, lot.expiry.month, lot.expiry.day))
                editor.setEnabled(False)
            editor.dateChanged.connect(self._recalculate)
        self.year.setEnabled(False)
        self.table.selectRow(row)
        self._recalculate()

    def _remove_line(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
        self.year.setEnabled(self.table.rowCount() == 0)
        self._recalculate()

    @staticmethod
    def _money(value):
        return format(value, "f").replace(".", ",")

    def _recalculate(self):
        invalid = [r for r in range(self.table.rowCount()) if self.table.cellWidget(r, 1).value() is None]
        self.excel_button.setEnabled(bool(self.table.rowCount()) and not invalid and self.year.value() is not None)
        if invalid:
            self.total.setText("Total pendiente: revisa las cantidades")
            self.status.setText("Introduce una cantidad entera de 1 a 1000000 en las líneas: " + ", ".join(str(r + 1) for r in invalid))
            self.status.show()
            for row in invalid:
                self.table.setItem(row, 3, QTableWidgetItem("Pendiente"))
            return
        total = Decimal("0.00")
        missing = 0
        quantities = {}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            lot = item.data(Qt.ItemDataRole.UserRole + 1)
            if lot:
                product = item.data(Qt.ItemDataRole.UserRole)
                key = (product.article_id, lot.warehouse_id, lot.lot, lot.expiry)
                quantities[key] = quantities.get(key, 0) + self.table.cellWidget(row, 1).value()
        for row in range(self.table.rowCount()):
            product = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            amount = self.service.amount(self.table.cellWidget(row, 1).value(), product.price)
            self.table.setItem(row, 2, QTableWidgetItem(
                self._money(product.price) if product.price is not None else "Sin tarifa"
            ))
            self.table.setItem(row, 3, QTableWidgetItem(
                self._money(amount) if amount is not None else "Pendiente"
            ))
            if amount is None:
                missing += 1
            else:
                total += amount
            delivery, expiry = (self.table.cellWidget(row, c) for c in (4, 5))
            pending = delivery.date() == delivery.minimumDate() or expiry.date() == expiry.minimumDate()
            status = "Fechas pendientes" if pending else ""
            if not pending and expiry.date() < delivery.date():
                status = "Caduca antes de la entrega"
            lot = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole + 1)
            if lot:
                key = (product.article_id, lot.warehouse_id, lot.lot, lot.expiry)
                if quantities[key] > lot.available:
                    status = " · ".join(filter(None, [status, "Previsión supera stock del lote"]))
            self.table.setItem(row, 6, QTableWidgetItem(status))
        label = "Subtotal valorado" if missing else "Total"
        self.total.setText(f"{label}: {self._money(total)} €" + (
            f" · Incompleto: {missing} línea(s) sin tarifa" if missing else ""
        ))
        self.remove_button.setEnabled(self.table.rowCount() > 0)
        self.line_count.setText(f"{self.table.rowCount()} líneas" if self.table.rowCount() else "Sin artículos")
        notices = [f"Línea {r + 1}: {self.table.item(r, 6).text()}" for r in range(self.table.rowCount()) if self.table.item(r, 6).text()]
        self.status.setText(" · ".join(notices))
        self.status.setVisible(bool(notices))

    def _export_excel(self):
        self._recalculate()
        if not self.excel_button.isEnabled():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar previsión a Excel", "prevision.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        if Path(path).suffix.lower() != ".xlsx":
            path += ".xlsx"
        rows = []
        for row in range(self.table.rowCount()):
            product = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            quantity = self.table.cellWidget(row, 1).value()
            dates = [self.table.cellWidget(row, c) for c in (4, 5)]
            rows.append([
                product.label, self.table.item(row, 7).text(), quantity, product.price,
                self.service.amount(quantity, product.price),
                *[e.date().toPython() if e.date() != e.minimumDate() else None for e in dates],
                self.table.item(row, 6).text(),
            ])
        try:
            export_forecast_excel(path, self.customer_name, self.tariff_name, self.year.value(), rows)
        except Exception as exc:
            QMessageBox.warning(self, "Exportar previsión", f"No se pudo guardar el Excel.\n{exc}")
            return
        QMessageBox.information(self, "Exportar previsión", f"Excel guardado en:\n{path}")

    def reject(self):
        if self.table.rowCount() and QMessageBox.question(
            self, "Cerrar previsión", "La previsión no se guarda. ¿Descartar y cerrar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        super().reject()

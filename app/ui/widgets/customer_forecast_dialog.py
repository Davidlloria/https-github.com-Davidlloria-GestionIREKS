from datetime import date
from decimal import Decimal
import unicodedata

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QDialog, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.services.customer_forecast_service import CustomerForecastService


class CustomerForecastDialog(QDialog):
    def __init__(self, customer, parent=None, *, service=None):
        super().__init__(parent)
        self.service = service or CustomerForecastService()
        self.customer_id = customer.cliente_id
        self.setObjectName("customerForecastDialog")
        self.setWindowTitle(f"Previsión · {customer.cliente_nombre_comercial}")
        self.resize(1100, 520)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.distributor = QLabel()
        controls.addWidget(self.distributor)
        controls.addStretch()
        controls.addWidget(QLabel("Año de tarifa:"))
        self.year = QSpinBox()
        self.year.setRange(2000, 9999)
        self.year.setValue(date.today().year)
        controls.addWidget(self.year)
        layout.addLayout(controls)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por cualquier parte de la referencia o del nombre…")
        self.search.setClearButtonEnabled(True)
        self.search.setObjectName("forecastProductSearch")
        layout.addWidget(self.search)
        self.matches = QLabel()
        layout.addWidget(self.matches)
        picker = QHBoxLayout()
        self.products = QComboBox()
        self.products.setMinimumContentsLength(25)
        self.products.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        picker.addWidget(self.products, 1)
        self.add_button = QPushButton("Añadir producto")
        self.add_button.clicked.connect(self._add_line)
        picker.addWidget(self.add_button)
        self.remove_button = QPushButton("Quitar línea")
        self.remove_button.clicked.connect(self._remove_line)
        picker.addWidget(self.remove_button)
        layout.addLayout(picker)
        lot_picker = QHBoxLayout()
        lot_picker.addWidget(QLabel("Lote:"))
        self.lots = QComboBox()
        self.lots.setMinimumContentsLength(30)
        self.lots.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        lot_picker.addWidget(self.lots, 1)
        layout.addLayout(lot_picker)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Producto", "Envases", "Tarifa €/envase", "Importe €",
            "Entrega prevista", "Caducidad", "Estado", "Lote / almacén", "Stock consultado",
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 260)
        layout.addWidget(self.table)
        self.total = QLabel()
        layout.addWidget(self.total)
        note = QLabel(
            "Fechas pendientes hasta su confirmación. Introduce la caducidad facilitada por el proveedor.\n"
            "Stock informativo al seleccionar el producto; no se reserva. Una línea por lote.\n"
            "Importes de tarifa sin añadir impuestos ni transporte. Previsión temporal: se descarta al cerrar."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.reject)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.year.valueChanged.connect(self._load_catalog)
        self.search.textChanged.connect(self._filter_products)
        self.products.currentIndexChanged.connect(self._load_lots)
        self._load_catalog()

    def _load_catalog(self):
        try:
            name, products = self.service.catalog(self.customer_id, self.year.value())
        except Exception as exc:
            self.distributor.setText(f"No se pudo cargar la tarifa: {exc}")
            products = []
        else:
            self.distributor.setText(f"Tarifa aplicada: {name}")
        self._catalog = products
        self._filter_products()
        if not products and not self.distributor.text().startswith("No se pudo"):
            self.distributor.setText(self.distributor.text() + " · Sin productos activos")
        self._recalculate()

    @staticmethod
    def _search_text(text):
        return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if not unicodedata.combining(c))

    def _filter_products(self):
        words = self._search_text(self.search.text()).split()
        products = [p for p in self._catalog if all(w in self._search_text(p.label) for w in words)]
        self.products.blockSignals(True)
        self.products.clear()
        for product in products:
            suffix = " — Sin tarifa" if product.price is None else ""
            self.products.addItem(product.label + suffix, product)
        self.add_button.setEnabled(bool(products))
        self.products.blockSignals(False)
        self.matches.setText(f"{len(products)} productos encontrados" if products else "Sin coincidencias")
        self._load_lots()

    def _load_lots(self):
        self.lots.clear()
        self.lots.addItem("Sin lote confirmado · Caducidad pendiente", None)
        product = self.products.currentData()
        self.lots.setEnabled(product is not None)
        if product is None:
            return
        try:
            lots = self.service.lots(product.article_id)
        except Exception as exc:
            self.lots.setItemText(0, f"No se pudo consultar stock: {exc} · Sin lote confirmado")
            return
        for lot in lots:
            expiry = lot.expiry.strftime("%d/%m/%Y") if lot.expiry else "Pendiente"
            self.lots.addItem(
                f"{lot.lot or 'Sin número'} · {lot.warehouse_name} · Caducidad: {expiry} · {lot.available:g} envases",
                lot,
            )
        if not lots:
            self.lots.setItemText(0, "Sin stock disponible · Sin lote confirmado")

    @staticmethod
    def _date_editor():
        editor = QDateEdit()
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("dd/MM/yyyy")
        editor.setMinimumDate(QDate(1900, 1, 1))
        editor.setSpecialValueText("Pendiente")
        editor.setDate(editor.minimumDate())
        today = QDate.currentDate()
        editor.calendarWidget().setCurrentPage(today.year(), today.month())
        return editor

    def _add_line(self):
        product = self.products.currentData()
        if product is None:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        item = QTableWidgetItem(product.label)
        item.setData(Qt.ItemDataRole.UserRole, product)
        lot = self.lots.currentData()
        item.setData(Qt.ItemDataRole.UserRole + 1, lot)
        self.table.setItem(row, 0, item)
        self.table.setItem(row, 7, QTableWidgetItem(
            f"{lot.lot or 'Sin número'} / {lot.warehouse_name}" if lot else "Sin confirmar"
        ))
        self.table.setItem(row, 8, QTableWidgetItem(f"{lot.available:g}" if lot else "—"))
        quantity = QSpinBox()
        quantity.setRange(1, 1000000)
        self.table.setCellWidget(row, 1, quantity)
        quantity.valueChanged.connect(self._recalculate)
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

    def reject(self):
        if self.table.rowCount() and QMessageBox.question(
            self, "Cerrar previsión", "La previsión no se guarda. ¿Descartar y cerrar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        super().reject()

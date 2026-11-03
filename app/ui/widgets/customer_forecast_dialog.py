from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QDialog, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QSpinBox,
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
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Producto", "Envases", "Tarifa €/envase", "Importe €",
            "Entrega prevista", "Caducidad", "Estado",
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        self.total = QLabel()
        layout.addWidget(self.total)
        note = QLabel(
            "Fechas pendientes hasta su confirmación. Introduce la caducidad facilitada por el proveedor.\n"
            "Importes de tarifa sin añadir impuestos ni transporte. Previsión temporal: se descarta al cerrar."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.reject)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.year.valueChanged.connect(self._load_catalog)
        self._load_catalog()

    def _load_catalog(self):
        self.products.clear()
        try:
            name, products = self.service.catalog(self.customer_id, self.year.value())
        except Exception as exc:
            self.distributor.setText(f"No se pudo cargar la tarifa: {exc}")
            products = []
        else:
            self.distributor.setText(f"Tarifa aplicada: {name}")
        for product in products:
            suffix = " — Sin tarifa" if product.price is None else ""
            self.products.addItem(product.label + suffix, product)
        self.add_button.setEnabled(bool(products))
        if not products and not self.distributor.text().startswith("No se pudo"):
            self.distributor.setText(self.distributor.text() + " · Sin productos activos")
        self._recalculate()

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
        self.table.setItem(row, 0, item)
        quantity = QSpinBox()
        quantity.setRange(1, 1000000)
        self.table.setCellWidget(row, 1, quantity)
        quantity.valueChanged.connect(self._recalculate)
        for column in (4, 5):
            editor = self._date_editor()
            self.table.setCellWidget(row, column, editor)
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

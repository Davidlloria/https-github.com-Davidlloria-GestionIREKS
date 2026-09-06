from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView, QDateEdit, QDialog, QDialogButtonBox, QHeaderView,
    QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.services.cadelsa_order_import_service import CadelsaPreview


class CadelsaOrderPreviewDialog(QDialog):
    def __init__(self, preview: CadelsaPreview, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Importar pedido CADELSA LZA")
        self.resize(1000, 640)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selecciona la fecha del pedido. Se asignará un número interno al guardar."))
        self.order_date = QDateEdit(QDate.currentDate())
        self.order_date.setCalendarPopup(True)
        self.order_date.setDisplayFormat("dd/MM/yyyy")
        layout.addWidget(self.order_date)
        table = QTableWidget(len(preview.lines), 7)
        self.table = table
        table.setHorizontalHeaderLabels(["Ref. IGSA", "Ref. producto", "Producto", "Unidades", "Kg/envase", "Total kg", "Incidencia"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for index, row in enumerate(preview.lines):
            values = [row.source.code, row.reference, row.name or row.source.description,
                      f"{row.source.units:g}", f"{row.source.weight_kg:g}",
                      f"{row.source.units * row.source.weight_kg:g}", row.issue]
            for column, value in enumerate(values):
                table.setItem(index, column, QTableWidgetItem(value))
        layout.addWidget(table)
        total = sum(row.source.units * row.source.weight_kg for row in preview.lines)
        layout.addWidget(QLabel(f"{len(preview.lines)} líneas · Total: {total:g} kg"))
        has_issues = not preview.lines or any(row.issue for row in preview.lines)
        if has_issues:
            message = QLabel("Corrige las equivalencias o fichas de producto y vuelve a importar. No se guardará un pedido incompleto.")
            message.setWordWrap(True)
            layout.addWidget(message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.save_button = buttons.addButton("Guardar pedido", QDialogButtonBox.ButtonRole.AcceptRole)
        self.save_button.setEnabled(not has_issues)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

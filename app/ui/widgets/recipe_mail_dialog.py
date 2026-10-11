from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.services.customer_contact_flow_service import CustomerContactFlowService
from app.services.recipe_mail_service import normalize_recipients


class RecipeMailDialog(QDialog):
    def __init__(self, parent=None, *, customer_id: str, recipe_name: str, contact_service=None):
        super().__init__(parent)
        self.setWindowTitle("Enviar receta por el nuevo Outlook")
        self.resize(650, 500)
        self.recipients: list[str] = []
        layout = QVBoxLayout(self)
        self.status = QLabel("Selecciona los contactos destinatarios. El correo se abrirá para tu revisión.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.contacts_table = QTableWidget(0, 2)
        self.contacts_table.setHorizontalHeaderLabels(["Contacto", "Correo"])
        self.contacts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.contacts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.contacts_table)
        contacts = []
        if customer_id:
            try:
                contacts = (contact_service or CustomerContactFlowService()).related_contacts(customer_id)
            except Exception as exc:
                self.status.setText(f"No se pudieron consultar los contactos: {exc}. Puedes introducir el correo manualmente.")
            else:
                if not contacts:
                    self.status.setText("El cliente no tiene contactos. Puedes introducir el correo manualmente.")
        else:
            self.status.setText("La receta no tiene cliente asociado. Introduce el correo manualmente.")
        self.contacts_table.setRowCount(len(contacts))
        usable = 0
        for row, contact in enumerate(contacts):
            email = str(contact.email or "").strip()
            name = " ".join(filter(None, [contact.nombre, contact.apellidos])) or "Sin nombre"
            item = QTableWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, email)
            try:
                valid = bool(normalize_recipients([email]))
            except ValueError:
                valid = False
            if valid:
                usable += 1
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
            else:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setToolTip("Contacto sin correo válido")
            self.contacts_table.setItem(row, 0, item)
            self.contacts_table.setItem(row, 1, QTableWidgetItem(email or "Sin correo"))
        if contacts and not usable:
            self.status.setText("Los contactos no tienen correos válidos. Introduce el correo manualmente.")
        layout.addWidget(QLabel("Otros destinatarios (separados por punto y coma):"))
        self.manual_recipients = QLineEdit()
        layout.addWidget(self.manual_recipients)
        layout.addWidget(QLabel("Asunto:"))
        self.subject = QLineEdit(f"Receta: {recipe_name}")
        layout.addWidget(self.subject)
        layout.addWidget(QLabel("Mensaje:"))
        self.body = QPlainTextEdit("Hola,\n\nAdjunto la receta en PDF con los documentos seleccionados.\n\nUn saludo.")
        layout.addWidget(self.body)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Abrir en nuevo Outlook")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        addresses = [self.manual_recipients.text()]
        for row in range(self.contacts_table.rowCount()):
            item = self.contacts_table.item(row, 0)
            if item.checkState() == Qt.CheckState.Checked:
                addresses.append(item.data(Qt.ItemDataRole.UserRole))
        try:
            self.recipients = normalize_recipients(addresses)
            if not self.recipients:
                raise ValueError("Selecciona un contacto o introduce un destinatario.")
        except ValueError as exc:
            QMessageBox.warning(self, "Destinatarios", str(exc))
            return
        super().accept()

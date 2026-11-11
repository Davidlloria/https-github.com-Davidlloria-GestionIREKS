from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from app.core.config import DATA_DIR
from app.services.customer_contact_flow_service import CustomerContactFlowService
from app.services.customer_service import CustomerService
from app.services.recipe_mail_service import normalize_recipients


class TechnicalSheetMailDialog(QDialog):
    def __init__(self, documents, parent=None, *, customer_service=None, contact_service=None):
        super().__init__(parent)
        self.setWindowTitle("Enviar fichas técnicas")
        self.resize(650, 600)
        self.recipients = []
        self._contacts = contact_service or CustomerContactFlowService()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Fichas seleccionadas:"))
        self.documents = QListWidget()
        for document_id, name in documents.items():
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, document_id)
            self.documents.addItem(item)
        layout.addWidget(self.documents)
        remove = QPushButton("Quitar ficha seleccionada")
        remove.clicked.connect(self._remove_document)
        layout.addWidget(remove)
        layout.addWidget(QLabel("Cliente (opcional):"))
        self.customers = QComboBox()
        self.customers.addItem("Selecciona un cliente", None)
        self.status = QLabel("Para el distribuidor puedes introducir su correo manualmente.")
        self.status.setWordWrap(True)
        try:
            for customer in (customer_service or CustomerService()).list():
                name = customer.cliente_nombre_comercial or customer.cliente_nombre_fiscal or str(customer.cliente_codigo)
                self.customers.addItem(name, (customer.cliente_id, customer.cliente_email))
        except Exception as exc:
            self.status.setText(f"No se pudieron cargar los clientes: {exc}. Introduce el correo manualmente.")
        layout.addWidget(self.customers)
        self.contacts = QListWidget()
        self.contacts.setMaximumHeight(110)
        layout.addWidget(self.contacts)
        self.customers.currentIndexChanged.connect(self._load_contacts)
        layout.addWidget(self.status)
        layout.addWidget(QLabel("Otros destinatarios (separados por punto y coma):"))
        self.manual_recipients = QLineEdit()
        layout.addWidget(self.manual_recipients)
        layout.addWidget(QLabel("Asunto:"))
        self.subject = QLineEdit("Fichas técnicas")
        layout.addWidget(self.subject)
        layout.addWidget(QLabel("Mensaje:"))
        self.body = QPlainTextEdit("Hola,\n\nAdjunto las fichas técnicas solicitadas.\n\nUn saludo.")
        layout.addWidget(self.body)
        self.include_signature = QCheckBox("Incluir firma guardada de Outlook")
        available = (DATA_DIR / "recipe_mail_signature.json").is_file()
        self.include_signature.setEnabled(available)
        self.include_signature.setChecked(available)
        layout.addWidget(self.include_signature)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Abrir en nuevo Outlook")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _remove_document(self):
        row = self.documents.currentRow()
        if row >= 0:
            self.documents.takeItem(row)

    def _load_contacts(self):
        self.contacts.clear()
        customer = self.customers.currentData()
        if not customer:
            return
        customer_id, email = customer
        entries = [("Correo del cliente", email)]
        try:
            entries += [(" ".join(filter(None, (contact.nombre, contact.apellidos))), contact.email)
                        for contact in self._contacts.related_contacts(customer_id)]
        except Exception as exc:
            self.status.setText(f"No se pudieron cargar los contactos: {exc}. Puedes introducir el correo manualmente.")
        for name, address in entries:
            try:
                valid = bool(normalize_recipients([str(address or "")]))
            except ValueError:
                valid = False
            item = QListWidgetItem(f"{name}: {address or 'Sin correo'}")
            item.setData(Qt.ItemDataRole.UserRole, address)
            if valid:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
            else:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.contacts.addItem(item)

    def accept(self):
        if not self.documents.count():
            QMessageBox.warning(self, "Fichas técnicas", "Selecciona al menos una ficha.")
            return
        addresses = [self.manual_recipients.text()]
        addresses += [self.contacts.item(i).data(Qt.ItemDataRole.UserRole)
                      for i in range(self.contacts.count())
                      if self.contacts.item(i).checkState() == Qt.CheckState.Checked]
        try:
            self.recipients = normalize_recipients(addresses)
            if not self.recipients:
                raise ValueError("Selecciona un contacto o introduce un destinatario.")
        except ValueError as exc:
            QMessageBox.warning(self, "Destinatarios", str(exc))
            return
        super().accept()

    def selected_document_ids(self):
        return [self.documents.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.documents.count())]

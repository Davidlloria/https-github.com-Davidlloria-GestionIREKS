from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QLabel, QLineEdit,
    QHBoxLayout, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from app.core.config import DATA_DIR
from app.services.customer_contact_flow_service import CustomerContactFlowService
from app.services.customer_service import CustomerService
from app.services.distributor_service import DistributorService
from app.services.recipe_mail_service import normalize_recipients


class TechnicalSheetMailDialog(QDialog):
    def __init__(self, documents, parent=None, *, customer_service=None, contact_service=None, distributor_service=None):
        super().__init__(parent)
        self.setWindowTitle("Enviar fichas técnicas")
        self.resize(1050, 680)
        self.recipients = []
        self._contacts = contact_service or CustomerContactFlowService()
        layout = QVBoxLayout(self)
        columns = QHBoxLayout()
        left = QVBoxLayout()
        right = QVBoxLayout()
        columns.addLayout(left, 2)
        columns.addLayout(right, 3)
        layout.addLayout(columns, 1)
        left.addWidget(QLabel("Fichas seleccionadas:"))
        self.documents = QListWidget()
        for document_id, name in documents.items():
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, document_id)
            self.documents.addItem(item)
        left.addWidget(self.documents, 1)
        remove = QPushButton("Quitar ficha seleccionada")
        remove.clicked.connect(self._remove_document)
        left.addWidget(remove)
        right.addWidget(QLabel("Buscar cliente o distribuidor:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Escribe parte del nombre…")
        right.addWidget(self.search)
        self.customers = QComboBox()
        self._recipients = []
        self.status = QLabel("Para el distribuidor puedes introducir su correo manualmente.")
        self.status.setWordWrap(True)
        errors = []
        try:
            for customer in (customer_service or CustomerService()).list():
                name = customer.cliente_nombre_comercial or customer.cliente_nombre_fiscal or str(customer.cliente_codigo)
                self._recipients.append((f"Cliente: {name}", ("customer", customer.cliente_id, customer.cliente_email),
                                         f"{name} {customer.cliente_nombre_fiscal}".casefold()))
        except Exception as exc:
            errors.append(f"clientes: {exc}")
        try:
            for distributor in (distributor_service or DistributorService()).list():
                name = distributor.distribuidor_nombre_comercial or distributor.distribuidor_razon_social or str(distributor.distribuidor_codigo)
                self._recipients.append((f"Distribuidor: {name}", ("distributor", distributor.distribuidor_id, ""),
                                         f"{name} {distributor.distribuidor_razon_social}".casefold()))
        except Exception as exc:
            errors.append(f"distribuidores: {exc}")
        if errors:
            self.status.setText(f"No se pudieron cargar {', '.join(errors)}. Puedes introducir el correo manualmente.")
        self._filter_recipients()
        self.search.textChanged.connect(self._filter_recipients)
        right.addWidget(self.customers)
        self.contacts = QListWidget()
        self.contacts.setMaximumHeight(110)
        right.addWidget(self.contacts)
        self.customers.currentIndexChanged.connect(self._load_contacts)
        right.addWidget(self.status)
        right.addWidget(QLabel("Otros destinatarios (separados por punto y coma):"))
        self.manual_recipients = QLineEdit()
        right.addWidget(self.manual_recipients)
        right.addWidget(QLabel("Asunto:"))
        self.subject = QLineEdit("Fichas técnicas")
        right.addWidget(self.subject)
        right.addWidget(QLabel("Mensaje:"))
        self.body = QPlainTextEdit("Hola,\n\nAdjunto las fichas técnicas solicitadas.\n\nUn saludo.")
        self.body.setMinimumHeight(180)
        right.addWidget(self.body, 1)
        self.include_signature = QCheckBox("Incluir firma guardada de Outlook")
        available = (DATA_DIR / "recipe_mail_signature.json").is_file()
        self.include_signature.setEnabled(available)
        self.include_signature.setChecked(available)
        right.addWidget(self.include_signature)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Abrir en nuevo Outlook")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _remove_document(self):
        row = self.documents.currentRow()
        if row >= 0:
            self.documents.takeItem(row)

    def _filter_recipients(self, *_args):
        query = self.search.text().strip().casefold()
        self.customers.clear()
        self.customers.addItem("Selecciona un cliente o distribuidor", None)
        for label, value, search_text in self._recipients:
            if query in search_text:
                self.customers.addItem(label, value)

    def _load_contacts(self):
        self.contacts.clear()
        customer = self.customers.currentData()
        if not customer:
            return
        kind, customer_id, email = customer
        if kind == "distributor":
            self.status.setText("El distribuidor no tiene correo guardado. Introduce su dirección manualmente.")
            return
        self.status.setText("Selecciona el correo del cliente o de sus contactos, o introduce otra dirección.")
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

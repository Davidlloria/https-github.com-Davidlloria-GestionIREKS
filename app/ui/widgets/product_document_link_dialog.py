from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
)

from app.services.document_product_link_service import TECHNICAL_SHEET_AREA


class ProductDocumentLinkDialog(QDialog):
    def __init__(self, product_id, product_name, links, library, parent=None):
        super().__init__(parent)
        self.product_id = product_id
        self.links = links
        self.library = library
        self.check = None
        self.setWindowTitle("Vincular documento")
        self.resize(760, 540)
        layout = QVBoxLayout(self)
        product_label = QLabel(f"Producto: {product_name}")
        product_label.setTextFormat(Qt.TextFormat.PlainText)
        product_label.setWordWrap(True)
        layout.addWidget(product_label)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar ficha técnica por nombre o ruta…")
        layout.addWidget(self.search)
        self.documents = QListWidget()
        layout.addWidget(self.documents, 1)
        self.evidence = QLabel("Selecciona una ficha técnica de la biblioteca.")
        self.evidence.setTextFormat(Qt.TextFormat.PlainText)
        self.evidence.setWordWrap(True)
        layout.addWidget(self.evidence)
        self.reviewed = QCheckBox("He revisado el contenido y confirmo que pertenece a este producto")
        self.reviewed.setEnabled(False)
        layout.addWidget(self.reviewed)
        buttons = QHBoxLayout()
        self.open_button = QPushButton("Abrir para revisar")
        self.save_button = QPushButton("Confirmar vinculación")
        cancel = QPushButton("Cancelar")
        for button in (self.open_button, self.save_button, cancel):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.open_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.open_button.clicked.connect(self._open)
        self.save_button.clicked.connect(self._save)
        cancel.clicked.connect(self.reject)
        self.reviewed.toggled.connect(self._update_save)
        self.documents.currentItemChanged.connect(self._select)
        self.search.textChanged.connect(self._filter)
        try:
            for document in library.list_documents(area=TECHNICAL_SHEET_AREA):
                item = QListWidgetItem(document.relative_path)
                item.setData(Qt.ItemDataRole.UserRole, document.document_id)
                self.documents.addItem(item)
            if not self.documents.count():
                self.evidence.setText("No hay fichas técnicas. Actualiza el catálogo en Documentos.")
        except Exception as exc:
            self.evidence.setText(f"No se pudo consultar la biblioteca: {exc}")

    def _filter(self, text):
        self.documents.setCurrentRow(-1)
        for row in range(self.documents.count()):
            item = self.documents.item(row)
            item.setHidden(text.casefold() not in item.text().casefold())

    def _document_id(self):
        item = self.documents.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _select(self, *_args):
        self.check = None
        self.reviewed.setChecked(False)
        self.reviewed.setEnabled(False)
        self.open_button.setEnabled(False)
        self.save_button.setEnabled(False)
        document_id = self._document_id()
        if not document_id:
            self.evidence.setText("Selecciona una ficha técnica de la biblioteca.")
            return
        try:
            self.check = self.links.check_manual_link(self.product_id, document_id)
            check = self.check
            status = {
                "exact": "Coincidencia exacta de fabricante y código (según carpeta y nombre).",
                "review": "Datos insuficientes: abre el documento y revisa su contenido.",
                "conflict": "Vinculación bloqueada: el fabricante o el código no coincide.",
            }[check.status]
            self.evidence.setText(
                f"{status}\n"
                f"Producto — fabricante: {check.product_manufacturer or 'Sin dato'}; "
                f"código: {check.product_code or 'Sin dato'}.\n"
                f"Documento — fabricante: {check.document_manufacturer or 'Sin dato'}; "
                f"código: {check.document_code or 'Sin dato'}."
            )
            self.open_button.setEnabled(True)
        except Exception as exc:
            self.evidence.setText(str(exc))
        self._update_save()

    def _update_save(self, *_args):
        self.save_button.setEnabled(bool(self.check and (
            self.check.status == "exact"
            or (self.check.status == "review" and self.reviewed.isChecked())
        )))

    def _open(self):
        try:
            path = self.library.resolve_document(self._document_id())
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise RuntimeError("Windows no pudo abrir el documento.")
            self.reviewed.setEnabled(bool(self.check and self.check.status == "review"))
        except Exception as exc:
            QMessageBox.warning(self, "Documento", str(exc))

    def _save(self):
        if not self.save_button.isEnabled():
            return
        try:
            document_id = self._document_id()
            self.library.resolve_document(document_id)
            self.links.link_manual(self.product_id, document_id, reviewed=self.reviewed.isChecked())
        except Exception as exc:
            QMessageBox.warning(self, "Vinculación", str(exc))
            return
        self.accept()

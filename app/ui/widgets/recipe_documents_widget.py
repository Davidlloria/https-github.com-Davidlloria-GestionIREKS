from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.services.recipe_documents_service import RecipeDocumentsService


class RecipeDocumentsWidget(QWidget):
    def __init__(self, parent=None, service=None):
        super().__init__(parent)
        self.service = service or RecipeDocumentsService()
        self.recipe_key = None
        self.documents = []
        self.error = ""
        layout = QVBoxLayout(self)
        self.status = QLabel("Selecciona una receta para ver sus fichas técnicas.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Incluir", "Producto", "Ficha técnica", "Estado"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        self.open_button = QPushButton("Abrir ficha técnica")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_selected)
        self.table.itemSelectionChanged.connect(self._update_open_button)
        self.table.cellDoubleClicked.connect(lambda *_: self.open_selected())
        layout.addWidget(self.open_button)

    def refresh(self, recipe_key, lines):
        selected = {}
        if self.recipe_key == recipe_key:
            for row, doc in enumerate(self.documents):
                if doc.path:
                    selected[(doc.product, doc.document_id)] = self.table.item(row, 0).checkState()
        self.recipe_key = recipe_key
        self.error = ""
        try:
            self.documents = self.service.list_documents(lines)
        except Exception as exc:
            self.documents = []
            self.error = f"No se pudieron consultar las fichas técnicas: {exc}"
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.documents))
        for row, doc in enumerate(self.documents):
            check = QTableWidgetItem()
            if doc.path:
                check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
                check.setCheckState(selected.get((doc.product, doc.document_id), Qt.CheckState.Checked))
            else:
                check.setFlags(Qt.ItemFlag.NoItemFlags)
            self.table.setItem(row, 0, check)
            for column, value in enumerate((doc.product, doc.name or "—", doc.status), 1):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        self.status.setText(self.error or (
            "Selecciona las fichas que se añadirán después de la receta en el PDF."
            if self.documents else "La receta no contiene productos del catálogo propio."
        ))
        self._update_open_button()

    def selected_paths(self):
        return list(dict.fromkeys(doc.path for row, doc in enumerate(self.documents)
                                 if doc.path and self.table.item(row, 0).checkState() == Qt.CheckState.Checked))

    def issues(self):
        return ([self.error] if self.error else []) + [
            f"{doc.product}: {doc.status}" for doc in self.documents if not doc.path
        ]

    def _update_open_button(self):
        row = self.table.currentRow()
        self.open_button.setEnabled(0 <= row < len(self.documents) and self.documents[row].path is not None)

    def open_selected(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.documents) and self.documents[row].path:
            path = self.documents[row].path
            if not path.is_file() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                QMessageBox.warning(self, "Documentos", "No se pudo abrir la ficha técnica.")

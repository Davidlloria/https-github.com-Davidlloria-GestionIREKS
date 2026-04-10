from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets.entity_dialog import EntityDialog


class EntityPage(QWidget):
    def __init__(
        self,
        title: str,
        columns: list[tuple[str, str]],
        schema: list[dict[str, Any]],
        list_fn: Callable[..., list[Any]],
        create_fn: Callable[[dict[str, Any]], Any],
        update_fn: Callable[[int, dict[str, Any]], Any],
        delete_fn: Callable[[int], bool],
        include_filters: bool = False,
        import_fn: Callable[[str], tuple[int, list[str]]] | None = None,
    ) -> None:
        super().__init__()
        self.title = title
        self.columns = columns
        self.schema = schema
        self.list_fn = list_fn
        self.create_fn = create_fn
        self.update_fn = update_fn
        self.delete_fn = delete_fn
        self.include_filters = include_filters
        self.import_fn = import_fn
        self.rows: list[Any] = []

        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel(self.title)
        header.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(header)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar...")
        self.search_input.textChanged.connect(self.reload)
        toolbar.addWidget(self.search_input, 2)

        self.familia_filter: QComboBox | None = None
        self.subfamilia_filter: QComboBox | None = None
        if self.include_filters:
            self.familia_filter = QComboBox()
            self.familia_filter.addItem("Familia (todas)")
            self.familia_filter.currentTextChanged.connect(self.reload)
            self.subfamilia_filter = QComboBox()
            self.subfamilia_filter.addItem("Subfamilia (todas)")
            self.subfamilia_filter.currentTextChanged.connect(self.reload)
            toolbar.addWidget(self.familia_filter, 1)
            toolbar.addWidget(self.subfamilia_filter, 1)

        new_btn = QPushButton("Nuevo")
        edit_btn = QPushButton("Editar")
        del_btn = QPushButton("Eliminar")
        refresh_btn = QPushButton("Refrescar")
        import_btn = QPushButton("Importar Excel/CSV")

        new_btn.clicked.connect(self._new_entity)
        edit_btn.clicked.connect(self._edit_entity)
        del_btn.clicked.connect(self._delete_entity)
        refresh_btn.clicked.connect(self.reload)
        import_btn.clicked.connect(self._import_entities)

        toolbar.addWidget(new_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(del_btn)
        if self.import_fn:
            toolbar.addWidget(import_btn)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, len(self.columns))
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setHorizontalHeaderLabels([label for _, label in self.columns])
        layout.addWidget(self.table)

    def reload(self) -> None:
        term = self.search_input.text().strip()
        familia = ""
        subfamilia = ""
        if self.include_filters and self.familia_filter and self.subfamilia_filter:
            familia = self.familia_filter.currentText()
            subfamilia = self.subfamilia_filter.currentText()
            familia = "" if familia.startswith("Familia") else familia
            subfamilia = "" if subfamilia.startswith("Subfamilia") else subfamilia
            self.rows = self.list_fn(term, familia, subfamilia)
            self._reload_filter_values()
        else:
            self.rows = self.list_fn(term)
        self._render_table()

    def _reload_filter_values(self) -> None:
        if not self.include_filters or not self.familia_filter or not self.subfamilia_filter:
            return

        familias = sorted({row.familia for row in self.rows if row.familia})
        subfamilias = sorted({row.subfamilia for row in self.rows if row.subfamilia})

        current_familia = self.familia_filter.currentText()
        current_subfamilia = self.subfamilia_filter.currentText()

        self.familia_filter.blockSignals(True)
        self.subfamilia_filter.blockSignals(True)

        self.familia_filter.clear()
        self.familia_filter.addItem("Familia (todas)")
        self.familia_filter.addItems(familias)
        if current_familia in familias:
            self.familia_filter.setCurrentText(current_familia)

        self.subfamilia_filter.clear()
        self.subfamilia_filter.addItem("Subfamilia (todas)")
        self.subfamilia_filter.addItems(subfamilias)
        if current_subfamilia in subfamilias:
            self.subfamilia_filter.setCurrentText(current_subfamilia)

        self.familia_filter.blockSignals(False)
        self.subfamilia_filter.blockSignals(False)

    def _render_table(self) -> None:
        self.table.setRowCount(len(self.rows))
        for row_idx, item in enumerate(self.rows):
            for col_idx, (attr, _) in enumerate(self.columns):
                value = getattr(item, attr, "")
                if isinstance(value, bool):
                    text = "Si" if value else "No"
                elif isinstance(value, float):
                    text = f"{value:.4f}".rstrip("0").rstrip(".")
                else:
                    text = str(value)
                table_item = QTableWidgetItem(text)
                table_item.setData(Qt.UserRole, getattr(item, "id", None))
                self.table.setItem(row_idx, col_idx, table_item)

    def _selected_row(self) -> Any | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        return self.rows[row]

    def _new_entity(self) -> None:
        dialog = EntityDialog(f"Nuevo: {self.title}", self.schema, parent=self)
        if dialog.exec():
            payload = dialog.get_payload()
            self.create_fn(payload)
            self.reload()

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un registro.")
            return
        initial = {field["name"]: getattr(row, field["name"], None) for field in self.schema}
        dialog = EntityDialog(f"Editar: {self.title}", self.schema, initial=initial, parent=self)
        if dialog.exec():
            payload = dialog.get_payload()
            self.update_fn(row.id, payload)
            self.reload()

    def _delete_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un registro.")
            return
        answer = QMessageBox.question(
            self,
            "Confirmar",
            f"Eliminar registro {getattr(row, 'codigo', row.id)}?",
        )
        if answer == QMessageBox.Yes:
            self.delete_fn(row.id)
            self.reload()

    def _import_entities(self) -> None:
        if not self.import_fn:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo",
            "",
            "Archivos de datos (*.xlsx *.xlsm *.csv)",
        )
        if not file_path:
            return
        imported, errors = self.import_fn(file_path)
        self.reload()
        if errors:
            preview = "\n".join(errors[:8])
            extra = "" if len(errors) <= 8 else f"\n... y {len(errors) - 8} errores mas."
            QMessageBox.warning(
                self,
                "Importacion completada con incidencias",
                f"Registros importados: {imported}\nErrores: {len(errors)}\n\n{preview}{extra}",
            )
            return
        QMessageBox.information(self, "Importacion completada", f"Registros importados: {imported}")

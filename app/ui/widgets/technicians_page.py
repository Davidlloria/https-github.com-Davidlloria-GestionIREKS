from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from app.services.technician_service import TechnicianService
from app.ui.widgets.entity_dialog import EntityDialog


class TechniciansPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.service = TechnicianService()
        self.rows: list = []
        self._is_loading_details = False
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.reload)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_selected)
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        header = QLabel("Tecnicos")
        header.setProperty("role", "pageTitle")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_panel.setObjectName("sidePanel")
        left_layout = QVBoxLayout(left_panel)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nombre, movil, interno o email...")
        self.search_input.textChanged.connect(self._schedule_reload)
        left_layout.addWidget(self.search_input)

        self.table = QTableWidget(0, 2)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        table_header = self.table.horizontalHeader()
        table_header.setSectionsClickable(True)
        table_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setHorizontalHeaderLabels(["Codigo", "Tecnico"])
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        left_layout.addWidget(self.table, 1)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        ribbon = QFrame()
        ribbon.setObjectName("topRibbon")
        ribbon.setFrameShape(QFrame.Shape.StyledPanel)
        ribbon_layout = QHBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(8, 6, 8, 6)
        ribbon_layout.setSpacing(6)
        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setProperty("btnRole", "success")
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setProperty("btnRole", "warning")
        self.del_btn = QPushButton("Eliminar")
        self.del_btn.setProperty("btnRole", "danger")
        self.id_btn = QPushButton("ID")
        self.id_btn.setProperty("btnRole", "secondary")
        self.import_btn = QPushButton("Importar Excel/CSV")
        self.import_btn.setProperty("btnRole", "secondary")
        self.refresh_btn = QPushButton("Refrescar")
        self.refresh_btn.setProperty("btnRole", "secondary")
        self.new_btn.clicked.connect(self._new_entity)
        self.edit_btn.clicked.connect(self._edit_entity)
        self.del_btn.clicked.connect(self._delete_entity)
        self.id_btn.clicked.connect(self._show_id_dialog)
        self.import_btn.clicked.connect(self._import_entities)
        self.refresh_btn.clicked.connect(self.reload)
        ribbon_layout.addWidget(self.new_btn)
        ribbon_layout.addWidget(self.edit_btn)
        ribbon_layout.addWidget(self.del_btn)
        ribbon_layout.addWidget(self.id_btn)
        ribbon_layout.addWidget(self.import_btn)
        ribbon_layout.addWidget(self.refresh_btn)
        ribbon_layout.addStretch(1)
        right_layout.addWidget(ribbon)

        detail_panel = QWidget()
        detail_panel.setObjectName("detailPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(8)
        detail_title = QLabel("Detalle de tecnico")
        detail_title.setProperty("role", "sectionTitle")
        detail_layout.addWidget(detail_title)

        row_1 = QHBoxLayout()
        row_1.addWidget(QLabel("Codigo"))
        self.detail_codigo = QLineEdit()
        self.detail_codigo.setReadOnly(True)
        row_1.addWidget(self.detail_codigo, 1)
        row_1.addWidget(QLabel("Interno"))
        self.detail_interno = QLineEdit()
        row_1.addWidget(self.detail_interno, 1)
        detail_layout.addLayout(row_1)

        row_2 = QHBoxLayout()
        row_2.addWidget(QLabel("Nombre"))
        self.detail_nombre = QLineEdit()
        row_2.addWidget(self.detail_nombre, 2)
        row_2.addWidget(QLabel("Apellidos"))
        self.detail_apellidos = QLineEdit()
        row_2.addWidget(self.detail_apellidos, 3)
        detail_layout.addLayout(row_2)

        row_3 = QHBoxLayout()
        row_3.addWidget(QLabel("Movil"))
        self.detail_movil = QLineEdit()
        row_3.addWidget(self.detail_movil, 1)
        row_3.addWidget(QLabel("Email"))
        self.detail_email = QLineEdit()
        row_3.addWidget(self.detail_email, 2)
        detail_layout.addLayout(row_3)
        detail_layout.addStretch(1)

        for field in (self.detail_nombre, self.detail_apellidos, self.detail_movil, self.detail_interno, self.detail_email):
            field.textEdited.connect(self._schedule_autosave)

        right_layout.addWidget(detail_panel, 1)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        splitter.handle(1).setEnabled(False)

    def _list(self, term: str) -> list:
        return self.service.list(term)

    def _create(self, payload: dict) -> None:
        self.service.create(payload)

    def _update(self, tecnico_id: str, payload: dict) -> None:
        self.service.update(tecnico_id, payload)

    def _delete(self, tecnico_id: str) -> bool:
        return self.service.delete(tecnico_id)

    def _import(self, file_path: str) -> tuple[int, list[str]]:
        return self.service.import_file(Path(file_path))
        schema = [
            {"name": "tecnico_id", "label": "tecnico_id"},
            {"name": "tecnico_codigo", "label": "codigo"},
            {"name": "nombre", "label": "Nombre"},
            {"name": "apellidos", "label": "Apellidos"},
            {"name": "movil", "label": "Movil"},
            {"name": "interno", "label": "interno"},
            {"name": "email", "label": "email"},
        ]
        aliases = {
            "nombre": ["nombre", "tecnico_nombre"],
            "apellidos": ["apellidos", "tecnico_apellidos"],
            "movil": ["movil", "móvil", "telefono", "tel", "telefono_movil"],
            "interno": ["interno", "ext", "extension"],
            "email": ["email", "correo", "mail"],
            "tecnico_id": ["tecnico_id", "tecnico_uuid"],
            "tecnico_codigo": ["codigo", "cod", "tecnico_codigo"],
        }

        def create_payload(payload: dict) -> None:
            self._create(
                {
                    "nombre": str(payload.get("nombre") or "").strip(),
                    "apellidos": str(payload.get("apellidos") or "").strip(),
                    "movil": str(payload.get("movil") or "").strip(),
                    "interno": str(payload.get("interno") or "").strip(),
                    "email": str(payload.get("email") or "").strip(),
                }
            )

        return self.import_service.import_with_schema(
            file_path=Path(file_path),
            schema=schema,
            create_fn=create_payload,
            required_fields=["nombre"],
            aliases=aliases,
        )

    def reload(self) -> None:
        term = self.search_input.text().strip()
        self.rows = self._list(term)
        self._render_table()
        self._show_selected_details()

    def _render_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for row_idx, item in enumerate(self.rows):
            nombre = f"{(item.nombre or '').strip()} {(item.apellidos or '').strip()}".strip()
            codigo = int(getattr(item, "tecnico_codigo", 0) or 0)
            code_item = QTableWidgetItem(str(codigo if codigo > 0 else ""))
            if codigo > 0:
                code_item.setData(Qt.ItemDataRole.DisplayRole, codigo)
            code_item.setData(Qt.ItemDataRole.UserRole, str(getattr(item, "tecnico_id", "") or ""))
            self.table.setItem(row_idx, 0, code_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(nombre))
        self.table.setSortingEnabled(True)

    def _selected_row(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        id_item = self.table.item(row_index, 0)
        if id_item is None:
            return None
        tecnico_id = str(id_item.data(Qt.ItemDataRole.UserRole) or "")
        return next((r for r in self.rows if str(getattr(r, "tecnico_id", "")) == tecnico_id), None)

    def _show_selected_details(self) -> None:
        row = self._selected_row()
        self._is_loading_details = True
        if not row:
            self.detail_codigo.clear()
            self.detail_nombre.clear()
            self.detail_apellidos.clear()
            self.detail_movil.clear()
            self.detail_interno.clear()
            self.detail_email.clear()
            self._is_loading_details = False
            return
        self.detail_codigo.setText(str(getattr(row, "tecnico_codigo", "") or ""))
        self.detail_nombre.setText(str(getattr(row, "nombre", "") or ""))
        self.detail_apellidos.setText(str(getattr(row, "apellidos", "") or ""))
        self.detail_movil.setText(str(getattr(row, "movil", "") or ""))
        self.detail_interno.setText(str(getattr(row, "interno", "") or ""))
        self.detail_email.setText(str(getattr(row, "email", "") or ""))
        self._is_loading_details = False

    def _schedule_autosave(self, *_args) -> None:
        if self._is_loading_details or not self._selected_row():
            return
        self._autosave_timer.start(350)

    def _schedule_reload(self) -> None:
        self._search_timer.start(250)

    def _autosave_selected(self) -> None:
        row = self._selected_row()
        if not row:
            return
        payload = {
            "nombre": self.detail_nombre.text().strip(),
            "apellidos": self.detail_apellidos.text().strip(),
            "movil": self.detail_movil.text().strip(),
            "interno": self.detail_interno.text().strip(),
            "email": self.detail_email.text().strip(),
        }
        try:
            self._update(str(row.tecnico_id), payload)
        except Exception as exc:
            QMessageBox.warning(self, "Guardado automatico", f"No se pudo guardar el cambio: {exc}")
            return
        self.reload()
        self._select_row_by_id(str(row.tecnico_id))

    def _select_row_by_id(self, tecnico_id: str) -> None:
        for row in range(self.table.rowCount()):
            cell = self.table.item(row, 0)
            if cell and str(cell.data(Qt.ItemDataRole.UserRole) or "") == tecnico_id:
                self.table.selectRow(row)
                break

    def _new_entity(self) -> None:
        schema = [
            {"name": "nombre", "label": "Nombre"},
            {"name": "apellidos", "label": "Apellidos"},
            {"name": "movil", "label": "Movil"},
            {"name": "interno", "label": "Interno"},
            {"name": "email", "label": "Email"},
        ]
        dialog = EntityDialog("Nuevo: Tecnico", schema, parent=self)
        if dialog.exec():
            self._create(dialog.get_payload())
            self.reload()

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un tecnico.")
            return
        schema = [
            {"name": "nombre", "label": "Nombre"},
            {"name": "apellidos", "label": "Apellidos"},
            {"name": "movil", "label": "Movil"},
            {"name": "interno", "label": "Interno"},
            {"name": "email", "label": "Email"},
        ]
        initial = {field["name"]: getattr(row, field["name"], "") for field in schema}
        dialog = EntityDialog("Editar: Tecnico", schema, initial=initial, parent=self)
        if dialog.exec():
            self._update(str(row.tecnico_id), dialog.get_payload())
            self.reload()

    def _delete_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un tecnico.")
            return
        full_name = f"{(row.nombre or '').strip()} {(row.apellidos or '').strip()}".strip()
        answer = QMessageBox.question(self, "Confirmar", f"Eliminar tecnico {full_name}?")
        if answer == QMessageBox.StandardButton.Yes:
            self._delete(str(row.tecnico_id))
            self.reload()

    def _show_id_dialog(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Tecnicos", "Selecciona un tecnico.")
            return
        tecnico_id = str(getattr(row, "tecnico_id", "") or "").strip()
        if not tecnico_id:
            QMessageBox.warning(self, "Tecnicos", "El tecnico no tiene ID.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("ID del tecnico")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        label = QLabel("ID del tecnico")
        id_field = QLineEdit(tecnico_id)
        id_field.setReadOnly(True)
        id_field.setCursorPosition(0)
        id_field.setSelection(0, 0)
        buttons = QHBoxLayout()
        copy_btn = QPushButton("Copiar")
        close_btn = QPushButton("Cerrar")
        copy_btn.setProperty("btnRole", "secondary")
        close_btn.setProperty("btnRole", "secondary")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(tecnico_id))
        close_btn.clicked.connect(dialog.accept)
        buttons.addWidget(copy_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)
        layout.addWidget(label)
        layout.addWidget(id_field)
        layout.addLayout(buttons)
        dialog.resize(460, 130)
        dialog.exec()

    def _import_entities(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo",
            "",
            "Archivos de datos (*.xlsx *.xlsm *.csv)",
        )
        if not file_path:
            return
        imported, errors = self._import(file_path)
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

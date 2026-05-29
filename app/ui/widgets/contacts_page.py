from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from app.services.contact_service import ContactService
from app.ui.widgets.entity_dialog import EntityDialog


class ContactsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.service = ContactService()
        self.rows: list = []
        self.company_id_to_name: dict[str, str] = {}
        self.company_name_to_id: dict[str, str] = {}
        self._is_loading_details = False
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.reload)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_selected_contact)
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel("Contactos")
        header.setProperty("role", "pageTitle")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_panel.setObjectName("sidePanel")
        left_layout = QVBoxLayout(left_panel)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nombre, apellidos o empresa...")
        self.search_input.textChanged.connect(self._schedule_reload)
        left_layout.addWidget(self.search_input)

        self.table = QTableWidget(0, 2)
        self.table.setObjectName("contactsTable")
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        table_header = self.table.horizontalHeader()
        table_header.setSectionsClickable(True)
        table_header.setMinimumSectionSize(120)
        table_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setHorizontalHeaderLabels(["Nombre", "Empresa"])
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        left_layout.addWidget(self.table, 1)
        self.empty_state_label = QLabel("No hay contactos todavía.\nPulsa 'Nuevo' para crear el primero.")
        self.empty_state_label.setObjectName("contactsEmptyState")
        self.empty_state_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.empty_state_label.setWordWrap(True)
        self.empty_state_label.setVisible(False)
        left_layout.addWidget(self.empty_state_label)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        ribbon = QFrame()
        ribbon.setObjectName("topRibbon")
        ribbon.setProperty("pageType", "contacts")
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
        self.import_btn = QPushButton("Importar Excel/CSV")
        self.import_btn.setProperty("btnRole", "secondary")
        self.refresh_btn = QPushButton("Refrescar")
        self.refresh_btn.setProperty("btnRole", "secondary")

        self.new_btn.clicked.connect(self._new_entity)
        self.edit_btn.clicked.connect(self._edit_entity)
        self.del_btn.clicked.connect(self._delete_entity)
        self.import_btn.clicked.connect(self._import_entities)
        self.refresh_btn.clicked.connect(self.reload)

        ribbon_layout.addWidget(self.new_btn)
        ribbon_layout.addWidget(self.edit_btn)
        ribbon_layout.addWidget(self.del_btn)
        ribbon_layout.addWidget(self.import_btn)
        ribbon_layout.addWidget(self.refresh_btn)
        ribbon_layout.addStretch(1)
        right_layout.addWidget(ribbon)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(right_splitter, 1)

        detail_panel = QWidget()
        detail_panel.setObjectName("detailPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(8)

        detail_title = QLabel("Detalle de contacto")
        detail_title.setProperty("role", "sectionTitle")
        detail_layout.addWidget(detail_title)

        detail_splitter = QSplitter(Qt.Orientation.Horizontal)
        detail_layout.addWidget(detail_splitter, 1)

        left_detail_panel = self._build_upper_left_detail_panel()
        right_detail_panel = self._build_upper_right_detail_panel()
        detail_splitter.addWidget(left_detail_panel)
        detail_splitter.addWidget(right_detail_panel)
        detail_splitter.setStretchFactor(0, 7)
        detail_splitter.setStretchFactor(1, 3)
        right_splitter.addWidget(detail_panel)

        tabs_panel = QWidget()
        tabs_layout = QVBoxLayout(tabs_panel)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(0)
        self.contact_tabs = QTabWidget()
        self.contact_tabs.addTab(self._build_tab_placeholder("Relacion de cursos asociados al contacto."), "Cursos")
        self.contact_tabs.addTab(self._build_tab_placeholder("Otros datos asociados al contacto."), "Otros")
        tabs_layout.addWidget(self.contact_tabs)
        right_splitter.addWidget(tabs_panel)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 9)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        splitter.handle(1).setEnabled(False)

    def _build_tab_placeholder(self, text: str) -> QWidget:
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setWordWrap(True)
        panel_layout.addWidget(label, 1)
        return panel

    def _build_upper_left_detail_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(2, 2, 12, 2)
        layout.setSpacing(8)

        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        nombre_col = QVBoxLayout()
        nombre_col.setSpacing(5)
        nombre_col.addWidget(QLabel("Nombre"))
        self.detail_nombre = QLineEdit()
        nombre_col.addWidget(self.detail_nombre)
        name_row.addLayout(nombre_col, 1)

        apellidos_col = QVBoxLayout()
        apellidos_col.setSpacing(5)
        apellidos_col.addWidget(QLabel("Apellidos"))
        self.detail_apellidos = QLineEdit()
        apellidos_col.addWidget(self.detail_apellidos)
        name_row.addLayout(apellidos_col, 2)
        layout.addLayout(name_row)

        nif_col = QVBoxLayout()
        nif_col.setSpacing(5)
        nif_col.addWidget(QLabel("NIF"))
        self.detail_nif = QLineEdit()
        nif_col.addWidget(self.detail_nif)
        layout.addLayout(nif_col)

        company_col = QVBoxLayout()
        company_col.setSpacing(5)
        company_col.addWidget(QLabel("Empresa"))
        self.detail_empresa_nombre = QComboBox()
        self.detail_empresa_nombre.setEditable(False)
        company_col.addWidget(self.detail_empresa_nombre)
        layout.addLayout(company_col)

        self.detail_nombre.textEdited.connect(self._schedule_autosave)
        self.detail_apellidos.textEdited.connect(self._schedule_autosave)
        self.detail_nif.textEdited.connect(self._schedule_autosave)
        self.detail_empresa_nombre.currentIndexChanged.connect(self._schedule_autosave)
        return panel

    def _build_upper_right_detail_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 2, 2, 2)
        layout.setSpacing(8)

        info_box = QFrame()
        info_box.setObjectName("card")
        info_box.setFrameShape(QFrame.Shape.Box)
        info_layout = QVBoxLayout(info_box)
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_layout.setSpacing(5)
        info_layout.addWidget(QLabel("Notas"))
        info_layout.addWidget(QLabel("Los campos internos de IDs no se muestran en esta vista."))
        layout.addWidget(info_box)
        layout.addStretch(1)
        return panel

    def _load_companies(self) -> None:
        lookup = self.service.company_lookup()
        self.company_id_to_name = lookup.id_to_name
        self.company_name_to_id = lookup.name_to_id

        current = self.detail_empresa_nombre.currentText() if hasattr(self, "detail_empresa_nombre") else ""
        if hasattr(self, "detail_empresa_nombre"):
            self.detail_empresa_nombre.blockSignals(True)
            self.detail_empresa_nombre.clear()
            for name in sorted(self.company_name_to_id.keys()):
                if name != name.lower():
                    self.detail_empresa_nombre.addItem(name)
            if current:
                idx = self.detail_empresa_nombre.findText(current)
                if idx >= 0:
                    self.detail_empresa_nombre.setCurrentIndex(idx)
            self.detail_empresa_nombre.blockSignals(False)

    def _resolve_cliente_id(self, empresa_nombre: str) -> str:
        text = (empresa_nombre or "").strip()
        if not text:
            return ""
        return self.company_name_to_id.get(text, self.company_name_to_id.get(text.lower(), ""))

    def _list(self, term: str) -> list:
        return self.service.list(term, self.company_id_to_name)

    def _create(self, payload: dict) -> None:
        self.service.create(payload)

    def _ensure_cliente_for_import(self, cliente_id: str) -> str:
        return self.service.ensure_cliente_for_import(cliente_id)

    def _update(self, contacto_id: str, payload: dict) -> None:
        self.service.update(contacto_id, payload)

    def _delete(self, contacto_id: str) -> bool:
        return self.service.delete(contacto_id)

    def _import(self, file_path: str) -> tuple[int, list[str]]:
        return self.service.import_file(Path(file_path))
        schema = [
            {"name": "contacto_id", "label": "Contacto_ID"},
            {"name": "nombre", "label": "Contacto_Nombre"},
            {"name": "apellidos", "label": "Contacto_Apellidos"},
            {"name": "cargo", "label": "Contacto_Cargo"},
            {"name": "nif", "label": "Contacto_NIF"},
            {"name": "telefono", "label": "Contacto_Telefono"},
            {"name": "email", "label": "Contacto_Email"},
            {"name": "cliente_id", "label": "Cliente_ID"},
        ]
        aliases = {
            "contacto_id": ["contacto_uuid"],
            "nombre": ["nombre", "contacto_nombre"],
            "apellidos": ["apellidos", "contacto_apellidos"],
            "cargo": ["cargo", "puesto"],
            "nif": ["dni", "documento"],
            "telefono": ["telefono", "movil", "celular"],
            "email": ["correo", "mail", "e_mail"],
            "cliente_id": ["empresa_id", "empresa_uuid", "cliente_uuid", "cliente_id"],
        }

        def create_payload_from_import(payload: dict) -> None:
            cliente_id = self._ensure_cliente_for_import(payload.get("cliente_id", ""))
            data = {
                "nombre": (payload.get("nombre") or "").strip(),
                "apellidos": (payload.get("apellidos") or "").strip(),
                "cargo": (payload.get("cargo") or "").strip(),
                "nif": (payload.get("nif") or "").strip(),
                "telefono": (payload.get("telefono") or "").strip(),
                "email": (payload.get("email") or "").strip(),
                "cliente_id": cliente_id,
            }
            contacto_id = (payload.get("contacto_id") or "").strip()
            if contacto_id:
                data["contacto_id"] = contacto_id
            self._create(data)

        return self.import_service.import_with_schema(
            file_path=Path(file_path),
            schema=schema,
            create_fn=create_payload_from_import,
            required_fields=["contacto_id", "nombre", "cliente_id"],
            aliases=aliases,
        )

    def reload(self) -> None:
        self._load_companies()
        term = self.search_input.text().strip()
        self.rows = self._list(term)
        self._render_table()
        self._show_selected_details()

    def _render_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for row_idx, item in enumerate(self.rows):
            full_name = f"{(item.nombre or '').strip()} {(item.apellidos or '').strip()}".strip()
            company_name = self.company_id_to_name.get(item.cliente_id, "")
            name_item = QTableWidgetItem(full_name)
            company_item = QTableWidgetItem(company_name)
            name_item.setData(Qt.ItemDataRole.UserRole, getattr(item, "contacto_id", None))
            self.table.setItem(row_idx, 0, name_item)
            self.table.setItem(row_idx, 1, company_item)
        self.table.setSortingEnabled(True)
        has_rows = len(self.rows) > 0
        self.table.setVisible(has_rows)
        self.empty_state_label.setVisible(not has_rows)

    def _selected_row(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        id_item = self.table.item(row_index, 0)
        if id_item is None:
            return None
        contacto_id = id_item.data(Qt.ItemDataRole.UserRole)
        if not contacto_id:
            return None
        for row in self.rows:
            if getattr(row, "contacto_id", None) == contacto_id:
                return row
        return None

    def _show_selected_details(self) -> None:
        row = self._selected_row()
        self._is_loading_details = True
        if not row:
            self.detail_nombre.clear()
            self.detail_apellidos.clear()
            self.detail_nif.clear()
            self.detail_empresa_nombre.setCurrentIndex(-1)
            self._is_loading_details = False
            return

        self.detail_nombre.setText(str(row.nombre or ""))
        self.detail_apellidos.setText(str(row.apellidos or ""))
        self.detail_nif.setText(str(getattr(row, "nif", "") or ""))
        company_name = self.company_id_to_name.get(row.cliente_id, "")
        idx = self.detail_empresa_nombre.findText(company_name)
        self.detail_empresa_nombre.setCurrentIndex(idx if idx >= 0 else -1)
        self._is_loading_details = False

    def _schedule_autosave(self, *_args) -> None:
        if self._is_loading_details or not self._selected_row():
            return
        self._autosave_timer.start(350)

    def _schedule_reload(self) -> None:
        self._search_timer.start(250)

    def _autosave_selected_contact(self) -> None:
        row = self._selected_row()
        if not row:
            return

        cliente_id = self._resolve_cliente_id(self.detail_empresa_nombre.currentText())
        if not cliente_id:
            return

        payload = {
            "nombre": self.detail_nombre.text(),
            "apellidos": self.detail_apellidos.text(),
            "nif": self.detail_nif.text(),
            "cliente_id": cliente_id,
        }
        try:
            self._update(row.contacto_id, payload)
        except Exception as exc:
            QMessageBox.warning(self, "Guardado automatico", f"No se pudo guardar el cambio: {exc}")
            return

        row.nombre = payload["nombre"]
        row.apellidos = payload["apellidos"]
        row.nif = payload["nif"]
        row.cliente_id = payload["cliente_id"]

        selected = self.table.selectionModel().selectedRows()
        if selected:
            row_idx = selected[0].row()
            full_name = f"{(row.nombre or '').strip()} {(row.apellidos or '').strip()}".strip()
            company_name = self.company_id_to_name.get(row.cliente_id, "")
            name_cell = self.table.item(row_idx, 0)
            company_cell = self.table.item(row_idx, 1)
            if name_cell is not None:
                name_cell.setText(full_name)
            if company_cell is not None:
                company_cell.setText(company_name)

    def _select_row_by_id(self, contacto_id: str) -> None:
        for row in range(self.table.rowCount()):
            cell = self.table.item(row, 0)
            if cell and cell.data(Qt.ItemDataRole.UserRole) == contacto_id:
                self.table.selectRow(row)
                break

    def _new_entity(self) -> None:
        schema = [
            {"name": "nombre", "label": "Nombre"},
            {"name": "apellidos", "label": "Apellidos"},
            {"name": "nif", "label": "NIF"},
            {"name": "empresa_nombre_comercial", "label": "Empresa_Nombre_Comercial"},
        ]
        dialog = EntityDialog("Nuevo: Contactos", schema, parent=self)
        if dialog.exec():
            payload = dialog.get_payload()
            cliente_id = self._resolve_cliente_id(payload.get("empresa_nombre_comercial", ""))
            if not payload.get("nombre"):
                QMessageBox.warning(self, "Atencion", "Nombre es obligatorio.")
                return
            if not cliente_id:
                QMessageBox.warning(self, "Atencion", "Empresa no encontrada por nombre comercial.")
                return
            self._create(
                {
                    "nombre": (payload.get("nombre") or "").strip(),
                    "apellidos": (payload.get("apellidos") or "").strip(),
                    "nif": (payload.get("nif") or "").strip(),
                    "cliente_id": cliente_id,
                }
            )
            self.reload()

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un contacto.")
            return
        schema = [
            {"name": "nombre", "label": "Nombre"},
            {"name": "apellidos", "label": "Apellidos"},
            {"name": "nif", "label": "NIF"},
            {"name": "empresa_nombre_comercial", "label": "Empresa_Nombre_Comercial"},
        ]
        initial = {
            "nombre": row.nombre,
            "apellidos": row.apellidos,
            "nif": row.nif,
            "empresa_nombre_comercial": self.company_id_to_name.get(row.cliente_id, ""),
        }
        dialog = EntityDialog("Editar: Contactos", schema, initial=initial, parent=self)
        if dialog.exec():
            payload = dialog.get_payload()
            cliente_id = self._resolve_cliente_id(payload.get("empresa_nombre_comercial", ""))
            if not payload.get("nombre"):
                QMessageBox.warning(self, "Atencion", "Nombre es obligatorio.")
                return
            if not cliente_id:
                QMessageBox.warning(self, "Atencion", "Empresa no encontrada por nombre comercial.")
                return
            self._update(
                row.contacto_id,
                {
                    "nombre": (payload.get("nombre") or "").strip(),
                    "apellidos": (payload.get("apellidos") or "").strip(),
                    "nif": (payload.get("nif") or "").strip(),
                    "cliente_id": cliente_id,
                },
            )
            self.reload()

    def _delete_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un contacto.")
            return
        full_name = f"{(row.nombre or '').strip()} {(row.apellidos or '').strip()}".strip()
        answer = QMessageBox.question(self, "Confirmar", f"Eliminar contacto {full_name}?")
        if answer == QMessageBox.StandardButton.Yes:
            self._delete(row.contacto_id)
            self.reload()

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

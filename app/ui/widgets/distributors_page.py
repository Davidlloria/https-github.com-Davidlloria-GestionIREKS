from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from app.models import Distribuidor
from app.services.distributor_service import DistributorService
from app.ui.widgets.entity_dialog import EntityDialog


class DistributorsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.service = DistributorService()
        self.rows: list[Distribuidor] = []
        self._is_loading_details = False
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.reload)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_selected_distributor)
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel("Distribuidores")
        header.setProperty("role", "pageTitle")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_panel.setObjectName("sidePanel")
        left_layout = QVBoxLayout(left_panel)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por codigo, nombre, razon social o CIF...")
        self.search_input.textChanged.connect(self._schedule_reload)
        left_layout.addWidget(self.search_input)

        self.table = QTableWidget(0, 2)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        table_header = self.table.horizontalHeader()
        table_header.setSectionsClickable(True)
        table_header.setMinimumSectionSize(90)
        self.table.setHorizontalHeaderLabels(["Codigo", "Nombre"])
        table_header.setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setStyleSheet(
            """
            QTableWidget::item:focus { border: none; outline: 0; }
            QTableWidget::item:selected { color: #0F172A; }
            """
        )
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
        self.id_btn.clicked.connect(self._show_distributor_id_dialog)
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

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(right_splitter, 1)

        detail_panel = QWidget()
        detail_panel.setObjectName("detailPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(8)
        detail_title = QLabel("Detalle del distribuidor")
        detail_title.setProperty("role", "sectionTitle")
        detail_layout.addWidget(detail_title)

        self.detail_codigo = QLineEdit()
        self.detail_codigo.setReadOnly(True)
        self.detail_razon_social = QLineEdit()
        self.detail_nombre_comercial = QLineEdit()
        self.detail_cif = QLineEdit()
        self.detail_telefono = QLineEdit()
        self.detail_contacto = QLineEdit()

        for label, field in [
            ("Codigo", self.detail_codigo),
            ("Razon social", self.detail_razon_social),
            ("Nombre comercial", self.detail_nombre_comercial),
            ("CIF", self.detail_cif),
            ("Telefono", self.detail_telefono),
            ("Contacto", self.detail_contacto),
        ]:
            row = QVBoxLayout()
            row.setSpacing(5)
            row.addWidget(QLabel(label))
            row.addWidget(field)
            detail_layout.addLayout(row)

        self.detail_razon_social.textEdited.connect(self._schedule_autosave)
        self.detail_nombre_comercial.textEdited.connect(self._schedule_autosave)
        self.detail_cif.textEdited.connect(self._schedule_autosave)
        self.detail_telefono.textEdited.connect(self._schedule_autosave)
        self.detail_contacto.textEdited.connect(self._schedule_autosave)
        right_splitter.addWidget(detail_panel)

        tabs_panel = QWidget()
        tabs_layout = QVBoxLayout(tabs_panel)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(0)
        tabs = QTabWidget()
        for name in ["Articulos", "Acuerdos", "Notas"]:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            info = QLabel(f"Pestaña {name} pendiente de implementar.")
            info.setWordWrap(True)
            tab_layout.addWidget(info, 1)
            tabs.addTab(tab, name)
        tabs_layout.addWidget(tabs)
        right_splitter.addWidget(tabs_panel)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 9)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        splitter.handle(1).setEnabled(False)

    def _schedule_reload(self) -> None:
        self._search_timer.start(180)

    def _schedule_autosave(self) -> None:
        if self._is_loading_details:
            return
        self._autosave_timer.start(350)

    def reload(self) -> None:
        selected_id = self._selected_id()
        self.rows = self.service.list(self.search_input.text().strip())
        header = self.table.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for row_idx, row in enumerate(self.rows):
            codigo = str(row.distribuidor_codigo or "")
            nombre = str(row.distribuidor_nombre_comercial or "").strip() or str(row.distribuidor_razon_social or "")
            item_code = QTableWidgetItem(codigo)
            item_code.setData(Qt.ItemDataRole.UserRole, row.distribuidor_id)
            self.table.setItem(row_idx, 0, item_code)
            self.table.setItem(row_idx, 1, QTableWidgetItem(nombre))
        self.table.setSortingEnabled(True)
        self.table.sortItems(sort_col if sort_col >= 0 else 0, sort_order)
        self._select_by_id(selected_id)
        if self.table.rowCount() > 0 and not self.table.selectionModel().selectedRows():
            self.table.selectRow(0)
        if self.table.rowCount() > 0:
            self._show_selected_details()
        else:
            self._clear_details()

    def _selected_row(self) -> Distribuidor | None:
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return None
        row_idx = selected[0].row()
        code_item = self.table.item(row_idx, 0)
        distribuidor_id = str(code_item.data(Qt.ItemDataRole.UserRole) or "") if code_item else ""
        if not distribuidor_id:
            return None
        return next((row for row in self.rows if str(row.distribuidor_id or "") == distribuidor_id), None)

    def _selected_id(self) -> str | None:
        row = self._selected_row()
        return None if row is None else str(row.distribuidor_id or "")

    def _select_by_id(self, distribuidor_id: str | None) -> None:
        if not distribuidor_id:
            return
        for i, row in enumerate(self.rows):
            if str(row.distribuidor_id or "") == distribuidor_id:
                self.table.selectRow(i)
                return

    def _show_selected_details(self) -> None:
        row = self._selected_row()
        self._is_loading_details = True
        if row is None:
            self._clear_details()
            self._is_loading_details = False
            return
        self.detail_codigo.setText(str(row.distribuidor_codigo or ""))
        self.detail_razon_social.setText(str(row.distribuidor_razon_social or ""))
        self.detail_nombre_comercial.setText(str(row.distribuidor_nombre_comercial or ""))
        self.detail_cif.setText(str(row.distribuidor_cif or ""))
        self.detail_telefono.setText(str(row.distribuidor_telefono or ""))
        self.detail_contacto.setText(str(row.distribuidor_contacto or ""))
        self._is_loading_details = False

    def _clear_details(self) -> None:
        for field in (
            self.detail_codigo,
            self.detail_razon_social,
            self.detail_nombre_comercial,
            self.detail_cif,
            self.detail_telefono,
            self.detail_contacto,
        ):
            field.clear()

    def _autosave_selected_distributor(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        payload = {
            "distribuidor_razon_social": self.detail_razon_social.text().strip(),
            "distribuidor_nombre_comercial": self.detail_nombre_comercial.text().strip(),
            "distribuidor_cif": self.detail_cif.text().strip(),
            "distribuidor_telefono": self.detail_telefono.text().strip(),
            "distribuidor_contacto": self.detail_contacto.text().strip(),
        }
        try:
            self.service.update(str(row.distribuidor_id or ""), payload)
            row.distribuidor_razon_social = payload["distribuidor_razon_social"]
            row.distribuidor_nombre_comercial = payload["distribuidor_nombre_comercial"]
            row.distribuidor_cif = payload["distribuidor_cif"]
            row.distribuidor_telefono = payload["distribuidor_telefono"]
            row.distribuidor_contacto = payload["distribuidor_contacto"]
            selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
            if selected:
                i = selected[0].row()
                item_name = self.table.item(i, 1)
                if item_name:
                    label = payload["distribuidor_nombre_comercial"] or payload["distribuidor_razon_social"]
                    item_name.setText(label)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Distribuidores", f"No se pudo guardar.\n{exc}")

    def _dialog_schema(self, include_id: bool) -> list[dict]:
        fields = [
            {"name": "distribuidor_codigo", "label": "Codigo"},
            {"name": "distribuidor_razon_social", "label": "Razon social"},
            {"name": "distribuidor_nombre_comercial", "label": "Nombre comercial"},
            {"name": "distribuidor_cif", "label": "CIF"},
            {"name": "distribuidor_telefono", "label": "Telefono"},
            {"name": "distribuidor_contacto", "label": "Contacto"},
        ]
        if include_id:
            return [{"name": "distribuidor_id", "label": "Distribuidor_ID"}, *fields]
        return fields

    def _new_entity(self) -> None:
        dialog = EntityDialog("Nuevo: Distribuidores", self._dialog_schema(include_id=True), parent=self)
        if dialog.exec():
            payload = dialog.get_payload()
            try:
                self.service.create(payload)
                self.reload()
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Distribuidores", f"No se pudo crear.\n{exc}")

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.warning(self, "Distribuidores", "Selecciona un distribuidor.")
            return
        initial = {
            "distribuidor_codigo": row.distribuidor_codigo,
            "distribuidor_razon_social": row.distribuidor_razon_social,
            "distribuidor_nombre_comercial": row.distribuidor_nombre_comercial,
            "distribuidor_cif": row.distribuidor_cif,
            "distribuidor_telefono": row.distribuidor_telefono,
            "distribuidor_contacto": row.distribuidor_contacto,
        }
        dialog = EntityDialog("Editar: Distribuidores", self._dialog_schema(include_id=False), initial=initial, parent=self)
        if dialog.exec():
            payload = dialog.get_payload()
            try:
                self.service.update(str(row.distribuidor_id or ""), payload)
                self.reload()
                self._select_by_id(str(row.distribuidor_id or ""))
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Distribuidores", f"No se pudo editar.\n{exc}")

    def _delete_entity(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.warning(self, "Distribuidores", "Selecciona un distribuidor.")
            return
        answer = QMessageBox.question(
            self,
            "Confirmar",
            f"Eliminar distribuidor {str(row.distribuidor_nombre_comercial or row.distribuidor_razon_social or '').strip()}?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(str(row.distribuidor_id or ""))
            self.reload()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Distribuidores", f"No se pudo eliminar.\n{exc}")

    def _import_entities(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo",
            "",
            "Archivos de datos (*.xlsx *.xlsm *.csv)",
        )
        if not file_path:
            return
        imported, errors = self.service.import_file(Path(file_path))
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

    def _show_distributor_id_dialog(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.warning(self, "Distribuidores", "Selecciona un distribuidor.")
            return
        distribuidor_id = str(row.distribuidor_id or "").strip()
        if not distribuidor_id:
            QMessageBox.warning(self, "Distribuidores", "El distribuidor no tiene ID.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("ID del distribuidor")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)

        label = QLabel("ID del distribuidor")
        id_field = QLineEdit(distribuidor_id)
        id_field.setReadOnly(True)
        id_field.setCursorPosition(0)
        id_field.setSelection(0, 0)

        buttons = QHBoxLayout()
        copy_btn = QPushButton("Copiar")
        close_btn = QPushButton("Cerrar")
        copy_btn.setProperty("btnRole", "secondary")
        close_btn.setProperty("btnRole", "secondary")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(distribuidor_id))
        close_btn.clicked.connect(dialog.accept)
        buttons.addWidget(copy_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)

        layout.addWidget(label)
        layout.addWidget(id_field)
        layout.addLayout(buttons)
        dialog.resize(460, 130)
        dialog.exec()

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.config import DATA_DIR
from app.models import CodigoPostal, Isla, Localidad, Municipio, Provincia
from app.services.address_catalog_service import AddressCatalogService
from app.services.settings_orders_import_service import SettingsOrdersImportService
from app.services.settings_import_service import SettingsImportService
from app.services.settings_maintenance_ui_service import SettingsMaintenanceUiService
from app.services.settings_provider_service import SettingsProviderService
from app.services.settings_sales_import_service import SettingsSalesImportService
from app.services.settings_sales_preview_service import SettingsSalesPreviewService
from app.ui.widgets.db_export_console_tab import DbExportConsoleTab
from app.ui.widgets.db_import_console_tab import DbImportConsoleTab
from app.ui.widgets.entity_dialog import EntityDialog


class LocalidadCreateDialog(QDialog):
    def __init__(self, municipios: list[tuple[str, str]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nueva: Localidad")
        self.setMinimumWidth(640)
        self.municipios = municipios
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.localidad_input = QLineEdit()
        self.cp_input = QLineEdit()
        self.municipio_combo = QComboBox()
        self.municipio_combo.addItem("", "")
        for name, municipio_id in self.municipios:
            self.municipio_combo.addItem(name, municipio_id)

        # Requested order: Localidad, Codigo postal, Municipio.
        form.addRow("Localidad", self.localidad_input)
        form.addRow("Codigo postal", self.cp_input)
        form.addRow("Municipio", self.municipio_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_payload(self) -> dict[str, str | None]:
        cp = self.cp_input.text().strip()
        return {
            "localidad_nombre": self.localidad_input.text().strip(),
            "codigo_postal": cp or None,
            "municipio_id": str(self.municipio_combo.currentData() or "").strip(),
        }


class ProvinciasTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.catalog_service = AddressCatalogService()
        self.rows: list[Provincia] = []
        self._loading_table = False
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por codigo, nombre o ID...")
        self.search_input.textChanged.connect(self.reload)
        toolbar.addWidget(self.search_input, 1)

        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setProperty("btnRole", "success")
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setProperty("btnRole", "warning")
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.setProperty("btnRole", "danger")
        self.import_btn = QPushButton("Importar Excel/CSV")
        self.import_btn.setProperty("btnRole", "secondary")
        self.refresh_btn = QPushButton("Refrescar")
        self.refresh_btn.setProperty("btnRole", "secondary")

        self.new_btn.clicked.connect(self._new_entity)
        self.edit_btn.clicked.connect(self._edit_entity)
        self.delete_btn.clicked.connect(self._delete_entity)
        self.import_btn.clicked.connect(self._import_entities)
        self.refresh_btn.clicked.connect(self.reload)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 2)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setHorizontalHeaderLabels(["Codigo", "Nombre"])
        self.table.setSortingEnabled(True)
        self.table.setColumnWidth(0, 140)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

    def reload(self) -> None:
        term = self.search_input.text().strip()
        self.rows = self.catalog_service.list_provincias(term)
        self._render_table()

    def _render_table(self) -> None:
        self._loading_table = True
        self.table.blockSignals(True)
        sorting_was_enabled = self.table.isSortingEnabled()
        sort_col = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(self.rows))
            for row_idx, item in enumerate(self.rows):
                code_item = QTableWidgetItem(str(item.provincia_codigo or ""))
                name_item = QTableWidgetItem(str(item.provincia_nombre or ""))
                code_item.setData(Qt.ItemDataRole.UserRole, str(item.provincia_id or ""))
                name_item.setData(Qt.ItemDataRole.UserRole, str(item.provincia_id or ""))
                self.table.setItem(row_idx, 0, code_item)
                self.table.setItem(row_idx, 1, name_item)
        finally:
            self.table.blockSignals(False)
            self.table.setSortingEnabled(sorting_was_enabled)
            if sorting_was_enabled and sort_col >= 0:
                self.table.sortByColumn(sort_col, sort_order)
            self._loading_table = False

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_table:
            return
        provincia_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not provincia_id:
            return
        row_idx = item.row()
        code_cell = self.table.item(row_idx, 0)
        name_cell = self.table.item(row_idx, 1)
        codigo = str(code_cell.text() if code_cell else "").strip()
        nombre = str(name_cell.text() if name_cell else "").strip()
        if not codigo or not nombre:
            self.reload()
            return
        try:
            if not self.catalog_service.update_provincia_cells(provincia_id, codigo, nombre):
                self.reload()
        except Exception as exc:
            QMessageBox.warning(self, "Provincias", f"No se pudo guardar: {exc}")
            self.reload()

    def _selected_row(self) -> Provincia | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_idx = selected[0].row()
        id_item = self.table.item(row_idx, 0)
        if id_item is None:
            return None
        provincia_id = str(id_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not provincia_id:
            return None
        for row in self.rows:
            if str(getattr(row, "provincia_id", "") or "") == provincia_id:
                return row
        return None

    def _new_entity(self) -> None:
        schema = [
            {"name": "provincia_id", "label": "Provincia_ID"},
            {"name": "provincia_nombre", "label": "Provincia_Nombre"},
            {"name": "provincia_codigo", "label": "Provincia_Codigo"},
        ]
        dialog = EntityDialog("Nueva: Provincia", schema, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        try:
            self._validate_required(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Atencion", str(exc))
            return
        self.catalog_service.create_provincia(payload)
        self.reload()

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona una provincia.")
            return
        schema = [
            {"name": "provincia_id", "label": "Provincia_ID"},
            {"name": "provincia_nombre", "label": "Provincia_Nombre"},
            {"name": "provincia_codigo", "label": "Provincia_Codigo"},
        ]
        initial = {
            "provincia_id": row.provincia_id,
            "provincia_nombre": row.provincia_nombre,
            "provincia_codigo": row.provincia_codigo,
        }
        dialog = EntityDialog("Editar: Provincia", schema, initial=initial, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        try:
            self._validate_required(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Atencion", str(exc))
            return
        if not self.catalog_service.replace_provincia(row.provincia_id, payload):
            QMessageBox.warning(self, "Atencion", "Provincia no encontrada.")
            return
        self.reload()

    def _delete_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona una provincia.")
            return
        answer = QMessageBox.question(self, "Confirmar", f"Eliminar provincia {row.provincia_nombre}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.catalog_service.delete_provincia(row.provincia_id)
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

        schema = [
            {"name": "provincia_id", "label": "Provincia_ID"},
            {"name": "provincia_nombre", "label": "Provincia_Nombre"},
            {"name": "provincia_codigo", "label": "Provincia_Codigo"},
        ]
        aliases = {
            "provincia_id": ["id", "uuid", "provincia_uuid"],
            "provincia_nombre": ["nombre", "provincia"],
            "provincia_codigo": ["codigo", "cod_provincia"],
        }

        imported, errors = self.catalog_service.import_provincias(Path(file_path), schema, aliases)

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

    def _validate_required(self, payload: dict) -> None:
        self.catalog_service.validate_provincia(payload)


class AddressPlaceholderTab(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setProperty("btnRole", "success")
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setProperty("btnRole", "warning")
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.setProperty("btnRole", "danger")
        self.import_btn = QPushButton("Importar Excel/CSV")
        self.import_btn.setProperty("btnRole", "secondary")
        self.refresh_btn = QPushButton("Refrescar")
        self.refresh_btn.setProperty("btnRole", "secondary")

        for btn in (self.new_btn, self.edit_btn, self.delete_btn, self.import_btn, self.refresh_btn):
            btn.clicked.connect(self._not_implemented)
            toolbar.addWidget(btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        info = QLabel(f"{self.title}: estructura creada. Pendiente de implementar la logica de datos.")
        info.setWordWrap(True)
        layout.addWidget(info)

    def _not_implemented(self) -> None:
        QMessageBox.information(self, self.title, "Modulo preparado. Implementacion de datos pendiente.")


class IslasTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.catalog_service = AddressCatalogService()
        self.rows: list[Isla] = []
        self.provincia_name_by_id: dict[str, str] = {}
        self.provincia_id_by_name: dict[str, str] = {}
        self._loading_table = False
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por codigo, nombre, iniciales o IDs...")
        self.search_input.textChanged.connect(self.reload)
        toolbar.addWidget(self.search_input, 1)

        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setProperty("btnRole", "success")
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setProperty("btnRole", "warning")
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.setProperty("btnRole", "danger")
        self.import_btn = QPushButton("Importar Excel/CSV")
        self.import_btn.setProperty("btnRole", "secondary")
        self.refresh_btn = QPushButton("Refrescar")
        self.refresh_btn.setProperty("btnRole", "secondary")

        self.new_btn.clicked.connect(self._new_entity)
        self.edit_btn.clicked.connect(self._edit_entity)
        self.delete_btn.clicked.connect(self._delete_entity)
        self.import_btn.clicked.connect(self._import_entities)
        self.refresh_btn.clicked.connect(self.reload)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 4)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setHorizontalHeaderLabels(["Codigo", "Nombre", "Iniciales", "Provincia"])
        self.table.setSortingEnabled(True)
        self.table.setColumnWidth(0, 140)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

    def reload(self) -> None:
        term = self.search_input.text().strip()
        self.rows, provincias = self.catalog_service.list_islas(term)
        self.provincia_name_by_id = {str(p.provincia_id): str(p.provincia_nombre or "") for p in provincias}
        self.provincia_id_by_name = {}
        for p in provincias:
            name = str(p.provincia_nombre or "").strip()
            pid = str(p.provincia_id or "").strip()
            if name and pid:
                self.provincia_id_by_name[name] = pid
                self.provincia_id_by_name[name.lower()] = pid
        self._render_table()

    def _render_table(self) -> None:
        self._loading_table = True
        self.table.blockSignals(True)
        sorting_was_enabled = self.table.isSortingEnabled()
        sort_col = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(self.rows))
            for row_idx, item in enumerate(self.rows):
                isla_id = str(item.isla_id or "")
                code_item = QTableWidgetItem(str(item.isla_codigo or ""))
                name_item = QTableWidgetItem(str(item.isla_nombre or ""))
                ini_item = QTableWidgetItem(str(item.isla_iniciales or ""))
                prov_item = QTableWidgetItem(self.provincia_name_by_id.get(str(item.provincia_id or ""), ""))
                for table_item in (code_item, name_item, ini_item, prov_item):
                    table_item.setData(Qt.ItemDataRole.UserRole, isla_id)
                self.table.setItem(row_idx, 0, code_item)
                self.table.setItem(row_idx, 1, name_item)
                self.table.setItem(row_idx, 2, ini_item)
                self.table.setItem(row_idx, 3, prov_item)
        finally:
            self.table.blockSignals(False)
            self.table.setSortingEnabled(sorting_was_enabled)
            if sorting_was_enabled and sort_col >= 0:
                self.table.sortByColumn(sort_col, sort_order)
            self._loading_table = False

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_table:
            return
        isla_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not isla_id:
            return
        row_idx = item.row()
        code_cell = self.table.item(row_idx, 0)
        name_cell = self.table.item(row_idx, 1)
        ini_cell = self.table.item(row_idx, 2)
        prov_cell = self.table.item(row_idx, 3)
        codigo = str(code_cell.text() if code_cell else "").strip()
        nombre = str(name_cell.text() if name_cell else "").strip()
        iniciales = str(ini_cell.text() if ini_cell else "").strip()
        provincia_name = str(prov_cell.text() if prov_cell else "").strip()
        provincia_id = self.provincia_id_by_name.get(provincia_name, self.provincia_id_by_name.get(provincia_name.lower(), ""))
        if not codigo or not nombre or not iniciales or not provincia_id:
            self.reload()
            return
        try:
            ok = self.catalog_service.update_isla_cells(
                isla_id,
                codigo=codigo,
                nombre=nombre,
                iniciales=iniciales,
                provincia_id=provincia_id,
            )
            if not ok:
                self.reload()
        except Exception as exc:
            QMessageBox.warning(self, "Islas", f"No se pudo guardar: {exc}")
            self.reload()

    def _selected_row(self) -> Isla | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_idx = selected[0].row()
        id_item = self.table.item(row_idx, 0)
        if id_item is None:
            return None
        isla_id = str(id_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not isla_id:
            return None
        for row in self.rows:
            if str(getattr(row, "isla_id", "") or "") == isla_id:
                return row
        return None

    def _new_entity(self) -> None:
        schema = [
            {"name": "isla_id", "label": "Isla_ID"},
            {"name": "provincia_id", "label": "Provincia_ID"},
            {"name": "isla_nombre", "label": "Isla_Nombre"},
            {"name": "isla_codigo", "label": "Isla_Codigo"},
            {"name": "isla_iniciales", "label": "Isla_Iniciales"},
        ]
        dialog = EntityDialog("Nueva: Isla", schema, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        try:
            self._validate_required(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Atencion", str(exc))
            return
        self.catalog_service.create_isla(payload)
        self.reload()

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona una isla.")
            return
        schema = [
            {"name": "isla_id", "label": "Isla_ID"},
            {"name": "provincia_id", "label": "Provincia_ID"},
            {"name": "isla_nombre", "label": "Isla_Nombre"},
            {"name": "isla_codigo", "label": "Isla_Codigo"},
            {"name": "isla_iniciales", "label": "Isla_Iniciales"},
        ]
        initial = {
            "isla_id": row.isla_id,
            "provincia_id": row.provincia_id,
            "isla_nombre": row.isla_nombre,
            "isla_codigo": row.isla_codigo,
            "isla_iniciales": row.isla_iniciales,
        }
        dialog = EntityDialog("Editar: Isla", schema, initial=initial, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        try:
            self._validate_required(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Atencion", str(exc))
            return
        if not self.catalog_service.replace_isla(row.isla_id, payload):
            QMessageBox.warning(self, "Atencion", "Isla no encontrada.")
            return
        self.reload()

    def _delete_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona una isla.")
            return
        answer = QMessageBox.question(self, "Confirmar", f"Eliminar isla {row.isla_nombre}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.catalog_service.delete_isla(row.isla_id)
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

        schema = [
            {"name": "isla_id", "label": "Isla_ID"},
            {"name": "provincia_id", "label": "Provincia_ID"},
            {"name": "isla_nombre", "label": "Isla_Nombre"},
            {"name": "isla_codigo", "label": "Isla_Codigo"},
            {"name": "isla_iniciales", "label": "Isla_Iniciales"},
        ]
        aliases = {
            "isla_id": ["id", "uuid", "isla_uuid"],
            "provincia_id": ["provincia_uuid", "provinciaid"],
            "isla_nombre": ["nombre", "isla"],
            "isla_codigo": ["codigo", "cod_isla"],
            "isla_iniciales": ["iniciales", "siglas"],
        }

        imported, errors = self.catalog_service.import_islas(Path(file_path), schema, aliases)

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

    def _validate_required(self, payload: dict) -> None:
        self.catalog_service.validate_isla(payload)


class MunicipiosTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.catalog_service = AddressCatalogService()
        self.rows: list[Municipio] = []
        self.isla_name_by_id: dict[str, str] = {}
        self.provincia_name_by_id: dict[str, str] = {}
        self.isla_id_by_name: dict[str, str] = {}
        self.provincia_id_by_name: dict[str, str] = {}
        self.isla_provincia_by_id: dict[str, str] = {}
        self._loading_table = False
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por codigo, nombre o IDs...")
        self.search_input.textChanged.connect(self.reload)
        toolbar.addWidget(self.search_input, 1)

        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setProperty("btnRole", "success")
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setProperty("btnRole", "warning")
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.setProperty("btnRole", "danger")
        self.import_btn = QPushButton("Importar Excel/CSV")
        self.import_btn.setProperty("btnRole", "secondary")
        self.refresh_btn = QPushButton("Refrescar")
        self.refresh_btn.setProperty("btnRole", "secondary")

        self.new_btn.clicked.connect(self._new_entity)
        self.edit_btn.clicked.connect(self._edit_entity)
        self.delete_btn.clicked.connect(self._delete_entity)
        self.import_btn.clicked.connect(self._import_entities)
        self.refresh_btn.clicked.connect(self.reload)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 4)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setHorizontalHeaderLabels(["Codigo", "Nombre", "Isla", "Provincia"])
        self.table.setSortingEnabled(True)
        self.table.setColumnWidth(0, 140)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

    def reload(self) -> None:
        term = self.search_input.text().strip()
        self.rows, islas, provincias = self.catalog_service.list_municipios(term)
        self.isla_name_by_id = {str(i.isla_id): str(i.isla_nombre or "") for i in islas}
        self.provincia_name_by_id = {str(p.provincia_id): str(p.provincia_nombre or "") for p in provincias}
        self.isla_id_by_name = {}
        self.isla_provincia_by_id = {}
        for i in islas:
            name = str(i.isla_nombre or "").strip()
            iid = str(i.isla_id or "").strip()
            if name and iid:
                self.isla_id_by_name[name] = iid
                self.isla_id_by_name[name.lower()] = iid
                self.isla_provincia_by_id[iid] = str(i.provincia_id or "")
        self.provincia_id_by_name = {}
        for p in provincias:
            name = str(p.provincia_nombre or "").strip()
            pid = str(p.provincia_id or "").strip()
            if name and pid:
                self.provincia_id_by_name[name] = pid
                self.provincia_id_by_name[name.lower()] = pid
        self._render_table()

    def _render_table(self) -> None:
        self._loading_table = True
        self.table.blockSignals(True)
        sorting_was_enabled = self.table.isSortingEnabled()
        sort_col = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(self.rows))
            for row_idx, item in enumerate(self.rows):
                municipio_id = str(item.municipio_id or "")
                code_item = QTableWidgetItem(str(item.municipio_codigo or ""))
                name_item = QTableWidgetItem(str(item.municipio_nombre or ""))
                isla_item = QTableWidgetItem(self.isla_name_by_id.get(str(item.isla_id or ""), ""))
                prov_item = QTableWidgetItem(self.provincia_name_by_id.get(str(item.provincia_id or ""), ""))
                for table_item in (code_item, name_item, isla_item, prov_item):
                    table_item.setData(Qt.ItemDataRole.UserRole, municipio_id)
                self.table.setItem(row_idx, 0, code_item)
                self.table.setItem(row_idx, 1, name_item)
                self.table.setItem(row_idx, 2, isla_item)
                self.table.setItem(row_idx, 3, prov_item)
        finally:
            self.table.blockSignals(False)
            self.table.setSortingEnabled(sorting_was_enabled)
            if sorting_was_enabled and sort_col >= 0:
                self.table.sortByColumn(sort_col, sort_order)
            self._loading_table = False

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_table:
            return
        municipio_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not municipio_id:
            return
        row_idx = item.row()
        code_cell = self.table.item(row_idx, 0)
        name_cell = self.table.item(row_idx, 1)
        isla_cell = self.table.item(row_idx, 2)
        prov_cell = self.table.item(row_idx, 3)
        codigo = str(code_cell.text() if code_cell else "").strip()
        nombre = str(name_cell.text() if name_cell else "").strip()
        isla_name = str(isla_cell.text() if isla_cell else "").strip()
        provincia_name = str(prov_cell.text() if prov_cell else "").strip()
        isla_id = self.isla_id_by_name.get(isla_name, self.isla_id_by_name.get(isla_name.lower(), ""))
        provincia_id = self.provincia_id_by_name.get(
            provincia_name, self.provincia_id_by_name.get(provincia_name.lower(), "")
        )
        if isla_id:
            provincia_id = self.isla_provincia_by_id.get(isla_id, provincia_id)
        if not codigo or not nombre or not isla_id or not provincia_id:
            self.reload()
            return
        try:
            ok = self.catalog_service.update_municipio_cells(
                municipio_id,
                codigo=codigo,
                nombre=nombre,
                isla_id=isla_id,
                provincia_id=provincia_id,
            )
            if not ok:
                self.reload()
        except Exception as exc:
            QMessageBox.warning(self, "Municipios", f"No se pudo guardar: {exc}")
            self.reload()

    def _selected_row(self) -> Municipio | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_idx = selected[0].row()
        id_item = self.table.item(row_idx, 0)
        if id_item is None:
            return None
        municipio_id = str(id_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not municipio_id:
            return None
        for row in self.rows:
            if str(getattr(row, "municipio_id", "") or "") == municipio_id:
                return row
        return None

    def _new_entity(self) -> None:
        schema = [
            {"name": "municipio_id", "label": "Municipio_ID"},
            {"name": "isla_id", "label": "Isla_ID"},
            {"name": "provincia_id", "label": "Provincia_ID"},
            {"name": "municipio_nombre", "label": "Municipio_Nombre"},
            {"name": "municipio_codigo", "label": "Municipio_Codigo"},
        ]
        dialog = EntityDialog("Nuevo: Municipio", schema, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        try:
            self._validate_required(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Atencion", str(exc))
            return
        self.catalog_service.create_municipio(payload)
        self.reload()

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un municipio.")
            return
        schema = [
            {"name": "municipio_id", "label": "Municipio_ID"},
            {"name": "isla_id", "label": "Isla_ID"},
            {"name": "provincia_id", "label": "Provincia_ID"},
            {"name": "municipio_nombre", "label": "Municipio_Nombre"},
            {"name": "municipio_codigo", "label": "Municipio_Codigo"},
        ]
        initial = {
            "municipio_id": row.municipio_id,
            "isla_id": row.isla_id,
            "provincia_id": row.provincia_id,
            "municipio_nombre": row.municipio_nombre,
            "municipio_codigo": row.municipio_codigo,
        }
        dialog = EntityDialog("Editar: Municipio", schema, initial=initial, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        try:
            self._validate_required(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Atencion", str(exc))
            return
        if not self.catalog_service.replace_municipio(row.municipio_id, payload):
            QMessageBox.warning(self, "Atencion", "Municipio no encontrado.")
            return
        self.reload()

    def _delete_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un municipio.")
            return
        answer = QMessageBox.question(self, "Confirmar", f"Eliminar municipio {row.municipio_nombre}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.catalog_service.delete_municipio(row.municipio_id)
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

        schema = [
            {"name": "municipio_id", "label": "Municipio_ID"},
            {"name": "isla_id", "label": "Isla_ID"},
            {"name": "provincia_id", "label": "Provincia_ID"},
            {"name": "municipio_nombre", "label": "Municipio_Nombre"},
            {"name": "municipio_codigo", "label": "Municipio_Codigo"},
        ]
        aliases = {
            "municipio_id": ["id", "uuid", "municipio_uuid"],
            "isla_id": ["isla_uuid", "islaid"],
            "provincia_id": ["provincia_uuid", "provinciaid"],
            "municipio_nombre": ["nombre", "municipio"],
            "municipio_codigo": ["codigo", "cod_municipio"],
        }

        imported, errors = self.catalog_service.import_municipios(Path(file_path), schema, aliases)

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

    def _validate_required(self, payload: dict) -> None:
        self.catalog_service.validate_municipio(payload)


class CodigosPostalesTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.catalog_service = AddressCatalogService()
        self.rows: list[CodigoPostal] = []
        self.municipio_name_by_id: dict[str, str] = {}
        self.municipio_id_by_name: dict[str, str] = {}
        self.isla_name_by_id: dict[str, str] = {}
        self.provincia_name_by_id: dict[str, str] = {}
        self.municipio_isla_by_id: dict[str, str] = {}
        self.municipio_provincia_by_id: dict[str, str] = {}
        self._loading_table = False
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por codigo postal, municipio o ID...")
        self.search_input.textChanged.connect(self.reload)
        toolbar.addWidget(self.search_input, 1)

        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setProperty("btnRole", "success")
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setProperty("btnRole", "warning")
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.setProperty("btnRole", "danger")
        self.import_btn = QPushButton("Importar Excel/CSV")
        self.import_btn.setProperty("btnRole", "secondary")
        self.refresh_btn = QPushButton("Refrescar")
        self.refresh_btn.setProperty("btnRole", "secondary")

        self.new_btn.clicked.connect(self._new_entity)
        self.edit_btn.clicked.connect(self._edit_entity)
        self.delete_btn.clicked.connect(self._delete_entity)
        self.import_btn.clicked.connect(self._import_entities)
        self.refresh_btn.clicked.connect(self.reload)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 4)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setHorizontalHeaderLabels(["Codigo Postal", "Municipio", "Isla", "Provincia"])
        self.table.setSortingEnabled(True)
        self.table.setColumnWidth(0, 140)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

    def reload(self) -> None:
        term = self.search_input.text().strip()
        self.rows, municipios, islas, provincias = self.catalog_service.list_codigos_postales(term)
        self.municipio_name_by_id = {str(m.municipio_id): str(m.municipio_nombre or "") for m in municipios}
        self.municipio_id_by_name = {}
        for m in municipios:
            name = str(m.municipio_nombre or "").strip()
            mid = str(m.municipio_id or "").strip()
            if name and mid:
                self.municipio_id_by_name[name] = mid
                self.municipio_id_by_name[name.lower()] = mid
        self.municipio_isla_by_id = {str(m.municipio_id): str(m.isla_id or "") for m in municipios}
        self.municipio_provincia_by_id = {str(m.municipio_id): str(m.provincia_id or "") for m in municipios}
        self.isla_name_by_id = {str(i.isla_id): str(i.isla_nombre or "") for i in islas}
        self.provincia_name_by_id = {str(p.provincia_id): str(p.provincia_nombre or "") for p in provincias}
        self._render_table()

    def _render_table(self) -> None:
        self._loading_table = True
        self.table.blockSignals(True)
        sorting_was_enabled = self.table.isSortingEnabled()
        sort_col = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(self.rows))
            for row_idx, item in enumerate(self.rows):
                municipio_id = str(item.municipio_id or "")
                codigo_postal = str(item.codigo_postal or "")
                isla_id = self.municipio_isla_by_id.get(municipio_id, "")
                provincia_id = self.municipio_provincia_by_id.get(municipio_id, "")
                cp_item = QTableWidgetItem(codigo_postal)
                mun_item = QTableWidgetItem(self.municipio_name_by_id.get(municipio_id, ""))
                isla_item = QTableWidgetItem(self.isla_name_by_id.get(isla_id, ""))
                prov_item = QTableWidgetItem(self.provincia_name_by_id.get(provincia_id, ""))
                cp_item.setData(Qt.ItemDataRole.UserRole, municipio_id)
                cp_item.setData(int(Qt.ItemDataRole.UserRole) + 1, codigo_postal)
                mun_item.setData(Qt.ItemDataRole.UserRole, municipio_id)
                mun_item.setData(int(Qt.ItemDataRole.UserRole) + 1, codigo_postal)
                for table_item in (isla_item, prov_item):
                    table_item.setFlags(table_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, 0, cp_item)
                self.table.setItem(row_idx, 1, mun_item)
                self.table.setItem(row_idx, 2, isla_item)
                self.table.setItem(row_idx, 3, prov_item)
        finally:
            self.table.blockSignals(False)
            self.table.setSortingEnabled(sorting_was_enabled)
            if sorting_was_enabled and sort_col >= 0:
                self.table.sortByColumn(sort_col, sort_order)
            self._loading_table = False

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_table:
            return
        row_idx = item.row()
        cp_cell = self.table.item(row_idx, 0)
        mun_cell = self.table.item(row_idx, 1)
        if cp_cell is None or mun_cell is None:
            return
        old_municipio_id = str(cp_cell.data(Qt.ItemDataRole.UserRole) or mun_cell.data(Qt.ItemDataRole.UserRole) or "").strip()
        old_codigo_postal = str(cp_cell.data(int(Qt.ItemDataRole.UserRole) + 1) or mun_cell.data(int(Qt.ItemDataRole.UserRole) + 1) or "").strip()
        new_codigo_postal = str(cp_cell.text() or "").strip()
        municipio_name = str(mun_cell.text() or "").strip()
        new_municipio_id = self.municipio_id_by_name.get(
            municipio_name, self.municipio_id_by_name.get(municipio_name.lower(), "")
        )
        if not new_codigo_postal or not new_municipio_id:
            self.reload()
            return
        try:
            status = self.catalog_service.replace_codigo_postal(
                old_municipio_id=old_municipio_id,
                old_codigo_postal=old_codigo_postal,
                new_municipio_id=new_municipio_id,
                new_codigo_postal=new_codigo_postal,
            )
            if status == "unchanged":
                return
        except Exception as exc:
            QMessageBox.warning(self, "Codigos postales", f"No se pudo guardar: {exc}")
        self.reload()

    def _selected_row(self) -> CodigoPostal | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_idx = selected[0].row()
        cp_item = self.table.item(row_idx, 0)
        if cp_item is None:
            return None
        municipio_id = str(cp_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        codigo_postal = str(cp_item.data(int(Qt.ItemDataRole.UserRole) + 1) or "").strip()
        if not municipio_id or not codigo_postal:
            return None
        for row in self.rows:
            if (
                str(getattr(row, "municipio_id", "") or "") == municipio_id
                and str(getattr(row, "codigo_postal", "") or "") == codigo_postal
            ):
                return row
        return None

    def _new_entity(self) -> None:
        schema = [
            {"name": "municipio_id", "label": "Municipio_ID"},
            {"name": "codigo_postal", "label": "Codigo_Postal"},
        ]
        dialog = EntityDialog("Nuevo: Codigo postal", schema, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        try:
            self._validate_required(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Atencion", str(exc))
            return
        self.catalog_service.create_codigo_postal(payload)
        self.reload()

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un codigo postal.")
            return
        schema = [
            {"name": "municipio_id", "label": "Municipio_ID"},
            {"name": "codigo_postal", "label": "Codigo_Postal"},
        ]
        initial = {
            "municipio_id": row.municipio_id,
            "codigo_postal": row.codigo_postal,
        }
        dialog = EntityDialog("Editar: Codigo postal", schema, initial=initial, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        try:
            self._validate_required(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Atencion", str(exc))
            return

        old_municipio_id = str(row.municipio_id or "").strip()
        old_codigo_postal = str(row.codigo_postal or "").strip()
        new_municipio_id = str(payload["municipio_id"]).strip()
        new_codigo_postal = str(payload["codigo_postal"]).strip()

        status = self.catalog_service.replace_codigo_postal(
            old_municipio_id=old_municipio_id,
            old_codigo_postal=old_codigo_postal,
            new_municipio_id=new_municipio_id,
            new_codigo_postal=new_codigo_postal,
        )
        if status == "missing":
            QMessageBox.warning(self, "Atencion", "Codigo postal no encontrado.")
            return
        if status == "exists":
            QMessageBox.warning(self, "Atencion", "Ya existe ese municipio_id + codigo_postal.")
            return
        if status == "unchanged":
            return
        self.reload()

    def _delete_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un codigo postal.")
            return
        answer = QMessageBox.question(self, "Confirmar", f"Eliminar codigo postal {row.codigo_postal}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.catalog_service.delete_codigo_postal(row.municipio_id, row.codigo_postal)
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

        schema = [
            {"name": "municipio_id", "label": "Municipio_ID"},
            {"name": "codigo_postal", "label": "Codigo_Postal"},
        ]
        aliases = {
            "municipio_id": ["municipio_uuid", "municipioid", "id_municipio"],
            "codigo_postal": ["cp", "codigo", "postal"],
        }

        imported, errors = self.catalog_service.import_codigos_postales(Path(file_path), schema, aliases)

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

    def _validate_required(self, payload: dict) -> None:
        self.catalog_service.validate_codigo_postal(payload)


class LocalidadesTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.catalog_service = AddressCatalogService()
        self.rows: list[Localidad] = []
        self.municipio_name_by_id: dict[str, str] = {}
        self.municipio_id_by_name: dict[str, str] = {}
        self.total_rows_count: int = 0
        self._loading_table = False
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por localidad, codigo postal o municipio...")
        self.search_input.textChanged.connect(self.reload)
        toolbar.addWidget(self.search_input, 1)
        self.counter_label = QLabel("0/0")
        self.counter_label.setProperty("role", "secondaryText")
        toolbar.addWidget(self.counter_label)

        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setProperty("btnRole", "success")
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setProperty("btnRole", "warning")
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.setProperty("btnRole", "danger")
        self.import_btn = QPushButton("Importar Excel/CSV")
        self.import_btn.setProperty("btnRole", "secondary")
        self.refresh_btn = QPushButton("Refrescar")
        self.refresh_btn.setProperty("btnRole", "secondary")

        self.new_btn.clicked.connect(self._new_entity)
        self.edit_btn.clicked.connect(self._edit_entity)
        self.delete_btn.clicked.connect(self._delete_entity)
        self.import_btn.clicked.connect(self._import_entities)
        self.refresh_btn.clicked.connect(self.reload)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 3)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setHorizontalHeaderLabels(["Localidad", "Codigo postal", "Municipio"])
        self.table.setSortingEnabled(True)
        self.table.setColumnWidth(1, 140)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

    def reload(self) -> None:
        term = self.search_input.text().strip()
        self.rows, self.total_rows_count, municipios = self.catalog_service.list_localidades(term)
        self.municipio_name_by_id = {str(m.municipio_id): str(m.municipio_nombre or "") for m in municipios}
        self.municipio_id_by_name = {}
        for m in municipios:
            name = str(m.municipio_nombre or "").strip()
            mid = str(m.municipio_id or "").strip()
            if name and mid:
                self.municipio_id_by_name[name] = mid
                self.municipio_id_by_name[name.lower()] = mid
        self.counter_label.setText(f"{len(self.rows)}/{self.total_rows_count}")
        self._render_table()

    def _render_table(self) -> None:
        self._loading_table = True
        self.table.blockSignals(True)
        sorting_was_enabled = self.table.isSortingEnabled()
        sort_col = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(self.rows))
            for row_idx, item in enumerate(self.rows):
                localidad_id = str(item.localidad_id or "")
                municipio_id = str(item.municipio_id or "")
                name_item = QTableWidgetItem(str(item.localidad_nombre or ""))
                cp_item = QTableWidgetItem(str(item.codigo_postal or ""))
                mun_item = QTableWidgetItem(self.municipio_name_by_id.get(municipio_id, ""))
                for table_item in (name_item, cp_item, mun_item):
                    table_item.setData(Qt.ItemDataRole.UserRole, localidad_id)
                self.table.setItem(row_idx, 0, name_item)
                self.table.setItem(row_idx, 1, cp_item)
                self.table.setItem(row_idx, 2, mun_item)
        finally:
            self.table.blockSignals(False)
            self.table.setSortingEnabled(sorting_was_enabled)
            if sorting_was_enabled and sort_col >= 0:
                self.table.sortByColumn(sort_col, sort_order)
            self._loading_table = False

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_table:
            return
        localidad_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not localidad_id:
            return
        row_idx = item.row()
        localidad_cell = self.table.item(row_idx, 0)
        cp_cell = self.table.item(row_idx, 1)
        municipio_cell = self.table.item(row_idx, 2)
        localidad_nombre = str(localidad_cell.text() if localidad_cell else "").strip()
        codigo_postal = str(cp_cell.text() if cp_cell else "").strip()
        municipio_name = str(municipio_cell.text() if municipio_cell else "").strip()
        municipio_id = self.municipio_id_by_name.get(
            municipio_name, self.municipio_id_by_name.get(municipio_name.lower(), "")
        )
        if not localidad_nombre or not municipio_id:
            self.reload()
            return
        codigo_postal_value = codigo_postal or None
        try:
            ok = self.catalog_service.update_localidad_cells(
                localidad_id,
                localidad_nombre=localidad_nombre,
                municipio_id=municipio_id,
                codigo_postal=codigo_postal_value,
            )
            if not ok:
                self.reload()
                return
        except Exception as exc:
            QMessageBox.warning(self, "Localidades", f"No se pudo guardar: {exc}")
        self.reload()

    def _selected_row(self) -> Localidad | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_idx = selected[0].row()
        id_item = self.table.item(row_idx, 0)
        if id_item is None:
            return None
        localidad_id = str(id_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not localidad_id:
            return None
        for row in self.rows:
            if str(getattr(row, "localidad_id", "") or "") == localidad_id:
                return row
        return None

    def _new_entity(self) -> None:
        municipios = sorted(
            [(str(name or ""), str(mid or "")) for mid, name in self.municipio_name_by_id.items() if name],
            key=lambda x: x[0].lower(),
        )
        dialog = LocalidadCreateDialog(municipios, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        try:
            self.catalog_service.create_localidad(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Atencion", str(exc))
            return
        self.reload()

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona una localidad.")
            return
        schema = [
            {"name": "localidad_id", "label": "Localidad_ID"},
            {"name": "municipio_id", "label": "Municipio_ID"},
            {"name": "localidad_nombre", "label": "Localidad_Nombre"},
            {"name": "codigo_postal", "label": "Codigo_Postal"},
        ]
        initial = {
            "localidad_id": row.localidad_id,
            "municipio_id": row.municipio_id,
            "localidad_nombre": row.localidad_nombre,
            "codigo_postal": row.codigo_postal,
        }
        dialog = EntityDialog("Editar: Localidad", schema, initial=initial, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        try:
            self._validate_required(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Atencion", str(exc))
            return
        if not self.catalog_service.replace_localidad(row.localidad_id, payload):
            QMessageBox.warning(self, "Atencion", "Localidad no encontrada.")
            return
        self.reload()

    def _delete_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona una localidad.")
            return
        answer = QMessageBox.question(self, "Confirmar", f"Eliminar localidad {row.localidad_nombre}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.catalog_service.delete_localidad(row.localidad_id)
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

        schema = [
            {"name": "localidad_id", "label": "Localidad_ID"},
            {"name": "municipio_id", "label": "Municipio_ID"},
            {"name": "localidad_nombre", "label": "Localidad_Nombre"},
            {"name": "codigo_postal", "label": "Codigo_Postal"},
        ]
        aliases = {
            "localidad_id": ["id", "uuid", "localidad_uuid"],
            "municipio_id": ["municipio_uuid", "municipioid", "id_municipio"],
            "localidad_nombre": ["nombre", "localidad"],
            "codigo_postal": ["cp", "codigo", "postal"],
        }

        imported, errors = self.catalog_service.import_localidades(Path(file_path), schema, aliases)

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

    def _validate_required(self, payload: dict) -> None:
        self.catalog_service.validate_localidad(payload)


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.settings_provider_service = SettingsProviderService()
        self.settings_import_service = SettingsImportService()
        self.settings_orders_import_service = SettingsOrdersImportService(self.settings_import_service)
        self.settings_sales_import_service = SettingsSalesImportService(
            settings_import_service=self.settings_import_service,
        )
        self.settings_sales_preview_service = SettingsSalesPreviewService(
            settings_import_service=self.settings_import_service,
        )
        self.settings_maintenance_ui_service = SettingsMaintenanceUiService()
        self._igsa_pdf_preview_lines: list[object] = []
        self._igsa_book_preview_lines: list[object] = []
        self._build_ui()
        self._refresh_status()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel("Configuracion")
        header.setProperty("role", "pageTitle")
        layout.addWidget(header)

        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self._build_db_export_tab(), "Exportacion BD")
        self.main_tabs.addTab(self._build_db_import_tab(), "Importacion BD")
        self.main_tabs.addTab(self._build_db_maintenance_tab(), "Mantenimiento BD")
        self.main_tabs.addTab(self._build_api_tab(), "API")
        self.main_tabs.addTab(self._build_mail_tab(), "Corro")
        self.main_tabs.addTab(self._build_auxiliares_tab(), "Auxiliares")
        layout.addWidget(self.main_tabs, 1)

    def _build_api_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        provider_view = self.settings_provider_service.build_ui_view()

        fdc_card = QFrame()
        fdc_card.setObjectName("card")
        fdc_layout = QVBoxLayout(fdc_card)
        fdc_layout.setContentsMargins(10, 10, 10, 10)
        fdc_layout.setSpacing(8)

        fdc_title = QLabel(provider_view.fdc_title)
        fdc_title.setProperty("role", "sectionTitle")
        fdc_layout.addWidget(fdc_title)

        form = QFormLayout()
        self.fdc_api_key_input = QLineEdit()
        self.fdc_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.fdc_api_key_input.setPlaceholderText(provider_view.fdc_placeholder)
        loaded = self.settings_provider_service.load_fdc()
        self.fdc_api_key_input.setText(str(loaded.get("api_key") or ""))
        self.fdc_data_type_combo = QComboBox()
        self.fdc_data_type_combo.addItems(list(provider_view.fdc_data_type_options))
        current_data_type = str(loaded.get("data_type") or "Foundation")
        idx = self.fdc_data_type_combo.findText(current_data_type)
        if idx >= 0:
            self.fdc_data_type_combo.setCurrentIndex(idx)
        form.addRow(provider_view.fdc_api_key_label, self.fdc_api_key_input)
        form.addRow(provider_view.fdc_data_type_label, self.fdc_data_type_combo)
        fdc_layout.addLayout(form)

        actions = QHBoxLayout()
        self.fdc_save_btn = QPushButton(provider_view.save_button_label)
        self.fdc_save_btn.setProperty("btnRole", "success")
        self.fdc_test_btn = QPushButton(provider_view.test_button_label)
        self.fdc_test_btn.setProperty("btnRole", "secondary")
        self.fdc_save_btn.clicked.connect(self._save_fdc_settings)
        self.fdc_test_btn.clicked.connect(self._test_fdc_connection)
        actions.addWidget(self.fdc_save_btn)
        actions.addWidget(self.fdc_test_btn)
        actions.addStretch(1)
        fdc_layout.addLayout(actions)

        self.fdc_info_label = QLabel(provider_view.secret_info_label)
        self.fdc_info_label.setWordWrap(True)
        fdc_layout.addWidget(self.fdc_info_label)
        layout.addWidget(fdc_card)

        fat_card = QFrame()
        fat_card.setObjectName("card")
        fat_layout = QVBoxLayout(fat_card)
        fat_layout.setContentsMargins(10, 10, 10, 10)
        fat_layout.setSpacing(8)

        fat_title = QLabel(provider_view.fatsecret_title)
        fat_title.setProperty("role", "sectionTitle")
        fat_layout.addWidget(fat_title)
        fat_loaded = self.settings_provider_service.load_fatsecret()

        fat_form = QFormLayout()
        self.fatsecret_client_id_input = QLineEdit()
        self.fatsecret_client_id_input.setPlaceholderText(provider_view.fatsecret_client_id_placeholder)
        self.fatsecret_client_id_input.setText(str(fat_loaded.get("client_id") or ""))
        self.fatsecret_client_secret_input = QLineEdit()
        self.fatsecret_client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.fatsecret_client_secret_input.setPlaceholderText(provider_view.fatsecret_client_secret_placeholder)
        self.fatsecret_client_secret_input.setText(str(fat_loaded.get("client_secret") or ""))
        self.fatsecret_scope_input = QLineEdit()
        self.fatsecret_scope_input.setPlaceholderText(provider_view.fatsecret_scope_placeholder)
        self.fatsecret_scope_input.setText(str(fat_loaded.get("scope") or "basic"))
        fat_form.addRow(provider_view.fatsecret_client_id_label, self.fatsecret_client_id_input)
        fat_form.addRow(provider_view.fatsecret_client_secret_label, self.fatsecret_client_secret_input)
        fat_form.addRow(provider_view.fatsecret_scope_label, self.fatsecret_scope_input)
        fat_layout.addLayout(fat_form)

        fat_actions = QHBoxLayout()
        self.fatsecret_save_btn = QPushButton(provider_view.save_button_label)
        self.fatsecret_save_btn.setProperty("btnRole", "success")
        self.fatsecret_test_btn = QPushButton(provider_view.test_button_label)
        self.fatsecret_test_btn.setProperty("btnRole", "secondary")
        self.fatsecret_save_btn.clicked.connect(self._save_fatsecret_settings)
        self.fatsecret_test_btn.clicked.connect(self._test_fatsecret_connection)
        fat_actions.addWidget(self.fatsecret_save_btn)
        fat_actions.addWidget(self.fatsecret_test_btn)
        fat_actions.addStretch(1)
        fat_layout.addLayout(fat_actions)

        fat_info = QLabel(provider_view.secret_info_label)
        fat_info.setWordWrap(True)
        fat_layout.addWidget(fat_info)
        layout.addWidget(fat_card)

        openai_card = QFrame()
        openai_card.setObjectName("card")
        openai_layout = QVBoxLayout(openai_card)
        openai_layout.setContentsMargins(10, 10, 10, 10)
        openai_layout.setSpacing(8)
        openai_title = QLabel(provider_view.openai_title)
        openai_title.setProperty("role", "sectionTitle")
        openai_layout.addWidget(openai_title)
        oa_loaded = self.settings_provider_service.load_openai()

        openai_form = QFormLayout()
        self.openai_api_key_input = QLineEdit()
        self.openai_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_api_key_input.setPlaceholderText(provider_view.openai_placeholder)
        self.openai_api_key_input.setText(str(oa_loaded.get("api_key") or ""))
        openai_form.addRow(provider_view.openai_api_key_label, self.openai_api_key_input)
        openai_layout.addLayout(openai_form)
        self.use_ai_translation_check = QCheckBox(provider_view.openai_ai_translation_label)
        self.use_ai_translation_check.setChecked(bool(oa_loaded.get("use_ai_translation", False)))
        openai_layout.addWidget(self.use_ai_translation_check)

        openai_actions = QHBoxLayout()
        self.openai_save_btn = QPushButton(provider_view.save_button_label)
        self.openai_save_btn.setProperty("btnRole", "success")
        self.openai_test_btn = QPushButton(provider_view.test_button_label)
        self.openai_test_btn.setProperty("btnRole", "secondary")
        self.openai_save_btn.clicked.connect(self._save_openai_settings)
        self.openai_test_btn.clicked.connect(self._test_openai_connection)
        openai_actions.addWidget(self.openai_save_btn)
        openai_actions.addWidget(self.openai_test_btn)
        openai_actions.addStretch(1)
        openai_layout.addLayout(openai_actions)

        openai_info = QLabel(provider_view.secret_info_label)
        openai_info.setWordWrap(True)
        openai_layout.addWidget(openai_info)
        layout.addWidget(openai_card)

        layout.addStretch(1)
        return panel

    def _build_db_maintenance_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        maintenance_view = self.settings_maintenance_ui_service.build_view()

        status_card = QFrame()
        status_card.setObjectName("card")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(10, 10, 10, 10)
        status_layout.setSpacing(6)
        self.db_path_label = QLabel()
        self.db_size_label = QLabel()
        self.db_rows_label = QLabel()
        self.orphans_label = QLabel()
        self.legacy_label = QLabel()
        for label in (self.db_path_label, self.db_size_label, self.db_rows_label, self.orphans_label, self.legacy_label):
            label.setWordWrap(True)
            status_layout.addWidget(label)
        layout.addWidget(status_card)

        actions_row = QHBoxLayout()
        self.refresh_btn = QPushButton(maintenance_view.refresh_button_label)
        self.refresh_btn.setProperty("btnRole", "secondary")
        self.integrity_btn = QPushButton(maintenance_view.integrity_button_label)
        self.integrity_btn.setProperty("btnRole", "warning")
        self.repair_links_btn = QPushButton(maintenance_view.repair_links_button_label)
        self.repair_links_btn.setProperty("btnRole", "warning")
        self.create_missing_clients_btn = QPushButton(maintenance_view.create_missing_clients_button_label)
        self.create_missing_clients_btn.setProperty("btnRole", "danger")
        self.optimize_btn = QPushButton(maintenance_view.optimize_button_label)
        self.optimize_btn.setProperty("btnRole", "warning")
        self.backup_btn = QPushButton(maintenance_view.backup_button_label)
        self.backup_btn.setProperty("btnRole", "success")

        self.refresh_btn.clicked.connect(self._refresh_status)
        self.integrity_btn.clicked.connect(self._run_integrity_check)
        self.repair_links_btn.clicked.connect(self._repair_links)
        self.create_missing_clients_btn.clicked.connect(self._create_missing_clients)
        self.optimize_btn.clicked.connect(self._optimize_db)
        self.backup_btn.clicked.connect(self._backup_db)

        for btn in (
            self.refresh_btn,
            self.integrity_btn,
            self.repair_links_btn,
            self.create_missing_clients_btn,
            self.optimize_btn,
            self.backup_btn,
        ):
            actions_row.addWidget(btn)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText(maintenance_view.log_placeholder)
        layout.addWidget(self.log_box, 1)
        return panel

    def _build_direcciones_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        tabs = QTabWidget()
        tabs.addTab(ProvinciasTab(), "Provincias")
        tabs.addTab(IslasTab(), "Islas")
        tabs.addTab(MunicipiosTab(), "Municipios")
        tabs.addTab(CodigosPostalesTab(), "Codigos postales")
        tabs.addTab(LocalidadesTab(), "Localidades")
        layout.addWidget(tabs, 1)
        return panel

    def _build_auxiliares_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        tabs = QTabWidget()
        tabs.addTab(self._build_direcciones_tab(), "Direcciones")
        layout.addWidget(tabs, 1)
        return panel

    def _build_mail_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        orders_mail_card = QFrame()
        orders_mail_card.setObjectName("card")
        orders_mail_layout = QVBoxLayout(orders_mail_card)
        orders_mail_layout.setContentsMargins(10, 10, 10, 10)
        orders_mail_layout.setSpacing(8)
        orders_loaded = self.settings_provider_service.load_orders_mail_view()
        orders_mail_title = QLabel(orders_loaded.title)
        orders_mail_title.setProperty("role", "sectionTitle")
        orders_mail_layout.addWidget(orders_mail_title)

        orders_form = QFormLayout()
        self.orders_mail_destino_input = QLineEdit()
        self.orders_mail_destino_input.setPlaceholderText(orders_loaded.destino_placeholder)
        self.orders_mail_destino_input.setText(orders_loaded.destino_email)
        orders_form.addRow("Email destino fijo", self.orders_mail_destino_input)

        self.orders_historico_dir_input = QLineEdit()
        self.orders_historico_dir_input.setPlaceholderText(orders_loaded.historico_placeholder)
        self.orders_historico_dir_input.setText(orders_loaded.historico_dir)
        historico_row = QHBoxLayout()
        historico_row.addWidget(self.orders_historico_dir_input, 1)
        self.orders_historico_dir_btn = QPushButton(orders_loaded.selector_button_label)
        self.orders_historico_dir_btn.setProperty("btnRole", "secondary")
        self.orders_historico_dir_btn.clicked.connect(self._pick_orders_historico_dir)
        historico_row.addWidget(self.orders_historico_dir_btn)
        historico_row_widget = QWidget()
        historico_row_widget.setLayout(historico_row)
        orders_form.addRow("Ruta historico", historico_row_widget)
        orders_mail_layout.addLayout(orders_form)

        orders_actions = QHBoxLayout()
        self.orders_mail_save_btn = QPushButton(orders_loaded.save_button_label)
        self.orders_mail_save_btn.setProperty("btnRole", "success")
        self.orders_mail_save_btn.clicked.connect(self._save_orders_mail_settings)
        orders_actions.addWidget(self.orders_mail_save_btn)
        orders_actions.addStretch(1)
        orders_mail_layout.addLayout(orders_actions)

        orders_info = QLabel(orders_loaded.info_label)
        orders_info.setWordWrap(True)
        orders_mail_layout.addWidget(orders_info)
        layout.addWidget(orders_mail_card)
        layout.addStretch(1)
        return panel

    def _build_db_import_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        tabs = QTabWidget()
        for name in (
            "Clientes",
            "Contactos",
            "Tecnicos",
            "Distribuidores",
            "Colaboradores",
            "Cursos",
            "Formulas",
            "Almacen",
            "Productos IREKS",
            "Materias primas",
            "Pedidos",
            "Ventas",
            "Configuracion",
        ):
            tabs.addTab(self._build_import_section_tab(name), name)
        layout.addWidget(tabs, 1)
        return panel

    def _build_db_export_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        tabs = QTabWidget()
        for name in (
            "Clientes",
            "Contactos",
            "Tecnicos",
            "Distribuidores",
            "Colaboradores",
            "Cursos",
            "Formulas",
            "Almacen",
            "Productos IREKS",
            "Materias primas",
            "Pedidos",
            "Ventas",
            "Configuracion",
        ):
            tabs.addTab(self._build_export_section_tab(name), name)
        layout.addWidget(tabs, 1)
        return panel

    def _build_import_section_tab(self, section_name: str) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        profile_map: dict[str, list[str]] = {
            "Distribuidores": ["proveedores"],
            "Productos IREKS": ["productos_ireks", "tarifa_precios_ireks", "valores_nutricionales_ireks"],
            "Materias primas": ["materias_primas", "materias_primas_formato", "precios_materias_primas"],
            "Auxiliares": ["provincias", "islas", "municipios", "codigos_postales", "localidades"],
        }

        if section_name == "Pedidos":
            orders_import_view = self.settings_orders_import_service.build_orders_import_view()
            card_orders = QFrame()
            card_orders.setObjectName("card")
            card_orders_layout = QHBoxLayout(card_orders)
            card_orders_layout.setContentsMargins(10, 10, 10, 10)
            card_orders_layout.setSpacing(8)
            info_orders = QLabel(orders_import_view.section_info_label)
            info_orders.setWordWrap(True)
            self.orders_import_almacen_combo = QComboBox()
            self.orders_import_almacen_combo.setMinimumWidth(260)
            import_orders_btn = QPushButton(orders_import_view.import_button_label)
            import_orders_btn.setProperty("btnRole", "secondary")
            import_orders_btn.clicked.connect(self._import_orders_json_from_settings)
            card_orders_layout.addWidget(info_orders, 1)
            card_orders_layout.addWidget(QLabel(orders_import_view.selector_label))
            card_orders_layout.addWidget(self.orders_import_almacen_combo)
            card_orders_layout.addWidget(import_orders_btn)
            layout.addWidget(card_orders)
            self._load_orders_import_almacen_combo()

        elif section_name == "Ventas":
            sales_import_view = self.settings_sales_import_service.build_import_view()
            card = QFrame()
            card.setObjectName("card")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(8)
            info = QLabel(sales_import_view.section_info_label)
            info.setWordWrap(True)
            import_btn = QPushButton(sales_import_view.import_button_label)
            import_btn.setProperty("btnRole", "secondary")
            import_btn.clicked.connect(self._import_ireks_sales_json)
            card_layout.addWidget(info, 1)
            card_layout.addWidget(import_btn)
            layout.addWidget(card)

            card_igsa = QFrame()
            card_igsa.setObjectName("card")
            card_igsa_layout = QHBoxLayout(card_igsa)
            card_igsa_layout.setContentsMargins(10, 10, 10, 10)
            card_igsa_layout.setSpacing(8)
            info_igsa = QLabel(
                "Importacion de ventas IGSA centralizada. "
                "Usa uno de los dos botones para cargar datos y, desde la vista previa, confirmar la importacion."
            )
            info_igsa.setWordWrap(True)
            preview_igsa_book_btn = QPushButton("Cargar libro")
            preview_igsa_book_btn.setProperty("btnRole", "secondary")
            preview_igsa_book_btn.clicked.connect(self._preview_igsa_sales_workbook)
            preview_igsa_pdf_btn = QPushButton("Cargar PDFs")
            preview_igsa_pdf_btn.setProperty("btnRole", "secondary")
            preview_igsa_pdf_btn.clicked.connect(self._preview_igsa_sales_pdf)
            card_igsa_layout.addWidget(info_igsa, 1)
            card_igsa_layout.addWidget(preview_igsa_book_btn)
            card_igsa_layout.addWidget(preview_igsa_pdf_btn)
            layout.addWidget(card_igsa)

        else:
            note = QLabel(
                f"Esta seccion no tiene importadores de mantenimiento especificos en esta version ({section_name})."
            )
            note.setWordWrap(True)
            layout.addWidget(note)

        allowed_profiles = profile_map.get(section_name, [])
        if allowed_profiles:
            layout.addWidget(
                DbImportConsoleTab(
                    on_import_completed=self._refresh_status,
                    allowed_profile_keys=allowed_profiles,
                    title=f"Importacion de {section_name}",
                ),
                1,
            )
        elif section_name == "Configuracion":
            layout.addWidget(DbImportConsoleTab(on_import_completed=self._refresh_status), 1)
        else:
            layout.addStretch(1)
        return panel

    def _build_export_section_tab(self, section_name: str) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        table_map: dict[str, list[str]] = {
            "Clientes": ["clientes"],
            "Contactos": ["contactos"],
            "Tecnicos": ["tecnicos"],
            "Distribuidores": ["distribuidores", "proveedores", "referencias_distribuidor"],
            "Colaboradores": ["colaboradores"],
            "Cursos": ["cursos", "asistentes", "cursos_tecnicos", "cursos_documentos"],
            "Formulas": ["recetas", "receta_lineas", "receta_versiones", "escandallos"],
            "Almacen": [
                "almacenes_catalogo",
                "almacen_stock",
                "almacen_movimientos",
                "inventarios_cabecera",
                "inventarios_detalle",
                "albaranes",
                "albaranes_items",
                "pedidos_pendientes",
            ],
            "Productos IREKS": [
                "productos_ireks",
                "productos_ireks_referencias_distribuidor",
                "tarifa_precios_ireks",
                "productos_valores_nutricionales",
            ],
            "Materias primas": ["materias_primas", "materias_primas_precios", "materias_primas_formato"],
            "Pedidos": ["pedidos", "pedidos_items", "albaranes", "albaranes_items", "pedidos_pendientes"],
            "Ventas": ["ventas_import_lotes", "ventas_mensuales_raw"],
            "Configuracion": [
                "provincias",
                "islas",
                "municipios",
                "codigos_postales",
                "localidades",
                "fabricantes",
                "familias",
                "subfamilias",
                "envases",
            ],
        }
        allowed_tables = table_map.get(section_name, [])
        info = QLabel(
            f"Exporta las tablas asociadas a {section_name}."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addWidget(
            DbExportConsoleTab(
                title=f"Consola de exportacion - {section_name}",
                allowed_table_names=allowed_tables,
            ),
            1,
        )
        return panel

    def _refresh_status(self) -> None:
        status = self.settings_maintenance_ui_service.build_status_view()
        self.db_path_label.setText(status.db_path_label)
        self.db_size_label.setText(status.db_size_label)
        self.db_rows_label.setText(status.db_rows_label)
        self.orphans_label.setText(status.orphans_label)
        self.legacy_label.setText(status.legacy_label)
        self._append_log(status.log_message)

    def _run_integrity_check(self) -> None:
        try:
            outcome = self.settings_maintenance_ui_service.run_integrity_check()
            self._append_log(outcome.log_message)
            if outcome.ok:
                QMessageBox.information(self, outcome.title, outcome.message)
            else:
                QMessageBox.warning(self, outcome.title, outcome.message)
        except Exception as exc:
            QMessageBox.critical(self, "Integridad DB", f"No se pudo ejecutar el chequeo: {exc}")
            self._append_log(f"ERROR integridad: {exc}")

    def _repair_links(self) -> None:
        try:
            outcome = self.settings_maintenance_ui_service.repair_contact_links()
            self._append_log(outcome.log_message)
            self._refresh_status()
            QMessageBox.information(self, outcome.title, outcome.message)
        except Exception as exc:
            QMessageBox.critical(self, "Reparar enlaces", f"No se pudo reparar enlaces: {exc}")
            self._append_log(f"ERROR reparar enlaces: {exc}")

    def _optimize_db(self) -> None:
        answer = QMessageBox.question(
            self,
            "Optimizar DB",
            "Se ejecutara PRAGMA optimize, ANALYZE y VACUUM. Puede tardar unos segundos. Continuar?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            outcome = self.settings_maintenance_ui_service.optimize_database()
            self._append_log(outcome.log_message)
            self._refresh_status()
            QMessageBox.information(self, outcome.title, outcome.message)
        except Exception as exc:
            QMessageBox.critical(self, "Optimizar DB", f"No se pudo optimizar: {exc}")
            self._append_log(f"ERROR optimizar DB: {exc}")

    def _create_missing_clients(self) -> None:
        answer = QMessageBox.question(
            self,
            "Crear clientes faltantes",
            (
                "Se crearan clientes tecnicos para cada Cliente_ID de contactos sin correspondencia.\n"
                "Esto permite mantener la relacion y mostrar empresa en Contactos.\n\n"
                "Continuar?"
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            outcome = self.settings_maintenance_ui_service.create_missing_clients()
            self._append_log(outcome.log_message)
            self._refresh_status()
            QMessageBox.information(self, outcome.title, outcome.message)
        except Exception as exc:
            QMessageBox.critical(self, "Clientes faltantes", f"No se pudo completar la operacion: {exc}")
            self._append_log(f"ERROR crear clientes faltantes: {exc}")

    def _backup_db(self) -> None:
        default_path = self.settings_maintenance_ui_service.build_backup_default_path()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar backup de base de datos",
            str(default_path),
            "SQLite (*.db)",
        )
        if not file_path:
            return
        try:
            outcome = self.settings_maintenance_ui_service.backup_database(Path(file_path))
            self._append_log(outcome.log_message)
            QMessageBox.information(self, outcome.title, outcome.message)
        except Exception as exc:
            QMessageBox.critical(self, "Backup DB", f"No se pudo crear backup: {exc}")
            self._append_log(f"ERROR backup DB: {exc}")

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_box.append(f"[{timestamp}] {message}")

    def _load_orders_import_almacen_combo(self) -> None:
        if not hasattr(self, "orders_import_almacen_combo"):
            return
        self.orders_import_almacen_combo.clear()
        orders_import_view = self.settings_orders_import_service.build_orders_import_view()
        for option in orders_import_view.warehouse_options:
            self.orders_import_almacen_combo.addItem(option.label, option.value)

    def _import_orders_json_from_settings(self) -> None:
        almacen_id = str(self.orders_import_almacen_combo.currentData() or "").strip()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo de pedidos",
            "",
            "Archivos JSON (*.json)",
        )
        if not file_path:
            return
        source = Path(file_path)
        try:
            outcome = self.settings_orders_import_service.import_orders_json(source, almacen_id)
        except Exception as exc:
            QMessageBox.warning(self, "Importacion pedidos", str(exc))
            return
        self._append_log(outcome.log_message)
        QMessageBox.information(self, "Importacion pedidos", "\n".join(outcome.summary_lines))

    def _preview_igsa_sales_pdf(self) -> None:
        preview_view = self.settings_sales_preview_service.build_preview_view()
        file_paths, _ = QFileDialog.getOpenFileNames(self, preview_view.pdf_title, "", preview_view.pdf_filter)
        if not file_paths:
            return
        try:
            outcome = self.settings_sales_preview_service.preview_igsa_pdf_files([Path(path) for path in file_paths])
        except Exception as exc:
            QMessageBox.warning(self, preview_view.pdf_preview_error_title, str(exc))
            return
        self._igsa_pdf_preview_lines = list(outcome.lines)
        self._show_igsa_pdf_preview_dialog(outcome.lines, outcome.errors)

    def _show_igsa_pdf_preview_dialog(self, lines: list[object], errors: list[str]) -> None:
        preview_view = self.settings_sales_preview_service.build_preview_view()
        dialog = QDialog(self)
        dialog.setWindowTitle(preview_view.pdf_preview_title)
        dialog.resize(1080, 760)
        root = QVBoxLayout(dialog)
        info = QLabel(
            f"Lineas detectadas: {len(lines)}"
            + (f" | Incidencias: {len(errors)}" if errors else "")
        )
        info.setWordWrap(True)
        root.addWidget(info)
        if errors:
            err = QTextEdit()
            err.setReadOnly(True)
            err.setMaximumHeight(110)
            err.setPlainText("\n".join(errors))
            root.addWidget(err)
        table = QTableWidget(0, 15)
        table.setHorizontalHeaderLabels(
            [
                "Fecha",
                "Albaran Nº",
                "Tipo",
                "Cod.Art.",
                "Descripcion",
                "Kilos",
                "Env.",
                "Emb.",
                "Precio",
                "% Dt.",
                "Total",
                "IVA",
                "Lote",
                "Cons.Pref",
                "Archivo",
            ]
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(14, QHeaderView.ResizeMode.Stretch)
        for row_idx, row in enumerate(lines):
            table.insertRow(row_idx)
            values = [
                getattr(row, "fecha", ""),
                getattr(row, "ref_pedido", ""),
                getattr(row, "doc_type", ""),
                getattr(row, "codigo", ""),
                getattr(row, "descripcion", ""),
                f"{float(getattr(row, 'kilos', 0.0)):.2f}",
                f"{float(getattr(row, 'envases', 0.0)):.2f}",
                f"{float(getattr(row, 'emb', 0.0)):.2f}",
                f"{float(getattr(row, 'precio', 0.0)):.2f}",
                f"{float(getattr(row, 'descuento_pct', 0.0)):.2f}",
                f"{float(getattr(row, 'total', 0.0)):.2f}",
                f"{float(getattr(row, 'iva', 0.0)):.2f}",
                getattr(row, "lote", ""),
                getattr(row, "cons_pref", ""),
                getattr(row, "source_file", ""),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_idx in {5, 6, 7, 8, 9, 10, 11}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row_idx, col_idx, item)
        root.addWidget(table, 1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        import_btn = QPushButton(preview_view.pdf_import_button_label)
        import_btn.setProperty("btnRole", "success")
        import_btn.clicked.connect(lambda: self._import_igsa_sales_pdf_preview(close_dialog=dialog))
        actions.addWidget(import_btn)
        close_btn = QPushButton(preview_view.pdf_close_button_label)
        close_btn.setProperty("btnRole", "secondary")
        close_btn.clicked.connect(dialog.accept)
        actions.addWidget(close_btn)
        root.addLayout(actions)
        dialog.exec()

    def _import_igsa_sales_pdf_preview(self, close_dialog: QDialog | None = None) -> None:
        lines = self._igsa_pdf_preview_lines if isinstance(self._igsa_pdf_preview_lines, list) else []
        try:
            outcome = self.settings_sales_import_service.import_igsa_pdf_lines(
                lines=lines,
            )
        except Exception as exc:
            preview_view = self.settings_sales_preview_service.build_preview_view()
            QMessageBox.warning(self, preview_view.pdf_import_error_title, str(exc))
            return
        if outcome.ok:
            QMessageBox.information(self, outcome.title, outcome.message)
            self._append_log(outcome.log_message)
            if close_dialog is not None:
                close_dialog.accept()
        else:
            QMessageBox.warning(self, outcome.title, outcome.message)
            self._append_log(outcome.log_message)

    def _import_ireks_sales_json(self) -> None:
        import_view = self.settings_sales_import_service.build_import_view()
        file_path, _ = QFileDialog.getOpenFileName(self, import_view.ireks_json_title, "", import_view.ireks_json_filter)
        if not file_path:
            return
        try:
            outcome = self.settings_sales_import_service.import_ireks_json(Path(file_path))
        except Exception as exc:
            QMessageBox.warning(self, "Importacion ventas IREKS", str(exc))
            return
        if outcome.ok:
            QMessageBox.information(self, outcome.title, outcome.message)
        else:
            QMessageBox.warning(self, outcome.title, outcome.message)
        self._append_log(outcome.log_message)

    def _preview_igsa_sales_workbook(self) -> None:
        preview_view = self.settings_sales_preview_service.build_preview_view()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            preview_view.workbook_title,
            "",
            preview_view.workbook_filter,
        )
        if not file_path:
            return
        try:
            outcome = self.settings_sales_preview_service.preview_igsa_workbook(Path(file_path))
        except Exception as exc:
            QMessageBox.warning(self, preview_view.workbook_preview_error_title, str(exc))
            return
        self._igsa_book_preview_lines = list(outcome.raw_lines)
        self._show_igsa_workbook_preview_dialog(outcome.preview_rows, outcome.errors)

    def _show_igsa_workbook_preview_dialog(self, lines: list[dict[str, object]], errors: list[str]) -> None:
        preview_view = self.settings_sales_preview_service.build_preview_view()
        dialog = QDialog(self)
        dialog.setWindowTitle(preview_view.workbook_preview_title)
        dialog.resize(1180, 760)
        root = QVBoxLayout(dialog)
        info = QLabel(
            f"Lineas detectadas (desglosadas por lote): {len(lines)}"
            + (f" | Incidencias: {len(errors)}" if errors else "")
        )
        info.setWordWrap(True)
        root.addWidget(info)
        if errors:
            err = QTextEdit()
            err.setReadOnly(True)
            err.setMaximumHeight(130)
            err.setPlainText("\n".join(errors[:100]))
            root.addWidget(err)
        table = QTableWidget(0, 9)
        table.setHorizontalHeaderLabels(
            [
                "Periodo",
                "Ref. Dist.",
                "Cod. Fab.",
                "Descripcion",
                "Peso/Env",
                "Nº Envases",
                "Tot. Kg",
                "Lote",
                "Tipo",
            ]
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        for row_idx, row in enumerate(lines):
            table.insertRow(row_idx)
            values = [
                str(row.get("periodo") or ""),
                str(row.get("ref_distribuidor") or ""),
                str(row.get("ref_fabricante") or ""),
                str(row.get("descripcion") or ""),
                f"{float(row.get('peso_envase') or 0.0):.3f}",
                f"{float(row.get('num_envases') or 0.0):.3f}",
                f"{float(row.get('tot_kg') or 0.0):.3f}",
                str(row.get("lote") or ""),
                str(row.get("tipo") or ""),
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_idx in {4, 5, 6}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row_idx, col_idx, item)
        root.addWidget(table, 1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        import_btn = QPushButton(preview_view.workbook_import_button_label)
        import_btn.setProperty("btnRole", "success")
        import_btn.clicked.connect(lambda: self._import_igsa_sales_workbook_preview(close_dialog=dialog))
        actions.addWidget(import_btn)
        close_btn = QPushButton(preview_view.workbook_close_button_label)
        close_btn.setProperty("btnRole", "secondary")
        close_btn.clicked.connect(dialog.accept)
        actions.addWidget(close_btn)
        root.addLayout(actions)
        dialog.exec()

    def _show_igsa_book_import_result_dialog(self, text: str) -> bool:
        preview_view = self.settings_sales_preview_service.build_preview_view()
        dialog = QDialog(self)
        dialog.setWindowTitle(preview_view.workbook_import_result_title)
        dialog.resize(620, 220)
        layout = QVBoxLayout(dialog)
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label, 1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        reimport_btn = QPushButton(preview_view.workbook_reimport_button_label)
        reimport_btn.setProperty("btnRole", "warning")
        close_btn = QPushButton(preview_view.workbook_close_button_label)
        close_btn.setProperty("btnRole", "secondary")
        actions.addWidget(reimport_btn)
        actions.addWidget(close_btn)
        layout.addLayout(actions)
        reimport_btn.clicked.connect(lambda: dialog.done(2))
        close_btn.clicked.connect(lambda: dialog.done(0))
        return dialog.exec() == 2

    def _import_igsa_sales_workbook_preview(
        self,
        close_dialog: QDialog | None = None,
        *,
        force_reimport: bool = False,
    ) -> None:
        lines = self._igsa_book_preview_lines if isinstance(self._igsa_book_preview_lines, list) else []
        try:
            outcome = self.settings_sales_import_service.import_igsa_workbook_lines(
                lines=lines,
                force_reimport=force_reimport,
            )
        except Exception as exc:
            preview_view = self.settings_sales_preview_service.build_preview_view()
            QMessageBox.warning(self, preview_view.workbook_import_error_title, str(exc))
            return
        if outcome.ok:
            wants_reimport = self._show_igsa_book_import_result_dialog(outcome.message)
            self._append_log(outcome.log_message)
            if close_dialog is not None:
                close_dialog.accept()
            if wants_reimport:
                self._import_igsa_sales_workbook_preview(force_reimport=True)
        else:
            QMessageBox.warning(self, outcome.title, outcome.message)
            self._append_log(outcome.log_message)
    def _save_fdc_settings(self) -> None:
        key = self.fdc_api_key_input.text().strip() if hasattr(self, "fdc_api_key_input") else ""
        data_type = self.fdc_data_type_combo.currentText().strip() if hasattr(self, "fdc_data_type_combo") else "Foundation"
        try:
            result = self.settings_provider_service.save_fdc(key, data_type)
            QMessageBox.information(self, "FoodData Central", f"{result.message}\n{result.path}")
        except Exception as exc:
            QMessageBox.warning(self, "FoodData Central", f"No se pudo guardar la configuracion.\n{exc}")

    def _test_fdc_connection(self) -> None:
        key = self.fdc_api_key_input.text().strip() if hasattr(self, "fdc_api_key_input") else ""
        data_type = self.fdc_data_type_combo.currentText().strip() if hasattr(self, "fdc_data_type_combo") else "Foundation"
        try:
            result = self.settings_provider_service.test_fdc(key, data_type)
            if result.ok:
                QMessageBox.information(self, "FoodData Central", result.message)
            else:
                QMessageBox.warning(self, "FoodData Central", result.message)
        except Exception as exc:
            QMessageBox.warning(self, "FoodData Central", f"Error de conexion.\n{exc}")

    def _save_fatsecret_settings(self) -> None:
        client_id = self.fatsecret_client_id_input.text().strip() if hasattr(self, "fatsecret_client_id_input") else ""
        client_secret = (
            self.fatsecret_client_secret_input.text().strip() if hasattr(self, "fatsecret_client_secret_input") else ""
        )
        scope = self.fatsecret_scope_input.text().strip() if hasattr(self, "fatsecret_scope_input") else "basic"
        try:
            result = self.settings_provider_service.save_fatsecret(client_id, client_secret, scope)
            QMessageBox.information(self, "FatSecret", f"{result.message}\n{result.path}")
        except Exception as exc:
            QMessageBox.warning(self, "FatSecret", f"No se pudo guardar la configuracion.\n{exc}")

    def _test_fatsecret_connection(self) -> None:
        client_id = self.fatsecret_client_id_input.text().strip() if hasattr(self, "fatsecret_client_id_input") else ""
        client_secret = (
            self.fatsecret_client_secret_input.text().strip() if hasattr(self, "fatsecret_client_secret_input") else ""
        )
        scope = self.fatsecret_scope_input.text().strip() if hasattr(self, "fatsecret_scope_input") else "basic"
        try:
            result = self.settings_provider_service.test_fatsecret(client_id, client_secret, scope)
            QMessageBox.information(self, "FatSecret", result.message)
        except Exception as exc:
            QMessageBox.warning(self, "FatSecret", f"Error de conexion.\n{exc}")

    def _save_openai_settings(self) -> None:
        api_key = self.openai_api_key_input.text().strip() if hasattr(self, "openai_api_key_input") else ""
        use_ai = self.use_ai_translation_check.isChecked() if hasattr(self, "use_ai_translation_check") else False
        try:
            result = self.settings_provider_service.save_openai(api_key=api_key, use_ai_translation=use_ai)
            QMessageBox.information(self, "OpenAI", f"{result.message}\n{result.path}")
        except Exception as exc:
            QMessageBox.warning(self, "OpenAI", f"No se pudo guardar la configuracion.\n{exc}")

    def _test_openai_connection(self) -> None:
        api_key = self.openai_api_key_input.text().strip() if hasattr(self, "openai_api_key_input") else ""
        use_ai = self.use_ai_translation_check.isChecked() if hasattr(self, "use_ai_translation_check") else False
        try:
            result = self.settings_provider_service.test_openai(api_key=api_key, use_ai_translation=use_ai)
            if result.ok:
                QMessageBox.information(self, "OpenAI", result.message)
            else:
                QMessageBox.warning(self, "OpenAI", result.message or "No se obtuvo respuesta valida.")
        except Exception as exc:
            QMessageBox.warning(self, "OpenAI", f"Error de conexion.\n{exc}")

    def _pick_orders_historico_dir(self) -> None:
        current = self.orders_historico_dir_input.text().strip() if hasattr(self, "orders_historico_dir_input") else ""
        selected = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar ruta de historico de pedidos",
            current or str(DATA_DIR),
        )
        if selected and hasattr(self, "orders_historico_dir_input"):
            self.orders_historico_dir_input.setText(selected)

    def _save_orders_mail_settings(self) -> None:
        destino = self.orders_mail_destino_input.text().strip() if hasattr(self, "orders_mail_destino_input") else ""
        historico = self.orders_historico_dir_input.text().strip() if hasattr(self, "orders_historico_dir_input") else ""
        try:
            result = self.settings_provider_service.save_orders_mail(destino_email=destino, historico_dir=historico)
            if result.ok:
                QMessageBox.information(self, "Pedidos Outlook", f"{result.message}\n{result.path}")
            else:
                QMessageBox.warning(self, "Pedidos Outlook", result.message)
        except Exception as exc:
            QMessageBox.warning(self, "Pedidos Outlook", f"No se pudo guardar la configuracion.\n{exc}")


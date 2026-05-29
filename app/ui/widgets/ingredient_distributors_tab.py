from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from app.services.provider_service import ProviderService


class IngredientDistributorsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.service = ProviderService()
        self.rows = []
        self.article_rows = []
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
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_panel.setObjectName("sidePanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        left_layout.addWidget(QLabel("Filtro"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar proveedor...")
        self.search_input.textChanged.connect(self._schedule_reload)
        left_layout.addWidget(self.search_input)

        self.table = QTableWidget(0, 2)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setHorizontalHeaderLabels(["Cod.", "Nombre"])
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        left_layout.addWidget(self.table, 1)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(right_splitter, 1)

        top_panel = QWidget()
        top_panel.setObjectName("detailPanel")
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(14, 14, 14, 14)
        top_layout.setSpacing(8)

        ribbon = QFrame()
        ribbon.setObjectName("topRibbon")
        ribbon_layout = QHBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(8, 6, 8, 6)
        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setProperty("btnRole", "success")
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.setProperty("btnRole", "danger")
        self.import_btn = QPushButton("Importar Excel/CSV")
        self.import_btn.setProperty("btnRole", "secondary")
        self.refresh_btn = QPushButton("Refrescar")
        self.refresh_btn.setProperty("btnRole", "secondary")
        self.new_btn.clicked.connect(self._new_distributor)
        self.delete_btn.clicked.connect(self._delete_distributor)
        self.import_btn.clicked.connect(self._import_distributors)
        self.refresh_btn.clicked.connect(self.reload)
        ribbon_layout.addWidget(self.new_btn)
        ribbon_layout.addWidget(self.delete_btn)
        ribbon_layout.addWidget(self.import_btn)
        ribbon_layout.addWidget(self.refresh_btn)
        ribbon_layout.addStretch(1)
        top_layout.addWidget(ribbon)

        title = QLabel("Detalle de proveedor")
        title.setProperty("role", "sectionTitle")
        top_layout.addWidget(title)

        row_1 = QHBoxLayout()
        row_1.addWidget(QLabel("Codigo"))
        self.detail_codigo = QLineEdit()
        self.detail_codigo.setReadOnly(True)
        row_1.addWidget(self.detail_codigo, 1)
        row_1.addWidget(QLabel("Nombre comercial"))
        self.detail_nombre_comercial = QLineEdit()
        row_1.addWidget(self.detail_nombre_comercial, 3)
        top_layout.addLayout(row_1)

        row_2 = QHBoxLayout()
        row_2.addWidget(QLabel("Razon social"))
        self.detail_razon_social = QLineEdit()
        row_2.addWidget(self.detail_razon_social, 2)
        row_2.addWidget(QLabel("CIF"))
        self.detail_cif = QLineEdit()
        row_2.addWidget(self.detail_cif, 1)
        top_layout.addLayout(row_2)

        row_3 = QHBoxLayout()
        row_3.addWidget(QLabel("Telefono"))
        self.detail_telefono = QLineEdit()
        row_3.addWidget(self.detail_telefono, 1)
        row_3.addWidget(QLabel("Contacto"))
        self.detail_contacto = QLineEdit()
        row_3.addWidget(self.detail_contacto, 2)
        top_layout.addLayout(row_3)

        for field in (
            self.detail_nombre_comercial,
            self.detail_razon_social,
            self.detail_cif,
            self.detail_telefono,
            self.detail_contacto,
        ):
            field.textEdited.connect(self._schedule_autosave)

        right_splitter.addWidget(top_panel)

        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        subtitle = QLabel("Articulos del proveedor")
        subtitle.setProperty("role", "sectionTitle")
        bottom_layout.addWidget(subtitle)

        self.articles_table = QTableWidget(0, 3)
        self.articles_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.articles_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.articles_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.articles_table.verticalHeader().setVisible(False)
        articles_header = self.articles_table.horizontalHeader()
        articles_header.setSectionsClickable(True)
        articles_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        articles_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        articles_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.articles_table.setHorizontalHeaderLabels(["Referencia", "Nombre", "Familia"])
        self.articles_table.setSortingEnabled(True)
        bottom_layout.addWidget(self.articles_table, 1)
        right_splitter.addWidget(bottom_panel)
        right_splitter.setStretchFactor(0, 2)
        right_splitter.setStretchFactor(1, 3)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        splitter.handle(1).setEnabled(False)

    def _schedule_reload(self) -> None:
        self._search_timer.start(200)

    def _schedule_autosave(self) -> None:
        if self._is_loading_details:
            return
        self._autosave_timer.start(350)

    def reload(self, selected_id: str | None = None) -> None:
        if selected_id is None:
            selected_id = self._selected_distributor_id()
        self.rows = self.service.list(self.search_input.text().strip())
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for row_idx, row in enumerate(self.rows):
            name = (row.proveedor_nombre_comercial or "").strip() or (row.proveedor_razon_social or "").strip()
            code_item = QTableWidgetItem(str(row.proveedor_codigo or ""))
            code_item.setData(Qt.ItemDataRole.UserRole, row.proveedor_id)
            self.table.setItem(row_idx, 0, code_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(name))
        self.table.setSortingEnabled(True)

        if selected_id:
            self._select_distributor(selected_id)
        elif self.table.rowCount() > 0:
            self.table.selectRow(0)
        else:
            self._clear_details()
            self._render_articles([])

    def _selected_distributor_id(self) -> str:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return ""
        item = self.table.item(rows[0].row(), 0)
        if not item:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def _selected_distributor(self):
        distribuidor_id = self._selected_distributor_id()
        if not distribuidor_id:
            return None
        return next((row for row in self.rows if row.proveedor_id == distribuidor_id), None)

    def _select_distributor(self, distribuidor_id: str) -> None:
        for row_idx in range(self.table.rowCount()):
            item = self.table.item(row_idx, 0)
            if item and str(item.data(Qt.ItemDataRole.UserRole) or "") == distribuidor_id:
                self.table.selectRow(row_idx)
                return

    def _show_selected_details(self) -> None:
        row = self._selected_distributor()
        self._is_loading_details = True
        if not row:
            self._clear_details()
            self._render_articles([])
            self._is_loading_details = False
            return

        self.detail_codigo.setText(str(row.proveedor_codigo or ""))
        self.detail_nombre_comercial.setText(row.proveedor_nombre_comercial or "")
        self.detail_razon_social.setText(row.proveedor_razon_social or "")
        self.detail_cif.setText(row.proveedor_cif or "")
        self.detail_telefono.setText(row.proveedor_telefono or "")
        self.detail_contacto.setText(row.proveedor_contacto or "")
        self._is_loading_details = False
        self.article_rows = self.service.list_articles_by_provider(row.proveedor_id)
        self._render_articles(self.article_rows)

    def _render_articles(self, rows) -> None:
        self.articles_table.setSortingEnabled(False)
        self.articles_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            self.articles_table.setItem(row_idx, 0, QTableWidgetItem(str(row.articulo_referencia_distribuidor or "")))
            self.articles_table.setItem(row_idx, 1, QTableWidgetItem(str(row.articulo_descripcion or "")))
            self.articles_table.setItem(row_idx, 2, QTableWidgetItem(str(row.articulo_familia_id or "")))
        self.articles_table.setSortingEnabled(True)

    def _clear_details(self) -> None:
        self.detail_codigo.clear()
        self.detail_nombre_comercial.clear()
        self.detail_razon_social.clear()
        self.detail_cif.clear()
        self.detail_telefono.clear()
        self.detail_contacto.clear()

    def _autosave_selected_distributor(self) -> None:
        row = self._selected_distributor()
        if not row:
            return
        payload = {
            "distribuidor_codigo": self.detail_codigo.text().strip(),
            "distribuidor_nombre_comercial": self.detail_nombre_comercial.text().strip(),
            "distribuidor_razon_social": self.detail_razon_social.text().strip(),
            "distribuidor_cif": self.detail_cif.text().strip(),
            "distribuidor_telefono": self.detail_telefono.text().strip(),
            "distribuidor_contacto": self.detail_contacto.text().strip(),
        }
        try:
            self.service.update(row.proveedor_id, payload)
            name = payload["distribuidor_nombre_comercial"] or payload["distribuidor_razon_social"]
            selected_rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
            if selected_rows:
                row_idx = selected_rows[0].row()
                item_name = self.table.item(row_idx, 1)
                if item_name is not None:
                    item_name.setText(name)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Proveedores", f"No se pudo guardar el proveedor.\n{exc}")

    def _new_distributor(self) -> None:
        row = self.service.create({})
        self.reload(selected_id=row.proveedor_id)

    def _delete_distributor(self) -> None:
        row = self._selected_distributor()
        if not row:
            QMessageBox.warning(self, "Proveedores", "Selecciona un proveedor.")
            return
        answer = QMessageBox.question(
            self,
            "Eliminar proveedor",
            f"Eliminar proveedor {row.proveedor_codigo}?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.service.delete(row.proveedor_id)
        self.reload()

    def _import_distributors(self) -> None:
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
                "Importacion de proveedores",
                f"Importados: {imported}\nErrores: {len(errors)}\n\n{preview}{extra}",
            )
            return
        QMessageBox.information(self, "Importacion de proveedores", f"Importados: {imported}")

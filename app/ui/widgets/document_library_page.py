from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHeaderView,
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

from app.services.document_library_service import (
    DocumentLibraryItem,
    DocumentLibraryScanResult,
    DocumentLibraryService,
    DocumentNotFoundError,
    UnsafeDocumentPathError,
)


class DocumentCatalogRefreshWorker(QThread):
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, service: DocumentLibraryService, parent=None) -> None:
        super().__init__(parent)
        self._service = service

    def run(self) -> None:
        try:
            self.result_ready.emit(self._service.refresh_catalog())
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or "Error desconocido al actualizar el catálogo.")


class _SortableTableItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value: object | None = None) -> None:
        super().__init__(text)
        self.setData(Qt.ItemDataRole.UserRole + 1, sort_value if sort_value is not None else text)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(Qt.ItemDataRole.UserRole + 1)
        right = other.data(Qt.ItemDataRole.UserRole + 1)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left < right
        return str(left).casefold() < str(right).casefold()


class DocumentLibraryPage(QWidget):
    def __init__(
        self,
        service: DocumentLibraryService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("documentLibraryPage")
        self._service = service or DocumentLibraryService()
        self._worker: DocumentCatalogRefreshWorker | None = None
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Documentos")
        title.setProperty("role", "pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.library_status_label = QLabel()
        self.library_status_label.setObjectName("documentLibraryAvailability")
        header.addWidget(self.library_status_label)
        layout.addLayout(header)

        filters = QFrame()
        filters.setObjectName("documentLibraryFilters")
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(0, 0, 0, 0)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("documentLibrarySearch")
        self.search_input.setPlaceholderText("Buscar por nombre o ruta...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_filters)
        filters_layout.addWidget(self.search_input, 2)

        self.area_filter = QComboBox()
        self.area_filter.setObjectName("documentLibraryAreaFilter")
        self.area_filter.setMinimumWidth(150)
        self.area_filter.currentIndexChanged.connect(self._area_changed)
        filters_layout.addWidget(self.area_filter)

        self.category_filter = QComboBox()
        self.category_filter.setObjectName("documentLibraryCategoryFilter")
        self.category_filter.setMinimumWidth(170)
        self.category_filter.currentIndexChanged.connect(self._apply_filters)
        filters_layout.addWidget(self.category_filter)

        self.extension_filter = QComboBox()
        self.extension_filter.setObjectName("documentLibraryExtensionFilter")
        self.extension_filter.setMinimumWidth(110)
        self.extension_filter.currentIndexChanged.connect(self._apply_filters)
        filters_layout.addWidget(self.extension_filter)

        self.clear_filters_button = QPushButton("Limpiar filtros")
        self.clear_filters_button.setObjectName("documentLibraryClearFilters")
        self.clear_filters_button.setProperty("btnRole", "secondary")
        self.clear_filters_button.clicked.connect(self._clear_filters)
        filters_layout.addWidget(self.clear_filters_button)

        self.refresh_button = QPushButton("Actualizar catálogo")
        self.refresh_button.setObjectName("documentLibraryRefreshButton")
        self.refresh_button.setProperty("btnRole", "primary")
        self.refresh_button.clicked.connect(self._start_refresh)
        filters_layout.addWidget(self.refresh_button)
        layout.addWidget(filters)

        self.table = QTableWidget(0, 6)
        self.table.setObjectName("documentLibraryTable")
        self.table.setHorizontalHeaderLabels(
            ["Nombre", "Área", "Categoría", "Tipo", "Tamaño", "Modificado"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.itemSelectionChanged.connect(self._sync_open_button)
        self.table.itemDoubleClicked.connect(lambda _item: self._open_selected_document())
        layout.addWidget(self.table, 1)

        self.empty_state_label = QLabel()
        self.empty_state_label.setObjectName("documentLibraryEmptyState")
        self.empty_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state_label.setWordWrap(True)
        layout.addWidget(self.empty_state_label)

        footer = QHBoxLayout()
        self.status_label = QLabel("Catálogo sin cargar.")
        self.status_label.setObjectName("documentLibraryStatus")
        self.status_label.setWordWrap(True)
        footer.addWidget(self.status_label, 1)
        self.counter_label = QLabel("0 documentos")
        self.counter_label.setObjectName("documentLibraryCounter")
        footer.addWidget(self.counter_label)
        self.open_button = QPushButton("Abrir documento")
        self.open_button.setObjectName("documentLibraryOpenButton")
        self.open_button.setProperty("btnRole", "secondary")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_selected_document)
        footer.addWidget(self.open_button)
        layout.addLayout(footer)

    def reload(self) -> None:
        selected_id = self._selected_document_id()
        self._sync_library_status()
        try:
            self._reload_filter_options()
            self._apply_filters(selected_id=selected_id)
            self.status_label.setText("Índice documental cargado.")
        except Exception as exc:  # noqa: BLE001
            self._render_documents([])
            self.status_label.setText(f"No se pudo cargar el catálogo: {exc}")

    def _sync_library_status(self) -> None:
        if self._service.is_library_available():
            self.library_status_label.setText("Biblioteca disponible")
            self.library_status_label.setProperty("status", "ready")
        else:
            self.library_status_label.setText("Biblioteca no disponible")
            self.library_status_label.setProperty("status", "unavailable")
        self.library_status_label.style().unpolish(self.library_status_label)
        self.library_status_label.style().polish(self.library_status_label)

    def _reload_filter_options(self) -> None:
        documents = self._service.list_documents(active=True)
        current_area = self.area_filter.currentData()
        current_extension = self.extension_filter.currentData()
        areas = sorted({item.area for item in documents if item.area}, key=str.casefold)
        extensions = sorted(
            {item.extension for item in documents if item.extension}, key=str.casefold
        )
        self._set_combo_values(self.area_filter, "Todas las áreas", areas, current_area)
        self._set_combo_values(
            self.extension_filter,
            "Todos los tipos",
            extensions,
            current_extension,
            display=lambda value: value.removeprefix(".").upper(),
        )
        self._reload_categories()

    def _reload_categories(self) -> None:
        current_category = self.category_filter.currentData()
        area = self.area_filter.currentData() or None
        documents = self._service.list_documents(area=area, active=True)
        categories = sorted(
            {item.category for item in documents if item.category}, key=str.casefold
        )
        self._set_combo_values(
            self.category_filter,
            "Todas las categorías",
            categories,
            current_category,
        )

    @staticmethod
    def _set_combo_values(
        combo: QComboBox,
        all_label: str,
        values: list[str],
        selected: object,
        *,
        display=lambda value: value,
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(all_label, "")
        for value in values:
            combo.addItem(display(value), value)
        selected_index = combo.findData(selected)
        combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        combo.blockSignals(False)

    def _area_changed(self) -> None:
        self._reload_categories()
        self._apply_filters()

    def _apply_filters(self, *_args, selected_id: str | None = None) -> None:
        if isinstance(selected_id, bool):
            selected_id = None
        if selected_id is None:
            selected_id = self._selected_document_id()
        documents = self._service.list_documents(
            query=self.search_input.text().strip() or None,
            area=self.area_filter.currentData() or None,
            category=self.category_filter.currentData() or None,
            extension=self.extension_filter.currentData() or None,
            active=True,
        )
        self._render_documents(documents, selected_id=selected_id)

    def _render_documents(
        self,
        documents: list[DocumentLibraryItem],
        *,
        selected_id: str | None = None,
    ) -> None:
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(len(documents))
        for row, document in enumerate(documents):
            name_item = _SortableTableItem(document.name)
            name_item.setData(Qt.ItemDataRole.UserRole, document.document_id)
            name_item.setToolTip(document.relative_path)
            values = [
                name_item,
                _SortableTableItem(document.area),
                _SortableTableItem(document.category),
                _SortableTableItem(document.extension.removeprefix(".").upper()),
                _SortableTableItem(self._format_size(document.size_bytes), document.size_bytes),
                _SortableTableItem(
                    self._format_modified_at(document.modified_at), document.modified_at
                ),
            ]
            for column, item in enumerate(values):
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)
        if selected_id:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == selected_id:
                    self.table.selectRow(row)
                    break
        self.counter_label.setText(
            f"{len(documents)} documento" if len(documents) == 1 else f"{len(documents)} documentos"
        )
        has_filters = bool(
            self.search_input.text().strip()
            or self.area_filter.currentData()
            or self.category_filter.currentData()
            or self.extension_filter.currentData()
        )
        if documents:
            self.empty_state_label.clear()
            self.empty_state_label.hide()
        else:
            self.empty_state_label.setText(
                "No hay documentos que coincidan con los filtros."
                if has_filters
                else "El catálogo está vacío. Pulsa «Actualizar catálogo» para crearlo."
            )
            self.empty_state_label.show()
        self._sync_open_button()

    def _clear_filters(self) -> None:
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.area_filter.setCurrentIndex(0)
        self.extension_filter.setCurrentIndex(0)
        self._reload_categories()
        self.category_filter.setCurrentIndex(0)
        self._apply_filters()

    def _start_refresh(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._set_refreshing(True)
        worker = DocumentCatalogRefreshWorker(self._service, self)
        self._worker = worker
        worker.result_ready.connect(self._refresh_succeeded)
        worker.failed.connect(self._refresh_failed)
        worker.finished.connect(lambda: self._finish_refresh(worker))
        try:
            worker.start()
        except Exception as exc:  # noqa: BLE001
            self._refresh_failed(str(exc) or "No se pudo iniciar la actualización.")
            self._finish_refresh(worker)

    def _set_refreshing(self, refreshing: bool) -> None:
        self.refresh_button.setEnabled(not refreshing)
        if refreshing:
            self.status_label.setToolTip("")
            self.status_label.setText("Actualizando catálogo en segundo plano...")

    def _refresh_succeeded(self, result: DocumentLibraryScanResult) -> None:
        self.reload()
        if not result.available:
            self.status_label.setToolTip("\n".join(result.errors))
            message = (
                "La biblioteca documental no está disponible. "
                "El catálogo existente no se modificó."
            )
            if result.errors:
                message += f" Detalle: {result.errors[0]}"
            self.status_label.setText(message)
            return
        summary = (
            f"Actualización completada: {result.added} añadidos, "
            f"{result.updated} actualizados, {result.unchanged} sin cambios y "
            f"{result.deactivated} desactivados."
        )
        if result.errors:
            summary += (
                f" Errores parciales: {len(result.errors)}. "
                f"Primer error: {result.errors[0]}"
            )
            self.status_label.setToolTip("\n".join(result.errors))
        else:
            self.status_label.setToolTip("")
        self.status_label.setText(summary)

    def _refresh_failed(self, message: str) -> None:
        self.status_label.setToolTip("")
        self.status_label.setText(f"No se pudo actualizar el catálogo: {message}")

    def _finish_refresh(self, worker: DocumentCatalogRefreshWorker) -> None:
        self._set_refreshing(False)
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    def _selected_document_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _sync_open_button(self) -> None:
        self.open_button.setEnabled(self._selected_document_id() is not None)

    def _open_selected_document(self) -> None:
        document_id = self._selected_document_id()
        if not document_id:
            return
        try:
            path = self._service.resolve_document(document_id)
        except (DocumentNotFoundError, UnsafeDocumentPathError) as exc:
            QMessageBox.warning(self, "Documentos", str(exc))
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(
                self,
                "Documentos",
                "Windows no pudo abrir el documento con la aplicación predeterminada.",
            )

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        size = float(size_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size_bytes} B"

    @staticmethod
    def _format_modified_at(value: str) -> str:
        try:
            return datetime.fromisoformat(value).astimezone().strftime("%d/%m/%Y %H:%M")
        except (TypeError, ValueError):
            return value

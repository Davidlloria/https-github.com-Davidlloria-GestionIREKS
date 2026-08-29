from __future__ import annotations

from threading import Event

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.document_content_index_service import (
    DocumentContentFTSUnavailableError,
    DocumentContentIndexResult,
    DocumentContentIndexService,
    DocumentContentSearchResult,
)
from app.services.document_library_service import DocumentLibraryService


class DocumentContentIndexWorker(QThread):
    progress = Signal(int, int, str)
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, service: DocumentContentIndexService, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._cancel_requested = Event()

    def request_cancel(self) -> None:
        self._cancel_requested.set()

    def run(self) -> None:
        try:
            result = self._service.update_index(
                progress_callback=self._report_progress,
                cancellation_callback=self._cancel_requested.is_set,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or "Error desconocido al actualizar el índice.")
            return
        self.result_ready.emit(result)

    def _report_progress(self, processed: int, candidates: int, document_id: str) -> None:
        self.progress.emit(processed, candidates, document_id)


class DocumentContentSearchDialog(QDialog):
    document_requested = Signal(str, int)

    def __init__(
        self,
        library_service: DocumentLibraryService | None = None,
        content_service: DocumentContentIndexService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if library_service is None and content_service is not None:
            library_service = content_service.library_service
        self._library_service = library_service or DocumentLibraryService()
        self._content_service = content_service or DocumentContentIndexService(
            self._library_service
        )
        self._worker: DocumentContentIndexWorker | None = None
        self._results: list[DocumentContentSearchResult] = []
        self.setWindowTitle("Buscar en contenido documental")
        self.setObjectName("documentContentSearchDialog")
        self.setModal(True)
        self.resize(980, 650)
        self._build_ui()
        self._load_filters()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        search_frame = QFrame()
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(0, 0, 0, 0)
        self.query_input = QLineEdit()
        self.query_input.setObjectName("documentContentQuery")
        self.query_input.setPlaceholderText("Palabras o frase a buscar...")
        self.query_input.setClearButtonEnabled(True)
        self.query_input.returnPressed.connect(self._search)
        search_layout.addWidget(self.query_input, 2)

        self.area_filter = QComboBox()
        self.area_filter.setObjectName("documentContentAreaFilter")
        self.area_filter.setMinimumWidth(150)
        self.area_filter.currentIndexChanged.connect(self._area_changed)
        search_layout.addWidget(self.area_filter)

        self.category_filter = QComboBox()
        self.category_filter.setObjectName("documentContentCategoryFilter")
        self.category_filter.setMinimumWidth(170)
        search_layout.addWidget(self.category_filter)

        self.search_button = QPushButton("Buscar")
        self.search_button.setObjectName("documentContentSearchButton")
        self.search_button.setProperty("btnRole", "primary")
        self.search_button.clicked.connect(self._search)
        search_layout.addWidget(self.search_button)

        self.clear_button = QPushButton("Limpiar")
        self.clear_button.setObjectName("documentContentClearButton")
        self.clear_button.setProperty("btnRole", "secondary")
        self.clear_button.clicked.connect(self._clear)
        search_layout.addWidget(self.clear_button)
        layout.addWidget(search_frame)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("documentContentResults")
        self.table.setHorizontalHeaderLabels(
            ["Documento", "Área", "Categoría", "Página", "Fragmento"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 210)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 150)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemDoubleClicked.connect(lambda _item: self._show_document())
        layout.addWidget(self.table, 1)

        result_status = QHBoxLayout()
        self.empty_state_label = QLabel("Introduce una consulta para buscar en el índice.")
        self.empty_state_label.setObjectName("documentContentEmptyState")
        self.empty_state_label.setWordWrap(True)
        result_status.addWidget(self.empty_state_label, 1)
        self.counter_label = QLabel("0 resultados")
        self.counter_label.setObjectName("documentContentCounter")
        result_status.addWidget(self.counter_label)
        layout.addLayout(result_status)

        index_row = QHBoxLayout()
        self.index_status_label = QLabel("Índice de contenido listo para consultar.")
        self.index_status_label.setObjectName("documentContentIndexStatus")
        self.index_status_label.setWordWrap(True)
        index_row.addWidget(self.index_status_label, 1)
        self.update_index_button = QPushButton("Actualizar índice de contenido")
        self.update_index_button.setObjectName("documentContentUpdateIndex")
        self.update_index_button.clicked.connect(self._start_index_update)
        index_row.addWidget(self.update_index_button)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setObjectName("documentContentCancelIndex")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_index_update)
        index_row.addWidget(self.cancel_button)
        layout.addLayout(index_row)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.show_document_button = QPushButton("Mostrar documento")
        self.show_document_button.setObjectName("documentContentShowDocument")
        self.show_document_button.setProperty("btnRole", "primary")
        self.show_document_button.setEnabled(False)
        self.show_document_button.clicked.connect(self._show_document)
        actions.addWidget(self.show_document_button)
        self.close_button = QPushButton("Cerrar")
        self.close_button.setObjectName("documentContentClose")
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)

    def _load_filters(self) -> None:
        try:
            documents = self._library_service.list_documents(active=True)
        except Exception as exc:  # noqa: BLE001
            self.index_status_label.setText(f"No se pudo cargar el catálogo: {exc}")
            documents = []
        areas = sorted({item.area for item in documents if item.area}, key=str.casefold)
        self._set_combo_values(self.area_filter, "Todas", areas)
        self._reload_categories()

    def _reload_categories(self) -> None:
        area = self.area_filter.currentData() or None
        try:
            documents = self._library_service.list_documents(area=area, active=True)
        except Exception as exc:  # noqa: BLE001
            self.index_status_label.setText(f"No se pudo cargar el catálogo: {exc}")
            documents = []
        categories = sorted(
            {item.category for item in documents if item.category}, key=str.casefold
        )
        self._set_combo_values(self.category_filter, "Todas", categories)

    @staticmethod
    def _set_combo_values(combo: QComboBox, all_label: str, values: list[str]) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(all_label, "")
        for value in values:
            combo.addItem(value, value)
        combo.blockSignals(False)

    def _area_changed(self) -> None:
        self._reload_categories()

    def _search(self) -> None:
        query = self.query_input.text().strip()
        if not query:
            self._render_results([])
            self.empty_state_label.setText("Introduce una consulta antes de buscar.")
            return
        try:
            results = self._content_service.search(
                query,
                area=self.area_filter.currentData() or None,
                category=self.category_filter.currentData() or None,
                limit=50,
            )
        except DocumentContentFTSUnavailableError:
            self._render_results([])
            self.empty_state_label.setText(
                "La búsqueda de contenido no está disponible porque SQLite no incluye FTS5."
            )
            return
        except Exception as exc:  # noqa: BLE001
            self._render_results([])
            self.empty_state_label.setText(
                f"No se pudo consultar el índice de contenido: {exc}"
            )
            return
        self._render_results(results)

    def _render_results(self, results: list[DocumentContentSearchResult]) -> None:
        self._results = list(results)
        self.table.clearContents()
        self.table.setRowCount(len(results))
        for row, result in enumerate(results):
            name_item = QTableWidgetItem(result.name)
            name_item.setData(Qt.ItemDataRole.UserRole, result.document_id)
            name_item.setData(Qt.ItemDataRole.UserRole + 1, result.page_number)
            values = (
                name_item,
                QTableWidgetItem(result.area),
                QTableWidgetItem(result.category),
                QTableWidgetItem(str(result.page_number)),
                QTableWidgetItem(result.fragment),
            )
            for column, item in enumerate(values):
                self.table.setItem(row, column, item)
        count = len(results)
        self.counter_label.setText(
            f"{count} resultado" if count == 1 else f"{count} resultados"
        )
        self.empty_state_label.setText(
            "" if results else "No hay coincidencias para la consulta y filtros indicados."
        )
        self.empty_state_label.setVisible(not results)
        self._selection_changed()

    def _clear(self) -> None:
        self.query_input.clear()
        self.area_filter.setCurrentIndex(0)
        self._reload_categories()
        self.category_filter.setCurrentIndex(0)
        self._render_results([])
        self.empty_state_label.setText("Introduce una consulta para buscar en el índice.")

    def _selected_result_reference(self) -> tuple[str, int] | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return None
        return (
            str(item.data(Qt.ItemDataRole.UserRole)),
            int(item.data(Qt.ItemDataRole.UserRole + 1)),
        )

    def _selection_changed(self) -> None:
        self.show_document_button.setEnabled(
            self._selected_result_reference() is not None
        )

    def _show_document(self) -> None:
        reference = self._selected_result_reference()
        if reference is None:
            return
        self.document_requested.emit(*reference)
        self.accept()

    def _start_index_update(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._set_indexing(True)
        self.index_status_label.setToolTip("")
        self.index_status_label.setText("Preparando el índice de contenido...")
        worker = DocumentContentIndexWorker(self._content_service, self)
        self._worker = worker
        worker.progress.connect(self._index_progress)
        worker.result_ready.connect(self._index_succeeded)
        worker.failed.connect(self._index_failed)
        worker.finished.connect(lambda: self._finish_index_update(worker))
        try:
            worker.start()
        except Exception as exc:  # noqa: BLE001
            self._index_failed(str(exc) or "No se pudo iniciar la actualización.")
            self._finish_index_update(worker)

    def _set_indexing(self, indexing: bool) -> None:
        self.update_index_button.setEnabled(not indexing)
        self.search_button.setEnabled(not indexing)
        self.query_input.setEnabled(not indexing)
        self.area_filter.setEnabled(not indexing)
        self.category_filter.setEnabled(not indexing)
        self.cancel_button.setEnabled(indexing)
        self.close_button.setEnabled(not indexing)

    def _index_progress(self, processed: int, candidates: int, _document_id: str) -> None:
        self.index_status_label.setText(
            f"Actualizando índice de contenido: {processed} / {candidates}"
        )

    def _cancel_index_update(self) -> None:
        if self._worker is None or not self._worker.isRunning():
            return
        self._worker.request_cancel()
        self.cancel_button.setEnabled(False)
        self.index_status_label.setText("Cancelando al terminar el documento actual...")

    def _index_succeeded(self, result: DocumentContentIndexResult) -> None:
        summary = (
            f"Índice actualizado: {result.candidates} candidatos, "
            f"{result.indexed} indexados, {result.unchanged} sin cambios, "
            f"{result.no_text} sin texto, {result.failed} fallidos y "
            f"{result.cancelled} cancelados."
        )
        self.index_status_label.setText(summary)
        self.index_status_label.setToolTip("\n".join(result.errors))

    def _index_failed(self, message: str) -> None:
        self.index_status_label.setToolTip("")
        self.index_status_label.setText(
            f"No se pudo actualizar el índice de contenido: {message}"
        )

    def _finish_index_update(self, worker: DocumentContentIndexWorker) -> None:
        self._set_indexing(False)
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._cancel_index_update()
            return
        super().reject()

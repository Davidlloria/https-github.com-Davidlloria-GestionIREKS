from __future__ import annotations

import re
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
from app.services.document_semantic_index_service import (
    DocumentSemanticIndexResult,
    DocumentSemanticIndexService,
    DocumentSemanticIndexStatus,
)
from app.services.local_embedding_service import LocalEmbeddingService


_SEMANTIC_PREFLIGHT_TEXT = "Prueba de búsqueda documental de GestionIREKS."
_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?i)(?<![\w])(?:[a-z]:[\\/]|\\\\)[^\s]+|(?<![\w])/(?:[^/\s]+/)+[^\s]+"
)


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


class DocumentSemanticIndexWorker(QThread):
    progress = Signal(int, int, str)
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, service: DocumentSemanticIndexService, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._cancel_requested = Event()

    def request_cancel(self) -> None:
        self._cancel_requested.set()

    def run(self) -> None:
        model = str(self._service.embedding_service.model or "").strip()
        if not model:
            self.failed.emit("No hay un modelo de embeddings configurado.")
            return
        try:
            preflight = self._service.embedding_service.embed(
                [_SEMANTIC_PREFLIGHT_TEXT]
            )
            if not preflight.ok:
                self.failed.emit(
                    f"No se pudo comprobar el modelo '{model}': "
                    f"{preflight.message or 'respuesta de embeddings no válida.'}"
                )
                return
            if self._cancel_requested.is_set():
                self.result_ready.emit(
                    DocumentSemanticIndexResult(cancelled=1)
                )
                return
            result = self._service.update_index(
                progress_callback=self._report_progress,
                cancellation_callback=self._cancel_requested.is_set,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or "Error desconocido al actualizar el índice semántico.")
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
        semantic_service: DocumentSemanticIndexService | None = None,
    ) -> None:
        super().__init__(parent)
        if content_service is None and semantic_service is not None:
            content_service = semantic_service.content_index_service
        if library_service is None and content_service is not None:
            library_service = content_service.library_service
        self._library_service = library_service or DocumentLibraryService()
        self._content_service = content_service or DocumentContentIndexService(
            self._library_service
        )
        self._semantic_service = semantic_service or DocumentSemanticIndexService(
            self._content_service,
            LocalEmbeddingService(),
        )
        self._worker: DocumentContentIndexWorker | DocumentSemanticIndexWorker | None = None
        self._operation_kind: str | None = None
        self._results: list[DocumentContentSearchResult] = []
        self.setWindowTitle("Buscar en contenido documental")
        self.setObjectName("documentContentSearchDialog")
        self.setModal(True)
        self.resize(980, 650)
        self._build_ui()
        self._load_filters()
        self._refresh_semantic_status()

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

        self.content_index_title_label = QLabel("1. Actualizar índice de contenido")
        self.content_index_title_label.setObjectName("documentContentIndexTitle")
        self.content_index_title_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.content_index_title_label)

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

        self.semantic_index_title_label = QLabel("2. Actualizar índice semántico")
        self.semantic_index_title_label.setObjectName("documentSemanticIndexTitle")
        self.semantic_index_title_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.semantic_index_title_label)

        semantic_status_row = QHBoxLayout()
        self.semantic_status_label = QLabel()
        self.semantic_status_label.setObjectName("documentSemanticIndexStatus")
        self.semantic_status_label.setWordWrap(True)
        semantic_status_row.addWidget(self.semantic_status_label, 1)
        self.semantic_model_label = QLabel()
        self.semantic_model_label.setObjectName("documentSemanticIndexModel")
        semantic_status_row.addWidget(self.semantic_model_label)
        layout.addLayout(semantic_status_row)

        semantic_action_row = QHBoxLayout()
        self.semantic_progress_label = QLabel("")
        self.semantic_progress_label.setObjectName("documentSemanticIndexProgress")
        self.semantic_progress_label.setWordWrap(True)
        semantic_action_row.addWidget(self.semantic_progress_label, 1)
        self.update_semantic_index_button = QPushButton(
            "Actualizar índice semántico"
        )
        self.update_semantic_index_button.setObjectName(
            "documentSemanticUpdateIndex"
        )
        self.update_semantic_index_button.clicked.connect(
            self._start_semantic_index_update
        )
        semantic_action_row.addWidget(self.update_semantic_index_button)
        self.semantic_cancel_button = QPushButton("Cancelar")
        self.semantic_cancel_button.setObjectName("documentSemanticCancelIndex")
        self.semantic_cancel_button.setEnabled(False)
        self.semantic_cancel_button.clicked.connect(
            self._cancel_semantic_index_update
        )
        semantic_action_row.addWidget(self.semantic_cancel_button)
        layout.addLayout(semantic_action_row)

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
        self._operation_kind = "content"
        self._set_indexing(True, "content")
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

    def _set_indexing(self, indexing: bool, kind: str = "content") -> None:
        self.update_index_button.setEnabled(not indexing)
        self.update_semantic_index_button.setEnabled(not indexing)
        self.search_button.setEnabled(not indexing)
        self.query_input.setEnabled(not indexing)
        self.area_filter.setEnabled(not indexing)
        self.category_filter.setEnabled(not indexing)
        self.cancel_button.setEnabled(indexing and kind == "content")
        self.semantic_cancel_button.setEnabled(indexing and kind == "semantic")
        self.close_button.setEnabled(not indexing)

    def _index_progress(self, processed: int, candidates: int, _document_id: str) -> None:
        self.index_status_label.setText(
            f"Actualizando índice de contenido: {processed} / {candidates}"
        )

    def _cancel_index_update(self) -> None:
        if (
            self._worker is None
            or not self._worker.isRunning()
            or self._operation_kind != "content"
        ):
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
        self._refresh_semantic_status()

    def _index_failed(self, message: str) -> None:
        self.index_status_label.setToolTip("")
        self.index_status_label.setText(
            f"No se pudo actualizar el índice de contenido: {message}"
        )

    def _finish_index_update(self, worker: DocumentContentIndexWorker) -> None:
        self._set_indexing(False)
        if self._worker is worker:
            self._worker = None
            self._operation_kind = None
        worker.deleteLater()

    def _refresh_semantic_status(self) -> None:
        try:
            status = self._semantic_service.get_status()
        except Exception:  # noqa: BLE001
            model = str(
                getattr(self._semantic_service.embedding_service, "model", "") or ""
            )
            self.semantic_model_label.setText(f"Modelo: {model or '—'}")
            self.semantic_status_label.setText(
                "No se pudo consultar el estado del índice semántico."
            )
            return
        self.semantic_model_label.setText(
            f"Modelo: {status.configured_model or '—'}"
        )
        self.semantic_status_label.setText(self._semantic_status_text(status))

    @staticmethod
    def _semantic_status_text(status: DocumentSemanticIndexStatus) -> str:
        model = status.configured_model or "modelo configurado"
        if status.content_documents == 0:
            return (
                "No hay contenido indexado para generar embeddings. "
                "Actualiza primero el índice de contenido."
            )
        if status.other_model_documents > 0:
            return (
                "El índice fue creado con otro modelo. "
                f"Es necesario actualizarlo para {model}."
            )
        if status.available and status.failed_documents > 0:
            return (
                "Índice semántico disponible con "
                f"{status.failed_documents} documentos fallidos."
            )
        if status.available:
            return (
                "Índice semántico disponible: "
                f"{status.indexed_documents} documentos y "
                f"{status.available_chunks} fragmentos · modelo {model}."
            )
        return f"Índice semántico pendiente para el modelo {model}."

    def _start_semantic_index_update(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        model = str(self._semantic_service.embedding_service.model or "").strip()
        self._operation_kind = "semantic"
        self._set_indexing(True, "semantic")
        self.semantic_progress_label.setToolTip("")
        self.semantic_progress_label.setText(
            f"Comprobando el modelo de embeddings {model or 'configurado'}..."
        )
        worker = DocumentSemanticIndexWorker(self._semantic_service, self)
        self._worker = worker
        worker.progress.connect(self._semantic_index_progress)
        worker.result_ready.connect(self._semantic_index_succeeded)
        worker.failed.connect(self._semantic_index_failed)
        worker.finished.connect(lambda: self._finish_semantic_index_update(worker))
        try:
            worker.start()
        except Exception as exc:  # noqa: BLE001
            self._semantic_index_failed(
                str(exc) or "No se pudo iniciar la actualización semántica."
            )
            self._finish_semantic_index_update(worker)

    def _semantic_index_progress(
        self,
        processed: int,
        candidates: int,
        _document_id: str,
    ) -> None:
        model = str(self._semantic_service.embedding_service.model or "").strip()
        self.semantic_progress_label.setText(
            "Actualizando índice semántico: "
            f"{processed} / {candidates} · modelo {model or 'configurado'}"
        )

    def _cancel_semantic_index_update(self) -> None:
        if (
            self._worker is None
            or not self._worker.isRunning()
            or self._operation_kind != "semantic"
        ):
            return
        self._worker.request_cancel()
        self.semantic_cancel_button.setEnabled(False)
        self.semantic_progress_label.setText(
            "Cancelando al terminar el documento o lote actual..."
        )

    def _semantic_index_succeeded(
        self,
        result: DocumentSemanticIndexResult,
    ) -> None:
        model = str(self._semantic_service.embedding_service.model or "").strip()
        self.semantic_progress_label.setText(
            f"Índice semántico: {result.candidates} candidatos, "
            f"{result.indexed} indexados, {result.unchanged} sin cambios, "
            f"{result.failed} fallidos, {result.cancelled} cancelados y "
            f"{result.chunks_generated} fragmentos generados · modelo {model}."
        )
        safe_errors = [self._safe_message(error) for error in result.errors]
        self.semantic_progress_label.setToolTip("\n".join(safe_errors))
        self._refresh_semantic_status()

    def _semantic_index_failed(self, message: str) -> None:
        self.semantic_progress_label.setToolTip("")
        self.semantic_progress_label.setText(
            "No se pudo actualizar el índice semántico: "
            f"{self._safe_message(message)}"
        )
        self._refresh_semantic_status()

    def _finish_semantic_index_update(
        self,
        worker: DocumentSemanticIndexWorker,
    ) -> None:
        self._set_indexing(False)
        if self._worker is worker:
            self._worker = None
            self._operation_kind = None
        worker.deleteLater()

    @staticmethod
    def _safe_message(message: str) -> str:
        return _ABSOLUTE_PATH_PATTERN.sub("[RUTA OMITIDA]", str(message or ""))

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            if self._operation_kind == "semantic":
                self._cancel_semantic_index_update()
            else:
                self._cancel_index_update()
            return
        super().reject()

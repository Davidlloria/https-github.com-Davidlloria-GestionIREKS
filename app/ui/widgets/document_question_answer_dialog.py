from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.document_content_index_service import DocumentContentIndexService
from app.services.document_library_service import DocumentLibraryService
from app.services.document_question_answer_service import (
    MAX_QUESTION_CHARS,
    DocumentQuestionAnswerResult,
    DocumentQuestionAnswerService,
)


class DocumentQuestionAnswerWorker(QThread):
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: DocumentQuestionAnswerService,
        question: str,
        area: str | None,
        category: str | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._question = question
        self._area = area
        self._category = category

    def run(self) -> None:
        try:
            result = self._service.answer(
                self._question,
                area=self._area,
                category=self._category,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or "Error desconocido durante la consulta.")
            return
        self.result_ready.emit(result)


class DocumentQuestionAnswerDialog(QDialog):
    source_requested = Signal(str, int)

    def __init__(
        self,
        library_service: DocumentLibraryService | None = None,
        question_answer_service: DocumentQuestionAnswerService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if library_service is None and question_answer_service is not None:
            library_service = (
                question_answer_service.content_index_service.library_service
            )
        self._library_service = library_service or DocumentLibraryService()
        if question_answer_service is None:
            content_service = DocumentContentIndexService(self._library_service)
            question_answer_service = DocumentQuestionAnswerService(content_service)
        self._question_answer_service = question_answer_service
        self._worker: DocumentQuestionAnswerWorker | None = None
        self.setWindowTitle("Preguntar a la IA documental")
        self.setObjectName("documentQuestionAnswerDialog")
        self.setModal(True)
        self.resize(980, 720)
        self._build_ui()
        self._load_filters()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Preguntar a la IA sobre los documentos")
        title.setProperty("role", "pageTitle")
        layout.addWidget(title)

        question_frame = QFrame()
        question_layout = QVBoxLayout(question_frame)
        question_layout.setContentsMargins(0, 0, 0, 0)
        self.question_input = QPlainTextEdit()
        self.question_input.setObjectName("documentQuestionInput")
        self.question_input.setPlaceholderText(
            "Escribe una pregunta basada en la biblioteca documental..."
        )
        self.question_input.setMaximumHeight(120)
        self.question_input.textChanged.connect(self._question_changed)
        question_layout.addWidget(self.question_input)
        self.question_counter_label = QLabel(f"0 / {MAX_QUESTION_CHARS}")
        self.question_counter_label.setObjectName("documentQuestionCounter")
        self.question_counter_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        question_layout.addWidget(self.question_counter_label)
        layout.addWidget(question_frame)

        filters = QHBoxLayout()
        self.area_filter = QComboBox()
        self.area_filter.setObjectName("documentQuestionAreaFilter")
        self.area_filter.setMinimumWidth(160)
        self.area_filter.currentIndexChanged.connect(self._area_changed)
        filters.addWidget(self.area_filter)
        self.category_filter = QComboBox()
        self.category_filter.setObjectName("documentQuestionCategoryFilter")
        self.category_filter.setMinimumWidth(180)
        filters.addWidget(self.category_filter)
        filters.addStretch(1)
        self.ask_button = QPushButton("Preguntar")
        self.ask_button.setObjectName("documentQuestionAsk")
        self.ask_button.setProperty("btnRole", "primary")
        self.ask_button.clicked.connect(self._start_question)
        filters.addWidget(self.ask_button)
        self.clear_button = QPushButton("Limpiar")
        self.clear_button.setObjectName("documentQuestionClear")
        self.clear_button.setProperty("btnRole", "secondary")
        self.clear_button.clicked.connect(self._clear)
        filters.addWidget(self.clear_button)
        layout.addLayout(filters)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Escribe una pregunta para consultar el índice documental.")
        self.status_label.setObjectName("documentQuestionStatus")
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.status_label, 1)
        self.ai_indicator_label = QLabel("")
        self.ai_indicator_label.setObjectName("documentQuestionAIIndicator")
        status_row.addWidget(self.ai_indicator_label)
        layout.addLayout(status_row)

        self.answer_output = QPlainTextEdit()
        self.answer_output.setObjectName("documentQuestionAnswer")
        self.answer_output.setReadOnly(True)
        self.answer_output.setPlaceholderText("La respuesta aparecerá aquí.")
        self.answer_output.setMinimumHeight(140)
        layout.addWidget(self.answer_output)

        sources_title = QLabel("Fuentes verificadas")
        sources_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(sources_title)

        self.sources_table = QTableWidget(0, 6)
        self.sources_table.setObjectName("documentQuestionSources")
        self.sources_table.setHorizontalHeaderLabels(
            ["Fuente", "Documento", "Área", "Categoría", "Página", "Fragmento"]
        )
        self.sources_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.sources_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.sources_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.sources_table.setAlternatingRowColors(True)
        self.sources_table.verticalHeader().setVisible(False)
        header = self.sources_table.horizontalHeader()
        for column in range(5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.sources_table.setColumnWidth(0, 70)
        self.sources_table.setColumnWidth(1, 200)
        self.sources_table.setColumnWidth(2, 120)
        self.sources_table.setColumnWidth(3, 150)
        self.sources_table.setColumnWidth(4, 70)
        self.sources_table.itemSelectionChanged.connect(self._selection_changed)
        self.sources_table.itemDoubleClicked.connect(
            lambda _item: self._show_source()
        )
        layout.addWidget(self.sources_table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.show_source_button = QPushButton("Mostrar fuente")
        self.show_source_button.setObjectName("documentQuestionShowSource")
        self.show_source_button.setEnabled(False)
        self.show_source_button.clicked.connect(self._show_source)
        actions.addWidget(self.show_source_button)
        self.close_button = QPushButton("Cerrar")
        self.close_button.setObjectName("documentQuestionClose")
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)

    def _load_filters(self) -> None:
        try:
            documents = self._library_service.list_documents(active=True)
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"No se pudo cargar el catálogo: {exc}")
            documents = []
        areas = sorted({item.area for item in documents if item.area}, key=str.casefold)
        self._set_combo_values(self.area_filter, areas)
        self._reload_categories()

    def _reload_categories(self) -> None:
        area = self.area_filter.currentData() or None
        try:
            documents = self._library_service.list_documents(area=area, active=True)
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"No se pudo cargar el catálogo: {exc}")
            documents = []
        categories = sorted(
            {item.category for item in documents if item.category}, key=str.casefold
        )
        self._set_combo_values(self.category_filter, categories)

    @staticmethod
    def _set_combo_values(combo: QComboBox, values: list[str]) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Todas", "")
        for value in values:
            combo.addItem(value, value)
        combo.blockSignals(False)

    def _area_changed(self) -> None:
        self._reload_categories()

    def _question_changed(self) -> None:
        length = len(self.question_input.toPlainText())
        self.question_counter_label.setText(f"{length} / {MAX_QUESTION_CHARS}")
        self.question_counter_label.setProperty(
            "status", "error" if length > MAX_QUESTION_CHARS else "ready"
        )
        self.question_counter_label.style().unpolish(self.question_counter_label)
        self.question_counter_label.style().polish(self.question_counter_label)

    def _start_question(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        question = self.question_input.toPlainText().strip()
        if not question:
            self.status_label.setText("Escribe una pregunta antes de consultar.")
            return
        if len(question) > MAX_QUESTION_CHARS:
            self.status_label.setText(
                f"La pregunta no puede superar {MAX_QUESTION_CHARS} caracteres."
            )
            return
        self._clear_result()
        self._set_querying(True)
        self.status_label.setText("Consultando el índice y la IA local...")
        worker = DocumentQuestionAnswerWorker(
            self._question_answer_service,
            question,
            self.area_filter.currentData() or None,
            self.category_filter.currentData() or None,
            self,
        )
        self._worker = worker
        worker.result_ready.connect(self._question_succeeded)
        worker.failed.connect(self._question_failed)
        worker.finished.connect(lambda: self._finish_question(worker))
        try:
            worker.start()
        except Exception as exc:  # noqa: BLE001
            self._question_failed(str(exc) or "No se pudo iniciar la consulta.")
            self._finish_question(worker)

    def _set_querying(self, querying: bool) -> None:
        self.question_input.setEnabled(not querying)
        self.area_filter.setEnabled(not querying)
        self.category_filter.setEnabled(not querying)
        self.ask_button.setEnabled(not querying)
        self.clear_button.setEnabled(not querying)
        self.close_button.setEnabled(not querying)

    def _question_succeeded(self, result: DocumentQuestionAnswerResult) -> None:
        self._clear_result()
        if not result.ok:
            self.status_label.setText(result.message)
            return
        self.answer_output.setPlainText(result.answer)
        self._render_sources(result)
        if result.used_ai:
            self.status_label.setText(
                "Respuesta generada con IA local y fuentes verificadas"
            )
            self.ai_indicator_label.setText("IA local · fuentes verificadas")
            self.ai_indicator_label.setProperty("status", "ready")
        else:
            self.status_label.setText(
                f"{result.message} Comprueba o actualiza el índice de contenido."
            )
            self.ai_indicator_label.setText("Sin uso de IA local")
            self.ai_indicator_label.setProperty("status", "neutral")
        self.ai_indicator_label.style().unpolish(self.ai_indicator_label)
        self.ai_indicator_label.style().polish(self.ai_indicator_label)

    def _question_failed(self, message: str) -> None:
        self._clear_result()
        self.status_label.setText(f"No se pudo completar la consulta: {message}")

    def _finish_question(self, worker: DocumentQuestionAnswerWorker) -> None:
        self._set_querying(False)
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    def _render_sources(self, result: DocumentQuestionAnswerResult) -> None:
        self.sources_table.clearContents()
        self.sources_table.setRowCount(len(result.sources))
        for row, source in enumerate(result.sources):
            source_item = QTableWidgetItem(source.source_id)
            source_item.setData(Qt.ItemDataRole.UserRole, source.document_id)
            source_item.setData(Qt.ItemDataRole.UserRole + 1, source.page_number)
            values = (
                source_item,
                QTableWidgetItem(source.name),
                QTableWidgetItem(source.area),
                QTableWidgetItem(source.category),
                QTableWidgetItem(str(source.page_number)),
                QTableWidgetItem(source.fragment),
            )
            for column, item in enumerate(values):
                self.sources_table.setItem(row, column, item)
        self._selection_changed()

    def _clear_result(self) -> None:
        self.answer_output.clear()
        self.sources_table.clearContents()
        self.sources_table.setRowCount(0)
        self.ai_indicator_label.clear()
        self.show_source_button.setEnabled(False)

    def _clear(self) -> None:
        self.question_input.clear()
        self.area_filter.setCurrentIndex(0)
        self._reload_categories()
        self.category_filter.setCurrentIndex(0)
        self._clear_result()
        self.status_label.setText("Escribe una pregunta para consultar el índice documental.")

    def _selected_source_reference(self) -> tuple[str, int] | None:
        rows = self.sources_table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.sources_table.item(rows[0].row(), 0)
        if item is None:
            return None
        return (
            str(item.data(Qt.ItemDataRole.UserRole)),
            int(item.data(Qt.ItemDataRole.UserRole + 1)),
        )

    def _selection_changed(self) -> None:
        self.show_source_button.setEnabled(
            self._selected_source_reference() is not None
        )

    def _show_source(self) -> None:
        reference = self._selected_source_reference()
        if reference is None:
            return
        self.source_requested.emit(*reference)
        self.accept()

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.status_label.setText(
                "La consulta está en curso. Espera a que finalice antes de cerrar."
            )
            return
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker is not None and self._worker.isRunning():
            self.status_label.setText(
                "La consulta está en curso. Espera a que finalice antes de cerrar."
            )
            event.ignore()
            return
        super().closeEvent(event)

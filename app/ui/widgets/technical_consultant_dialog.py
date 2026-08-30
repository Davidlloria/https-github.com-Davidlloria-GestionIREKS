from __future__ import annotations

import re

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.technical_consultant_service import (
    TechnicalConsultantResult,
    TechnicalConsultantService,
)


MAX_TECHNICAL_QUESTION_CHARS = 1_000
_STATUS_LABELS = {
    "recommended": "Recomendado",
    "complementary": "Complementario",
}
_RETRIEVAL_MODE_LABELS = {
    "hybrid": "Búsqueda híbrida",
    "lexical": "Búsqueda léxica",
    "semantic": "Búsqueda semántica",
    "none": "Sin recuperación",
}
_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?i)(?<![\w])(?:[a-z]:[\\/]|\\\\)[^\s]+|(?<![\w])/(?:[^/\s]+/)+[^\s]+"
)


class TechnicalConsultantWorker(QThread):
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: TechnicalConsultantService,
        question: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._question = question

    def run(self) -> None:
        try:
            result = self._service.consult(self._question)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or "Error desconocido durante la consulta.")
            return
        self.result_ready.emit(result)


class TechnicalConsultantDialog(QDialog):
    source_requested = Signal(str, int)

    def __init__(
        self,
        consultant_service: TechnicalConsultantService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._consultant_service = consultant_service
        self._worker: TechnicalConsultantWorker | None = None
        self._consultation_parts: list[str] = []
        self._submitted_parts: tuple[str, ...] = ()
        self.setWindowTitle("Consultor técnico de panadería")
        self.setObjectName("technicalConsultantDialog")
        self.setModal(True)
        self.resize(1_080, 780)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Consultor técnico de panadería")
        title.setProperty("role", "pageTitle")
        layout.addWidget(title)

        description = QLabel(
            "Describe el producto, el proceso y el resultado técnico que necesitas. "
            "Las recomendaciones se limitan a las fichas técnicas verificadas."
        )
        description.setObjectName("technicalConsultantDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.context_label = QLabel("")
        self.context_label.setObjectName("technicalConsultantContext")
        self.context_label.setWordWrap(True)
        self.context_label.setVisible(False)
        layout.addWidget(self.context_label)

        self.question_input = QPlainTextEdit()
        self.question_input.setObjectName("technicalConsultantQuestion")
        self.question_input.setPlaceholderText(
            "Ejemplo: necesito un producto para elaborar pan precocinado y después congelado."
        )
        self.question_input.setMaximumHeight(110)
        self.question_input.textChanged.connect(self._question_changed)
        layout.addWidget(self.question_input)

        question_actions = QHBoxLayout()
        self.question_counter_label = QLabel(f"0 / {MAX_TECHNICAL_QUESTION_CHARS}")
        self.question_counter_label.setObjectName("technicalConsultantCounter")
        question_actions.addWidget(self.question_counter_label)
        question_actions.addStretch(1)
        self.ask_button = QPushButton("Consultar")
        self.ask_button.setObjectName("technicalConsultantAsk")
        self.ask_button.setProperty("btnRole", "primary")
        self.ask_button.clicked.connect(self._start_question)
        question_actions.addWidget(self.ask_button)
        self.clear_button = QPushButton("Limpiar")
        self.clear_button.setObjectName("technicalConsultantClear")
        self.clear_button.setProperty("btnRole", "secondary")
        self.clear_button.clicked.connect(self._clear)
        question_actions.addWidget(self.clear_button)
        layout.addLayout(question_actions)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Escribe una necesidad técnica para comenzar.")
        self.status_label.setObjectName("technicalConsultantStatus")
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.status_label, 1)
        self.ai_indicator_label = QLabel("")
        self.ai_indicator_label.setObjectName("technicalConsultantAIIndicator")
        status_row.addWidget(self.ai_indicator_label)
        self.retrieval_mode_label = QLabel("Sin recuperación")
        self.retrieval_mode_label.setObjectName("technicalConsultantRetrievalMode")
        status_row.addWidget(self.retrieval_mode_label)
        layout.addLayout(status_row)

        answer_title = QLabel("Respuesta técnica")
        answer_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(answer_title)
        self.answer_output = QPlainTextEdit()
        self.answer_output.setObjectName("technicalConsultantAnswer")
        self.answer_output.setReadOnly(True)
        self.answer_output.setPlaceholderText("La respuesta aparecerá aquí.")
        self.answer_output.setMinimumHeight(100)
        layout.addWidget(self.answer_output)

        self.clarification_title = QLabel("Información necesaria")
        self.clarification_title.setStyleSheet("font-weight: 600;")
        self.clarification_title.setVisible(False)
        layout.addWidget(self.clarification_title)
        self.clarification_list = QListWidget()
        self.clarification_list.setObjectName("technicalConsultantClarifications")
        self.clarification_list.setMaximumHeight(110)
        self.clarification_list.setVisible(False)
        layout.addWidget(self.clarification_list)

        products_title = QLabel("Productos con respaldo documental")
        products_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(products_title)
        self.products_table = QTableWidget(0, 5)
        self.products_table.setObjectName("technicalConsultantProducts")
        self.products_table.setHorizontalHeaderLabels(
            ["Estado", "Producto", "Aplicación documentada", "Dosificación", "Motivo"]
        )
        self.products_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.products_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.products_table.setAlternatingRowColors(True)
        self.products_table.verticalHeader().setVisible(False)
        product_header = self.products_table.horizontalHeader()
        product_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        product_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        product_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        product_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        product_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.products_table, 1)

        sources_title = QLabel("Fuentes verificadas")
        sources_title.setStyleSheet("font-weight: 600;")
        layout.addWidget(sources_title)
        self.sources_table = QTableWidget(0, 4)
        self.sources_table.setObjectName("technicalConsultantSources")
        self.sources_table.setHorizontalHeaderLabels(
            ["Fuente", "Producto", "Documento", "Página"]
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
        source_header = self.sources_table.horizontalHeader()
        source_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        source_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        source_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        source_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.sources_table.itemSelectionChanged.connect(self._selection_changed)
        self.sources_table.itemDoubleClicked.connect(lambda _item: self._show_source())
        layout.addWidget(self.sources_table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.show_source_button = QPushButton("Mostrar fuente")
        self.show_source_button.setObjectName("technicalConsultantShowSource")
        self.show_source_button.setEnabled(False)
        self.show_source_button.clicked.connect(self._show_source)
        actions.addWidget(self.show_source_button)
        self.close_button = QPushButton("Cerrar")
        self.close_button.setObjectName("technicalConsultantClose")
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)

    def _question_changed(self) -> None:
        length = len(self.question_input.toPlainText())
        self.question_counter_label.setText(
            f"{length} / {MAX_TECHNICAL_QUESTION_CHARS}"
        )
        self.question_counter_label.setProperty(
            "status",
            "error" if length > MAX_TECHNICAL_QUESTION_CHARS else "ready",
        )
        self.question_counter_label.style().unpolish(self.question_counter_label)
        self.question_counter_label.style().polish(self.question_counter_label)

    def _start_question(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        question = self.question_input.toPlainText().strip()
        if not question:
            self.status_label.setText("Escribe una necesidad técnica antes de consultar.")
            return
        if len(question) > MAX_TECHNICAL_QUESTION_CHARS:
            self.status_label.setText(
                "La consulta no puede superar "
                f"{MAX_TECHNICAL_QUESTION_CHARS} caracteres."
            )
            return
        submitted_parts = (*self._consultation_parts, question)
        composed_question = self._compose_question(submitted_parts)
        if len(composed_question) > MAX_TECHNICAL_QUESTION_CHARS:
            self.status_label.setText(
                "La consulta acumulada no puede superar "
                f"{MAX_TECHNICAL_QUESTION_CHARS} caracteres."
            )
            return
        self._submitted_parts = submitted_parts
        self._clear_result()
        self._set_querying(True)
        self.status_label.setText(
            "Consultando fichas técnicas y preparando la respuesta..."
        )
        worker = TechnicalConsultantWorker(
            self._consultant_service,
            composed_question,
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
        self.ask_button.setEnabled(not querying)
        self.clear_button.setEnabled(not querying)
        self.close_button.setEnabled(not querying)

    def _question_succeeded(self, result: TechnicalConsultantResult) -> None:
        self._clear_result()
        mode_label = _RETRIEVAL_MODE_LABELS.get(
            str(result.retrieval_mode or "none"),
            "Sin recuperación",
        )
        self.retrieval_mode_label.setText(mode_label)
        safe_warnings = tuple(self._safe_message(item) for item in result.warnings)
        self.retrieval_mode_label.setToolTip("\n".join(safe_warnings))
        if not result.ok:
            self.status_label.setText(result.message)
            return

        self.answer_output.setPlainText(result.answer)
        self._render_clarifications(result)
        self._render_products(result)
        self._render_sources(result)
        if result.needs_clarification:
            self._continue_consultation()
            self.ai_indicator_label.setText("Pendiente de aclaración")
            self.ai_indicator_label.setProperty("status", "neutral")
        elif result.used_ai:
            self._finish_consultation_context()
            self.ai_indicator_label.setText("IA local · datos verificados")
            self.ai_indicator_label.setProperty("status", "ready")
        else:
            self._finish_consultation_context()
            self.ai_indicator_label.setText("Respuesta determinista")
            self.ai_indicator_label.setProperty("status", "neutral")
        status = f"{result.message} · {mode_label}"
        if safe_warnings:
            status += "\nLa consulta utilizó un mecanismo seguro de respaldo."
        self.status_label.setText(status)
        self.ai_indicator_label.style().unpolish(self.ai_indicator_label)
        self.ai_indicator_label.style().polish(self.ai_indicator_label)

    def _render_clarifications(self, result: TechnicalConsultantResult) -> None:
        self.clarification_list.addItems(list(result.clarification_questions))
        visible = bool(result.clarification_questions)
        self.clarification_title.setVisible(visible)
        self.clarification_list.setVisible(visible)

    def _continue_consultation(self) -> None:
        self._consultation_parts = list(self._submitted_parts)
        if not self._consultation_parts:
            return
        original = self._consultation_parts[0]
        additions = max(0, len(self._consultation_parts) - 1)
        suffix = (
            f" · {additions} aclaración aportada"
            if additions == 1
            else f" · {additions} aclaraciones aportadas"
            if additions > 1
            else ""
        )
        self.context_label.setText(f"Consulta inicial: {original}{suffix}")
        self.context_label.setVisible(True)
        self.question_input.clear()
        self.question_input.setPlaceholderText(
            "Responde aquí a las preguntas de aclaración..."
        )
        self.ask_button.setText("Continuar consulta")

    def _finish_consultation_context(self) -> None:
        self._consultation_parts.clear()
        self._submitted_parts = ()
        self.context_label.clear()
        self.context_label.setVisible(False)
        self.question_input.setPlaceholderText(
            "Ejemplo: necesito un producto para elaborar pan precocinado y después congelado."
        )
        self.ask_button.setText("Consultar")

    @staticmethod
    def _compose_question(parts: tuple[str, ...]) -> str:
        if not parts:
            return ""
        return "\nInformación adicional: ".join(parts)

    def _render_products(self, result: TechnicalConsultantResult) -> None:
        self.products_table.setRowCount(len(result.products))
        for row, product in enumerate(result.products):
            values = (
                _STATUS_LABELS.get(product.status, product.status),
                product.product_name,
                product.application or "No disponible",
                product.dosage or "No documentada",
                product.reason,
            )
            for column, value in enumerate(values):
                self.products_table.setItem(row, column, QTableWidgetItem(value))
        self.products_table.resizeRowsToContents()

    def _render_sources(self, result: TechnicalConsultantResult) -> None:
        product_by_source = {
            source_id: product.product_name
            for product in result.products
            for source_id in product.source_ids
        }
        self.sources_table.setRowCount(len(result.sources))
        for row, source in enumerate(result.sources):
            source_item = QTableWidgetItem(source.source_id)
            source_item.setData(Qt.ItemDataRole.UserRole, source.document_id)
            source_item.setData(Qt.ItemDataRole.UserRole + 1, source.page_number)
            values = (
                source_item,
                QTableWidgetItem(product_by_source.get(source.source_id, "")),
                QTableWidgetItem(source.name),
                QTableWidgetItem(str(source.page_number)),
            )
            for column, item in enumerate(values):
                self.sources_table.setItem(row, column, item)
        self._selection_changed()

    def _question_failed(self, message: str) -> None:
        self._clear_result()
        self.status_label.setText(
            f"No se pudo completar la consulta: {self._safe_message(message)}"
        )

    def _finish_question(self, worker: TechnicalConsultantWorker) -> None:
        self._set_querying(False)
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    def _clear_result(self) -> None:
        self.answer_output.clear()
        self.clarification_list.clear()
        self.clarification_title.setVisible(False)
        self.clarification_list.setVisible(False)
        self.products_table.clearContents()
        self.products_table.setRowCount(0)
        self.sources_table.clearContents()
        self.sources_table.setRowCount(0)
        self.ai_indicator_label.clear()
        self.retrieval_mode_label.setText("Sin recuperación")
        self.retrieval_mode_label.setToolTip("")
        self.show_source_button.setEnabled(False)

    def _clear(self) -> None:
        self.question_input.clear()
        self._finish_consultation_context()
        self._clear_result()
        self.status_label.setText("Escribe una necesidad técnica para comenzar.")

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

    @staticmethod
    def _safe_message(message: str) -> str:
        return _ABSOLUTE_PATH_PATTERN.sub("[RUTA OMITIDA]", str(message or ""))

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

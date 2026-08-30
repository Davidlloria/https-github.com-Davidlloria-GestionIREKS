from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.document_catalog_refresh_service import DocumentCatalogRefreshService
from app.services.document_content_index_service import DocumentContentIndexService
from app.services.document_hybrid_retrieval_service import (
    DocumentHybridRetrievalService,
)
from app.services.document_library_service import (
    DocumentLibraryItem,
    DocumentLibraryScanResult,
    DocumentLibraryService,
    DocumentNotFoundError,
    UnsafeDocumentPathError,
)
from app.services.document_question_answer_service import DocumentQuestionAnswerService
from app.services.document_product_link_service import DocumentProductLinkService
from app.services.document_semantic_index_service import DocumentSemanticIndexService
from app.services.local_embedding_service import LocalEmbeddingService
from app.services.technical_consultant_service import TechnicalConsultantService
from app.services.technical_product_comparison_service import (
    TechnicalProductComparisonService,
)
from app.services.technical_product_decision_service import (
    TechnicalProductDecisionService,
)
from app.services.technical_product_retrieval_service import (
    TechnicalProductRetrievalService,
)
from app.services.whatsapp_share_service import WhatsAppShareService
from app.ui.widgets.document_content_search_dialog import DocumentContentSearchDialog
from app.ui.widgets.document_question_answer_dialog import DocumentQuestionAnswerDialog
from app.ui.widgets.technical_consultant_dialog import TechnicalConsultantDialog
from app.ui.widgets.whatsapp_share_dialog import WhatsAppShareDialog


class DocumentCatalogRefreshWorker(QThread):
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, service: DocumentCatalogRefreshService, parent=None) -> None:
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
        content_index_service: DocumentContentIndexService | None = None,
        question_answer_service: DocumentQuestionAnswerService | None = None,
        parent=None,
        semantic_index_service: DocumentSemanticIndexService | None = None,
        technical_consultant_service: TechnicalConsultantService | None = None,
        whatsapp_share_service: WhatsAppShareService | None = None,
        product_link_service: DocumentProductLinkService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("documentLibraryPage")
        if content_index_service is None and semantic_index_service is not None:
            content_index_service = semantic_index_service.content_index_service
        if content_index_service is None:
            content_index_service = getattr(
                question_answer_service, "content_index_service", None
            )
        if service is None and content_index_service is not None:
            service = content_index_service.library_service
        self._service = service or DocumentLibraryService()
        self._product_link_service = product_link_service or DocumentProductLinkService(
            document_database_path=getattr(self._service, "database_path", None)
        )
        self._catalog_refresh_service = DocumentCatalogRefreshService(
            self._service,
            self._product_link_service,
        )
        self._content_index_service = content_index_service or getattr(
            question_answer_service, "content_index_service", None
        )
        self._semantic_index_service = semantic_index_service or getattr(
            getattr(question_answer_service, "retrieval_service", None),
            "semantic_index_service",
            None,
        )
        self._question_answer_service = question_answer_service
        self._technical_consultant_service = technical_consultant_service
        self._whatsapp_share_service = (
            whatsapp_share_service or WhatsAppShareService()
        )
        self._worker: DocumentCatalogRefreshWorker | None = None
        self._content_search_dialog: DocumentContentSearchDialog | None = None
        self._question_answer_dialog: DocumentQuestionAnswerDialog | None = None
        self._technical_consultant_dialog: TechnicalConsultantDialog | None = None
        self._documents_by_id: dict[str, DocumentLibraryItem] = {}
        self._loaded_document_id: str | None = None
        self._minimum_zoom = 0.25
        self._maximum_zoom = 4.0
        self._zoom_step = 0.25
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

        self.content_search_button = QPushButton("Buscar en contenido")
        self.content_search_button.setObjectName("documentLibraryContentSearch")
        self.content_search_button.setProperty("btnRole", "secondary")
        self.content_search_button.clicked.connect(self._open_content_search)
        filters_layout.addWidget(self.content_search_button)

        self.question_answer_button = QPushButton("Preguntar a la IA")
        self.question_answer_button.setObjectName("documentLibraryQuestionAnswer")
        self.question_answer_button.setProperty("btnRole", "secondary")
        self.question_answer_button.clicked.connect(self._open_question_answer)
        filters_layout.addWidget(self.question_answer_button)

        self.technical_consultant_button = QPushButton("Consultor técnico")
        self.technical_consultant_button.setObjectName(
            "documentLibraryTechnicalConsultant"
        )
        self.technical_consultant_button.setProperty("btnRole", "secondary")
        self.technical_consultant_button.clicked.connect(
            self._open_technical_consultant
        )
        filters_layout.addWidget(self.technical_consultant_button)

        self.refresh_button = QPushButton("Actualizar catálogo")
        self.refresh_button.setObjectName("documentLibraryRefreshButton")
        self.refresh_button.setProperty("btnRole", "primary")
        self.refresh_button.clicked.connect(self._start_refresh)
        filters_layout.addWidget(self.refresh_button)
        layout.addWidget(filters)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setObjectName("documentLibrarySplitter")
        self.main_splitter.setChildrenCollapsible(False)

        table_panel = QFrame()
        table_panel.setObjectName("documentLibraryTablePanel")
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(6)

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
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        column_widths = {1: 130, 2: 160, 3: 70, 4: 90, 5: 135}
        for column, width in column_widths.items():
            header_view.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(column, width)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemDoubleClicked.connect(lambda _item: self._open_selected_document())
        table_layout.addWidget(self.table, 1)

        self.empty_state_label = QLabel()
        self.empty_state_label.setObjectName("documentLibraryEmptyState")
        self.empty_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state_label.setWordWrap(True)
        table_layout.addWidget(self.empty_state_label)

        self.main_splitter.addWidget(table_panel)
        self.main_splitter.addWidget(self._build_preview_panel())
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([760, 420])
        layout.addWidget(self.main_splitter, 1)

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
        self.whatsapp_button = QPushButton("WhatsApp")
        self.whatsapp_button.setObjectName("documentLibraryWhatsAppButton")
        self.whatsapp_button.setProperty("btnRole", "success")
        self.whatsapp_button.setEnabled(False)
        self.whatsapp_button.clicked.connect(self._share_selected_document)
        footer.addWidget(self.whatsapp_button)
        layout.addLayout(footer)

    def _build_preview_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("documentLibraryPreviewPanel")
        panel.setMinimumWidth(320)
        preview_layout = QVBoxLayout(panel)
        preview_layout.setContentsMargins(10, 8, 0, 0)
        preview_layout.setSpacing(7)

        self.preview_name_label = QLabel("Vista previa")
        self.preview_name_label.setObjectName("documentLibraryPreviewName")
        self.preview_name_label.setStyleSheet("font-weight: 600;")
        preview_layout.addWidget(self.preview_name_label)

        self.preview_path_label = QLabel("")
        self.preview_path_label.setObjectName("documentLibraryPreviewPath")
        self.preview_path_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_path_label)

        controls = QHBoxLayout()
        self.fit_width_button = QPushButton("Ajustar ancho")
        self.fit_width_button.setObjectName("documentLibraryFitWidth")
        self.fit_width_button.clicked.connect(self._fit_preview_to_width)
        controls.addWidget(self.fit_width_button)
        self.zoom_out_button = QPushButton("−")
        self.zoom_out_button.setObjectName("documentLibraryZoomOut")
        self.zoom_out_button.setToolTip("Reducir zoom")
        self.zoom_out_button.clicked.connect(lambda: self._change_zoom(-self._zoom_step))
        controls.addWidget(self.zoom_out_button)
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setObjectName("documentLibraryZoomIn")
        self.zoom_in_button.setToolTip("Aumentar zoom")
        self.zoom_in_button.clicked.connect(lambda: self._change_zoom(self._zoom_step))
        controls.addWidget(self.zoom_in_button)
        self.zoom_label = QLabel("100 %")
        self.zoom_label.setObjectName("documentLibraryZoomLabel")
        self.zoom_label.setMinimumWidth(58)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls.addWidget(self.zoom_label)
        controls.addStretch(1)
        preview_layout.addLayout(controls)

        self.preview_stack = QStackedWidget()
        self.preview_stack.setObjectName("documentLibraryPreviewStack")
        self.preview_placeholder = QLabel("Selecciona un PDF para previsualizarlo")
        self.preview_placeholder.setObjectName("documentLibraryPreviewPlaceholder")
        self.preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_placeholder.setWordWrap(True)
        self.preview_stack.addWidget(self.preview_placeholder)

        self.pdf_view = QPdfView()
        self.pdf_view.setObjectName("documentLibraryPdfView")
        self.pdf_document = QPdfDocument(self)
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.pdf_view.zoomFactorChanged.connect(self._update_zoom_controls)
        self.preview_stack.addWidget(self.pdf_view)
        preview_layout.addWidget(self.preview_stack, 1)

        self.preview_status_label = QLabel("Selecciona un PDF para previsualizarlo")
        self.preview_status_label.setObjectName("documentLibraryPreviewStatus")
        self.preview_status_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_status_label)
        self._set_preview_controls_enabled(False)
        return panel

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
        self._documents_by_id = {document.document_id: document for document in documents}
        self.table.setUpdatesEnabled(False)
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
        self.table.setUpdatesEnabled(True)
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
        self._selection_changed()

    def _clear_filters(self) -> None:
        self.table.clearSelection()
        self._clear_preview()
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
        worker = DocumentCatalogRefreshWorker(self._catalog_refresh_service, self)
        self._worker = worker
        worker.result_ready.connect(self._refresh_succeeded)
        worker.failed.connect(self._refresh_failed)
        worker.finished.connect(lambda: self._finish_refresh(worker))
        try:
            worker.start()
        except Exception as exc:  # noqa: BLE001
            self._refresh_failed(str(exc) or "No se pudo iniciar la actualización.")
            self._finish_refresh(worker)

    def _open_content_search(self) -> None:
        if self._content_search_dialog is not None:
            self._content_search_dialog.raise_()
            self._content_search_dialog.activateWindow()
            return
        if self._content_index_service is None:
            self._content_index_service = DocumentContentIndexService(self._service)
        if self._semantic_index_service is None:
            self._semantic_index_service = DocumentSemanticIndexService(
                self._content_index_service,
                LocalEmbeddingService(),
            )
        dialog = DocumentContentSearchDialog(
            self._service,
            self._content_index_service,
            self,
            semantic_service=self._semantic_index_service,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.document_requested.connect(self._show_content_search_result)
        dialog.destroyed.connect(self._content_search_dialog_closed)
        self._content_search_dialog = dialog
        dialog.open()

    def _content_search_dialog_closed(self) -> None:
        self._content_search_dialog = None

    def _open_question_answer(self) -> None:
        if self._question_answer_dialog is not None:
            self._question_answer_dialog.raise_()
            self._question_answer_dialog.activateWindow()
            return
        if self._question_answer_service is None:
            if self._content_index_service is None:
                self._content_index_service = DocumentContentIndexService(self._service)
            if self._semantic_index_service is None:
                self._semantic_index_service = DocumentSemanticIndexService(
                    self._content_index_service,
                    LocalEmbeddingService(),
                )
            retrieval_service = DocumentHybridRetrievalService(
                self._content_index_service,
                self._semantic_index_service,
            )
            self._question_answer_service = DocumentQuestionAnswerService(
                self._content_index_service,
                retrieval_service=retrieval_service,
            )
        dialog = DocumentQuestionAnswerDialog(
            self._service,
            self._question_answer_service,
            self,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.source_requested.connect(self._show_content_search_result)
        dialog.destroyed.connect(self._question_answer_dialog_closed)
        self._question_answer_dialog = dialog
        dialog.open()

    def _question_answer_dialog_closed(self) -> None:
        self._question_answer_dialog = None

    def _open_technical_consultant(self) -> None:
        if self._technical_consultant_dialog is not None:
            self._technical_consultant_dialog.raise_()
            self._technical_consultant_dialog.activateWindow()
            return
        if self._technical_consultant_service is None:
            if self._content_index_service is None:
                self._content_index_service = DocumentContentIndexService(self._service)
            if self._semantic_index_service is None:
                self._semantic_index_service = DocumentSemanticIndexService(
                    self._content_index_service,
                    LocalEmbeddingService(),
                )
            hybrid_service = DocumentHybridRetrievalService(
                self._content_index_service,
                self._semantic_index_service,
            )
            retrieval_service = TechnicalProductRetrievalService(hybrid_service)
            comparison_service = TechnicalProductComparisonService(
                retrieval_service,
                self._content_index_service,
            )
            decision_service = TechnicalProductDecisionService(comparison_service)
            self._technical_consultant_service = TechnicalConsultantService(
                decision_service
            )
        dialog = TechnicalConsultantDialog(
            self._technical_consultant_service,
            self,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.source_requested.connect(self._show_content_search_result)
        dialog.destroyed.connect(self._technical_consultant_dialog_closed)
        self._technical_consultant_dialog = dialog
        dialog.open()

    def _technical_consultant_dialog_closed(self) -> None:
        self._technical_consultant_dialog = None

    def _show_content_search_result(self, document_id: str, page_number: int) -> None:
        self._clear_filters()
        matching_row = None
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == document_id:
                matching_row = row
                break
        if matching_row is None:
            self._show_preview_placeholder(
                "El documento del resultado ya no está disponible en el catálogo."
            )
            return
        self.table.selectRow(matching_row)
        document = self._documents_by_id.get(document_id)
        if document is None or document.extension.casefold() != ".pdf":
            return
        if self._loaded_document_id != document_id:
            return
        self._navigate_to_pdf_page(page_number)

    def _navigate_to_pdf_page(self, page_number: int) -> None:
        page_count = self.pdf_document.pageCount()
        if page_count <= 0:
            return
        target_page = max(0, min(int(page_number) - 1, page_count - 1))
        try:
            navigator = self.pdf_view.pageNavigator()
            navigator.jump(target_page, QPointF(), 0)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            self.preview_status_label.setText(
                f"PDF cargado, pero no se pudo ir a la página {target_page + 1}."
            )

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
        if result.product_links is not None:
            links = result.product_links
            summary += (
                f" Relaciones: {links.linked} vinculadas, {links.created} nuevas, "
                f"{links.updated} actualizadas, {links.unchanged} conservadas y "
                f"{links.removed} retiradas; {links.unmatched} sin producto y "
                f"{links.ambiguous} ambiguas."
            )
        elif result.product_link_error:
            summary += (
                " El catálogo se actualizó, pero falló la relación con productos: "
                f"{result.product_link_error}"
            )
        elif not result.scan_complete:
            summary += " Las relaciones no se actualizaron porque el escaneo quedó incompleto."
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
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _selected_document(self) -> DocumentLibraryItem | None:
        document_id = self._selected_document_id()
        return self._documents_by_id.get(document_id) if document_id else None

    def _selection_changed(self) -> None:
        document = self._selected_document()
        self.open_button.setEnabled(document is not None)
        self.whatsapp_button.setEnabled(document is not None)
        if document is None:
            self._clear_preview()
            return
        self._preview_document(document)

    def _preview_document(self, document: DocumentLibraryItem) -> None:
        self._close_pdf_document()
        self.preview_name_label.setText(document.name)
        self.preview_path_label.setText(document.relative_path)
        if document.extension.casefold() != ".pdf":
            self._show_preview_placeholder(
                "La vista previa interna está disponible solo para PDF. "
                "Usa «Abrir documento» para consultar este archivo."
            )
            return
        if not self._service.is_library_available():
            self._show_preview_placeholder("La biblioteca documental no está disponible.")
            return

        self._show_preview_placeholder("Cargando PDF...")
        try:
            resolved_path = self._service.resolve_document(document.document_id)
        except DocumentNotFoundError as exc:
            self._show_preview_placeholder(f"El archivo ha desaparecido: {exc}")
            return
        except UnsafeDocumentPathError as exc:
            self._show_preview_placeholder(f"La ruta del documento no es segura: {exc}")
            return

        load_error = self.pdf_document.load(str(resolved_path))
        if load_error != QPdfDocument.Error.None_ or self.pdf_document.pageCount() <= 0:
            self._close_pdf_document()
            self._show_preview_placeholder(
                "El PDF está corrupto o no es compatible con el visor."
            )
            return

        self._loaded_document_id = document.document_id
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.preview_stack.setCurrentWidget(self.pdf_view)
        page_count = self.pdf_document.pageCount()
        self.preview_status_label.setText(
            f"PDF cargado · {page_count} página" if page_count == 1 else f"PDF cargado · {page_count} páginas"
        )
        self._set_preview_controls_enabled(True)
        self._update_zoom_controls()

    def _show_preview_placeholder(self, message: str) -> None:
        self.preview_placeholder.setText(message)
        self.preview_status_label.setText(message)
        self.preview_stack.setCurrentWidget(self.preview_placeholder)
        self._set_preview_controls_enabled(False)

    def _clear_preview(self) -> None:
        self._close_pdf_document()
        self.preview_name_label.setText("Vista previa")
        self.preview_path_label.clear()
        self._show_preview_placeholder("Selecciona un PDF para previsualizarlo")

    def _close_pdf_document(self) -> None:
        self.pdf_document.close()
        self._loaded_document_id = None
        self._set_preview_controls_enabled(False)

    def _dispose_pdf_view(self) -> None:
        self.pdf_view.setDocument(None)
        self.pdf_document.close()
        self._loaded_document_id = None
        self._set_preview_controls_enabled(False)

    def _set_preview_controls_enabled(self, enabled: bool) -> None:
        self.fit_width_button.setEnabled(enabled)
        self.zoom_out_button.setEnabled(enabled)
        self.zoom_in_button.setEnabled(enabled)
        if not enabled:
            self.zoom_label.setText("—")

    def _fit_preview_to_width(self) -> None:
        if self._loaded_document_id is None:
            return
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._update_zoom_controls()

    def _change_zoom(self, amount: float) -> None:
        if self._loaded_document_id is None:
            return
        current_zoom = float(self.pdf_view.zoomFactor())
        target_zoom = max(
            self._minimum_zoom,
            min(self._maximum_zoom, current_zoom + amount),
        )
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(target_zoom)
        self._update_zoom_controls(target_zoom)

    def _update_zoom_controls(self, zoom_factor: float | None = None) -> None:
        if self._loaded_document_id is None:
            return
        factor = float(zoom_factor if zoom_factor is not None else self.pdf_view.zoomFactor())
        factor = max(self._minimum_zoom, min(self._maximum_zoom, factor))
        self.zoom_label.setText(f"{round(factor * 100)} %")
        self.zoom_out_button.setEnabled(factor > self._minimum_zoom)
        self.zoom_in_button.setEnabled(factor < self._maximum_zoom)

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

    def _share_selected_document(self) -> None:
        document = self._selected_document()
        if document is None:
            return
        try:
            path = self._service.resolve_document(document.document_id)
        except (DocumentNotFoundError, UnsafeDocumentPathError) as exc:
            QMessageBox.warning(self, "WhatsApp", str(exc))
            return

        dialog = WhatsAppShareDialog(
            document.name,
            self._whatsapp_share_service,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        chat_url = self._whatsapp_share_service.build_chat_url(
            dialog.normalized_phone,
            dialog.message,
        )
        file_revealed = self._whatsapp_share_service.reveal_file(path)
        chat_opened = QDesktopServices.openUrl(QUrl(chat_url))
        if not chat_opened:
            QMessageBox.warning(
                self,
                "WhatsApp",
                "Windows no pudo abrir la conversación de WhatsApp.",
            )
            return
        if not file_revealed:
            QMessageBox.warning(
                self,
                "WhatsApp",
                "La conversación se abrió, pero Windows no pudo mostrar el archivo. "
                "Adjúntalo manualmente desde WhatsApp.",
            )
            return
        self.status_label.setText(
            "WhatsApp abierto. Arrastra el documento marcado en el Explorador "
            "al chat y confirma el envío."
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        self._dispose_pdf_view()
        super().closeEvent(event)

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

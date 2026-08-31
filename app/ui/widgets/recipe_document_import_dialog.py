from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.document_content_index_service import DocumentContentSearchResult
from app.services.recipe_document_import_service import (
    RecipeDocumentDraft,
    RecipeDocumentImportService,
)


class RecipeDocumentImportDialog(QDialog):
    """Search, preview and review one documented recipe before loading it."""

    def __init__(self, service: RecipeDocumentImportService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.selected_draft: RecipeDocumentDraft | None = None
        self._results: list[DocumentContentSearchResult] = []
        self._active_result: DocumentContentSearchResult | None = None
        self._draft: RecipeDocumentDraft | None = None
        self.setWindowTitle("Importar fórmula desde documentación")
        self.setObjectName("recipeDocumentImportDialog")
        self.setModal(True)
        self.resize(1180, 780)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        search_row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setObjectName("recipeDocumentQuery")
        self.query_input.setPlaceholderText("Nombre, producto IREKS o texto de la fórmula...")
        self.query_input.setClearButtonEnabled(True)
        self.query_input.returnPressed.connect(self._search)
        search_row.addWidget(self.query_input, 1)
        self.search_button = QPushButton("Buscar")
        self.search_button.setObjectName("recipeDocumentSearchButton")
        self.search_button.setProperty("btnRole", "primary")
        self.search_button.clicked.connect(self._search)
        search_row.addWidget(self.search_button)
        root.addLayout(search_row)

        self.status_label = QLabel(
            "La búsqueda se limita a la documentación técnica de recetas y recetarios."
        )
        self.status_label.setObjectName("recipeDocumentStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Resultados"))
        self.results_table = QTableWidget(0, 4)
        self.results_table.setObjectName("recipeDocumentResults")
        self.results_table.setHorizontalHeaderLabels(
            ["Documento", "Categoría", "Pág.", "Coincidencia"]
        )
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.verticalHeader().setVisible(False)
        results_header = self.results_table.horizontalHeader()
        results_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        results_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        results_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        results_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.results_table.setColumnWidth(0, 235)
        self.results_table.setColumnWidth(1, 180)
        self.results_table.itemSelectionChanged.connect(self._result_selected)
        left_layout.addWidget(self.results_table, 2)

        review_header = QHBoxLayout()
        review_header.addWidget(QLabel("Revisión de la fórmula"))
        self.raw_material_button = QPushButton("Buscar materia prima")
        self.raw_material_button.setObjectName("recipeDocumentRawMaterialSearch")
        self.raw_material_button.setToolTip(
            "Asociar la línea seleccionada con un ingrediente de Materias primas"
        )
        self.raw_material_button.setEnabled(False)
        self.raw_material_button.clicked.connect(self._search_raw_material)
        review_header.addWidget(self.raw_material_button)
        review_header.addStretch(1)
        self.page_label = QLabel("Página")
        review_header.addWidget(self.page_label)
        self.page_spin = QSpinBox()
        self.page_spin.setObjectName("recipeDocumentPage")
        self.page_spin.setRange(1, 1)
        self.page_spin.setEnabled(False)
        self.page_spin.valueChanged.connect(self._page_changed)
        review_header.addWidget(self.page_spin)
        left_layout.addLayout(review_header)

        self.draft_name_label = QLabel("Selecciona un resultado.")
        self.draft_name_label.setObjectName("recipeDocumentDraftName")
        self.draft_name_label.setWordWrap(True)
        left_layout.addWidget(self.draft_name_label)
        self.review_table = QTableWidget(0, 5)
        self.review_table.setObjectName("recipeDocumentReview")
        self.review_table.setHorizontalHeaderLabels(
            ["Proceso", "Texto extraído", "Cantidad", "Coincidencia", "Estado"]
        )
        self.review_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.review_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.review_table.verticalHeader().setVisible(False)
        self.review_table.itemSelectionChanged.connect(self._review_selection_changed)
        self.review_table.itemDoubleClicked.connect(lambda _item: self._search_raw_material())
        review_header_widget = self.review_table.horizontalHeader()
        review_header_widget.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        review_header_widget.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        review_header_widget.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        review_header_widget.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        review_header_widget.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        left_layout.addWidget(self.review_table, 3)
        self.warning_label = QLabel("")
        self.warning_label.setObjectName("recipeDocumentWarnings")
        self.warning_label.setWordWrap(True)
        left_layout.addWidget(self.warning_label)
        splitter.addWidget(left)

        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(QLabel("Documento original"))
        self.pdf_view = QPdfView()
        self.pdf_view.setObjectName("recipeDocumentPdfPreview")
        self.pdf_document = QPdfDocument(self)
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        preview_layout.addWidget(self.pdf_view, 1)
        splitter.addWidget(preview_panel)
        splitter.setSizes([690, 470])
        root.addWidget(splitter, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.load_button = QPushButton("Cargar como borrador")
        self.load_button.setObjectName("recipeDocumentLoadDraft")
        self.load_button.setProperty("btnRole", "success")
        self.load_button.setEnabled(False)
        self.load_button.clicked.connect(self._accept_draft)
        actions.addWidget(self.load_button)
        close_button = QPushButton("Cancelar")
        close_button.clicked.connect(self.reject)
        actions.addWidget(close_button)
        root.addLayout(actions)

    def _search(self) -> None:
        query = self.query_input.text().strip()
        if not query:
            self._render_results([])
            self.status_label.setText("Escribe un término antes de buscar.")
            return
        try:
            results = self.service.search(query)
        except Exception as exc:  # noqa: BLE001
            self._render_results([])
            self.status_label.setText(f"No se pudo consultar la documentación: {exc}")
            return
        self._render_results(results)
        self.status_label.setText(
            f"{len(results)} resultado(s). Selecciona una página y revisa la extracción."
            if results
            else "No se encontraron fórmulas para la consulta indicada."
        )

    def _render_results(self, results: list[DocumentContentSearchResult]) -> None:
        self._results = list(results)
        self.results_table.blockSignals(True)
        self.results_table.setRowCount(len(results))
        for row, result in enumerate(results):
            values = (result.name, result.category, str(result.page_number), result.fragment)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.results_table.setItem(row, column, item)
        self.results_table.blockSignals(False)
        if results:
            self.results_table.selectRow(0)
            self._result_selected()
        else:
            self._active_result = None
            self._render_draft(None)
            self._close_pdf()

    def _result_selected(self) -> None:
        selected = self.results_table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        if row < 0 or row >= len(self._results):
            return
        self._active_result = self._results[row]
        self._load_pdf(self._active_result)
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(self._active_result.page_number)
        self.page_spin.blockSignals(False)
        self._load_draft(self._active_result.page_number)

    def _load_pdf(self, result: DocumentContentSearchResult) -> None:
        self._close_pdf()
        try:
            path = self.service.resolve_document(result.document_id)
            load_error = self.pdf_document.load(str(path))
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"No se pudo abrir el documento: {exc}")
            self.page_spin.setEnabled(False)
            return
        if load_error != QPdfDocument.Error.None_ or self.pdf_document.pageCount() <= 0:
            self.status_label.setText("El PDF seleccionado no se pudo previsualizar.")
            self.page_spin.setEnabled(False)
            return
        self.page_spin.setRange(1, self.pdf_document.pageCount())
        self.page_spin.setEnabled(True)
        self._navigate_pdf(result.page_number)

    def _page_changed(self, page_number: int) -> None:
        if self._active_result is None:
            return
        self._navigate_pdf(page_number)
        self._load_draft(page_number)

    def _navigate_pdf(self, page_number: int) -> None:
        if self.pdf_document.pageCount() <= 0:
            return
        target = max(0, min(int(page_number) - 1, self.pdf_document.pageCount() - 1))
        try:
            self.pdf_view.pageNavigator().jump(target, QPointF(), 0)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

    def _load_draft(self, page_number: int) -> None:
        if self._active_result is None:
            return
        try:
            draft = self.service.build_draft(self._active_result, page_number=page_number)
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"No se pudo extraer la fórmula: {exc}")
            self._render_draft(None)
            return
        self._render_draft(draft)

    def _render_draft(self, draft: RecipeDocumentDraft | None) -> None:
        self._draft = draft
        self.review_table.setRowCount(0 if draft is None else len(draft.lines))
        if draft is None:
            self.draft_name_label.setText("Selecciona un resultado.")
            self.warning_label.clear()
            self.load_button.setEnabled(False)
            self.raw_material_button.setEnabled(False)
            return
        self.draft_name_label.setText(
            f"{draft.recipe_name} · página {draft.page_number} · {len(draft.lines)} líneas"
        )
        for row, line in enumerate(draft.lines):
            matched = line.matched_ingredient
            values = (
                line.process_name,
                line.source_name,
                line.source_quantity,
                matched.nombre if matched is not None else "—",
                "Coincide" if matched is not None else "Revisar",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if matched is None:
                    item.setBackground(QColor("#FFF3CD"))
                if line.notes:
                    item.setToolTip(line.notes)
                self.review_table.setItem(row, column, item)
        self.warning_label.setText("\n".join(f"• {warning}" for warning in draft.warnings))
        self.load_button.setEnabled(bool(draft.recipe_name and draft.lines))
        self._review_selection_changed()

    def _review_selection_changed(self) -> None:
        selected = self.review_table.selectionModel().selectedRows()
        self.raw_material_button.setEnabled(bool(self._draft is not None and selected))

    def _search_raw_material(self) -> None:
        if self._draft is None:
            return
        selected_rows = self.review_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Materias primas", "Selecciona primero una línea.")
            return
        line_index = selected_rows[0].row()
        source_line = self._draft.lines[line_index]
        query, accepted = QInputDialog.getText(
            self,
            "Buscar materia prima",
            "Nombre o parte del nombre:",
            QLineEdit.EchoMode.Normal,
            source_line.source_name,
        )
        if not accepted or not query.strip():
            return
        candidates = self.service.search_raw_materials(query.strip())
        if not candidates:
            QMessageBox.information(
                self,
                "Materias primas",
                "No se encontraron materias primas para ese texto.",
            )
            return
        labels = [
            f"{ingredient.nombre} ({ingredient.codigo})" if ingredient.codigo else ingredient.nombre
            for ingredient in candidates
        ]
        selected_label, accepted = QInputDialog.getItem(
            self,
            "Seleccionar materia prima",
            "Coincidencias:",
            labels,
            0,
            False,
        )
        if not accepted:
            return
        selected_index = labels.index(selected_label)
        self._draft = self.service.apply_raw_material_match(
            self._draft,
            line_index,
            candidates[selected_index],
        )
        self._render_draft(self._draft)
        self.review_table.selectRow(line_index)

    def _accept_draft(self) -> None:
        if self._draft is None or not self._draft.lines:
            return
        if self._draft.unresolved_count:
            answer = QMessageBox.question(
                self,
                "Ingredientes pendientes",
                f"Hay {self._draft.unresolved_count} ingrediente(s) sin asociación exacta. "
                "Se cargarán marcados para revisión y no se guardará nada todavía. ¿Continuar?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.selected_draft = self._draft
        self.accept()

    def _close_pdf(self) -> None:
        self.pdf_document.close()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._close_pdf()
        super().closeEvent(event)

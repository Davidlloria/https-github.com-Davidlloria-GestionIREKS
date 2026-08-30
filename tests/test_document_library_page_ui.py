from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QApplication, QDialog, QHeaderView, QMessageBox
from reportlab.pdfgen import canvas

import app.ui.widgets.document_library_page as page_module
from app.services.document_library_service import (
    DocumentLibraryItem,
    DocumentLibraryScanResult,
    DocumentLibraryService,
    DocumentNotFoundError,
    UnsafeDocumentPathError,
)
from app.services.document_semantic_index_service import DocumentSemanticIndexStatus
from app.ui.widgets.document_library_page import DocumentLibraryPage


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _document(
    document_id: str,
    relative_path: str,
    *,
    area: str,
    category: str,
    extension: str,
    size_bytes: int = 2048,
) -> DocumentLibraryItem:
    return DocumentLibraryItem(
        document_id=document_id,
        relative_path=relative_path,
        name=Path(relative_path).name,
        area=area,
        category=category,
        extension=extension,
        size_bytes=size_bytes,
        modified_at="2026-08-28T10:30:00+00:00",
        indexed_at="2026-08-28T11:00:00+00:00",
        active=True,
    )


def _write_pdf(
    path: Path,
    text: str = "Documento de prueba",
    *,
    pages: int = 1,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path))
    for page_number in range(pages):
        pdf.drawString(72, 760, f"{text} {page_number + 1}")
        pdf.showPage()
    pdf.save()
    return path


class _FakeDocumentLibraryService:
    def __init__(self, documents: list[DocumentLibraryItem] | None = None) -> None:
        self.documents = documents or []
        self.available = True
        self.resolved_ids: list[str] = []
        self.resolve_error: Exception | None = None
        self.resolved_path = Path("C:/safe/document.pdf")
        self.resolved_paths: dict[str, Path] = {}

    def is_library_available(self) -> bool:
        return self.available

    def list_documents(
        self,
        *,
        query=None,
        area=None,
        category=None,
        extension=None,
        active=True,
    ) -> list[DocumentLibraryItem]:
        rows = [item for item in self.documents if item.active is active]
        if query:
            term = str(query).casefold()
            rows = [
                item
                for item in rows
                if term in item.name.casefold() or term in item.relative_path.casefold()
            ]
        if area:
            rows = [item for item in rows if item.area.casefold() == str(area).casefold()]
        if category:
            rows = [
                item
                for item in rows
                if item.category.casefold() == str(category).casefold()
            ]
        if extension:
            rows = [
                item
                for item in rows
                if item.extension.casefold() == str(extension).casefold()
            ]
        return rows

    def resolve_document(self, document_id: str) -> Path:
        self.resolved_ids.append(document_id)
        if self.resolve_error is not None:
            raise self.resolve_error
        return self.resolved_paths.get(document_id, self.resolved_path)


class _FakeContentIndexService:
    def __init__(self, library_service: _FakeDocumentLibraryService) -> None:
        self.library_service = library_service

    def search(self, *_args, **_kwargs):
        return []


class _FakeSemanticIndexService:
    def __init__(self, content_index_service) -> None:
        self.content_index_service = content_index_service
        self.embedding_service = type("Embedding", (), {"model": "embeddinggemma"})()

    def get_status(self):
        return DocumentSemanticIndexStatus(
            configured_model="embeddinggemma",
            content_documents=1,
            requires_reindex=True,
        )


class _FakeQuestionAnswerService:
    def answer(self, *_args, **_kwargs):
        raise AssertionError("El test de apertura no debe consultar la IA.")


def _sample_documents() -> list[DocumentLibraryItem]:
    return [
        _document(
            "a" * 64,
            "Calidad/Fichas/Trigo.pdf",
            area="Calidad",
            category="Fichas",
            extension=".pdf",
        ),
        _document(
            "b" * 64,
            "Calidad/Normas/Trigo.docx",
            area="Calidad",
            category="Normas",
            extension=".docx",
        ),
        _document(
            "c" * 64,
            "Ventas/Tarifas/Precios.xlsx",
            area="Ventas",
            category="Tarifas",
            extension=".xlsx",
        ),
    ]


def test_empty_catalog_shows_call_to_refresh_and_disables_open() -> None:
    _application()
    page = DocumentLibraryPage(_FakeDocumentLibraryService())

    assert page.table.rowCount() == 0
    assert page.counter_label.text() == "0 documentos"
    assert "catálogo está vacío" in page.empty_state_label.text()
    assert not page.empty_state_label.isHidden()
    assert page.open_button.isEnabled() is False
    assert page.preview_status_label.text() == "Selecciona un PDF para previsualizarlo"
    assert page.fit_width_button.isEnabled() is False
    assert page.zoom_out_button.isEnabled() is False
    assert page.zoom_in_button.isEnabled() is False


def test_page_loads_catalog_and_combines_search_and_filters() -> None:
    _application()
    page = DocumentLibraryPage(_FakeDocumentLibraryService(_sample_documents()))

    assert page.table.rowCount() == 3
    assert page.counter_label.text() == "3 documentos"
    page.area_filter.setCurrentIndex(page.area_filter.findData("Calidad"))
    page.category_filter.setCurrentIndex(page.category_filter.findData("Fichas"))
    page.extension_filter.setCurrentIndex(page.extension_filter.findData(".pdf"))
    page.search_input.setText("FICHAS/TRIGO")

    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "Trigo.pdf"
    assert page.counter_label.text() == "1 documento"
    assert "C:/" not in page.table.item(0, 0).toolTip()


def test_large_catalog_columns_do_not_use_resize_to_contents() -> None:
    _application()
    page = DocumentLibraryPage(_FakeDocumentLibraryService(_sample_documents()))
    header = page.table.horizontalHeader()

    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    for column in range(1, page.table.columnCount()):
        assert header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive


def test_open_uses_selected_identifier_and_safe_resolved_path(monkeypatch) -> None:
    _application()
    service = _FakeDocumentLibraryService([_sample_documents()[1]])
    page = DocumentLibraryPage(service)
    opened_urls: list[QUrl] = []
    monkeypatch.setattr(
        page_module.QDesktopServices,
        "openUrl",
        lambda url: opened_urls.append(url) or True,
    )

    assert page.open_button.isEnabled() is False
    page.table.selectRow(0)
    _application().processEvents()
    assert page.open_button.isEnabled() is True
    page.open_button.click()

    assert service.resolved_ids == ["b" * 64]
    assert len(opened_urls) == 1
    assert opened_urls[0].toLocalFile().replace("\\", "/").endswith(
        "C:/safe/document.pdf"
    )


def test_whatsapp_button_prepares_selected_document_without_sending(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _application()
    document = _sample_documents()[1]
    library = _FakeDocumentLibraryService([document])
    library.resolved_path = tmp_path / document.name

    class _FakeWhatsAppService:
        def __init__(self) -> None:
            self.revealed: list[Path] = []
            self.urls: list[tuple[str, str]] = []

        def build_chat_url(self, phone: str, message: str) -> str:
            self.urls.append((phone, message))
            return "https://wa.me/34600123456?text=mensaje"

        def reveal_file(self, path: Path) -> bool:
            self.revealed.append(path)
            return True

    share_service = _FakeWhatsAppService()

    class _AcceptedDialog:
        def __init__(self, document_name, service, parent) -> None:
            assert document_name == document.name
            assert service is share_service
            assert parent is page
            self.normalized_phone = "34600123456"
            self.message = "Te envío la ficha."

        def exec(self):
            return QDialog.DialogCode.Accepted

    opened_urls: list[QUrl] = []
    monkeypatch.setattr(page_module, "WhatsAppShareDialog", _AcceptedDialog)
    monkeypatch.setattr(
        page_module.QDesktopServices,
        "openUrl",
        lambda url: opened_urls.append(url) or True,
    )
    page = DocumentLibraryPage(
        library,
        whatsapp_share_service=share_service,  # type: ignore[arg-type]
    )

    assert page.whatsapp_button.text() == "WhatsApp"
    assert page.whatsapp_button.isEnabled() is False
    page.table.selectRow(0)
    assert page.whatsapp_button.isEnabled() is True
    page.whatsapp_button.click()

    assert library.resolved_ids == [document.document_id]
    assert share_service.revealed == [library.resolved_path]
    assert share_service.urls == [
        ("34600123456", "Te envío la ficha.")
    ]
    assert [url.toString() for url in opened_urls] == [
        "https://wa.me/34600123456?text=mensaje"
    ]
    assert "confirma el envío" in page.status_label.text()


def test_missing_document_shows_message_and_does_not_open(monkeypatch) -> None:
    _application()
    service = _FakeDocumentLibraryService(_sample_documents()[:1])
    service.resolve_error = DocumentNotFoundError("El archivo ha desaparecido.")
    page = DocumentLibraryPage(service)
    warnings: list[str] = []
    opened_urls: list[QUrl] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    monkeypatch.setattr(
        page_module.QDesktopServices,
        "openUrl",
        lambda url: opened_urls.append(url) or True,
    )
    page.table.selectRow(0)

    page._open_selected_document()

    assert service.resolved_ids == ["a" * 64, "a" * 64]
    assert warnings == ["El archivo ha desaparecido."]
    assert opened_urls == []


class _FinishedWorker:
    def __init__(self) -> None:
        self.deleted = False

    def deleteLater(self) -> None:
        self.deleted = True


def test_refresh_status_and_button_recover_after_success_and_error() -> None:
    _application()
    service = _FakeDocumentLibraryService(_sample_documents()[:1])
    page = DocumentLibraryPage(service)
    worker = _FinishedWorker()

    page._worker = worker  # type: ignore[assignment]
    page._set_refreshing(True)
    assert page.refresh_button.isEnabled() is False
    assert "segundo plano" in page.status_label.text()
    page._refresh_succeeded(
        DocumentLibraryScanResult(
            available=True,
            scan_complete=False,
            added=1,
            updated=2,
            unchanged=3,
            deactivated=4,
            errors=("sin acceso a una subcarpeta",),
        )
    )
    page._finish_refresh(worker)  # type: ignore[arg-type]
    assert page.refresh_button.isEnabled() is True
    assert "1 añadidos" in page.status_label.text()
    assert "Errores parciales: 1" in page.status_label.text()

    second_worker = _FinishedWorker()
    page._worker = second_worker  # type: ignore[assignment]
    page._set_refreshing(True)
    page._refresh_failed("fallo simulado")
    page._finish_refresh(second_worker)  # type: ignore[arg-type]
    assert page.refresh_button.isEnabled() is True
    assert page.status_label.text() == "No se pudo actualizar el catálogo: fallo simulado"


def test_inactive_documents_are_not_shown() -> None:
    _application()
    inactive = replace(_sample_documents()[0], active=False)
    page = DocumentLibraryPage(_FakeDocumentLibraryService([inactive]))

    assert page.table.rowCount() == 0


def test_selecting_valid_pdf_resolves_identifier_and_loads_preview(tmp_path: Path) -> None:
    _application()
    document = _sample_documents()[0]
    service = _FakeDocumentLibraryService([document])
    service.resolved_path = _write_pdf(tmp_path / "valid.pdf")
    page = DocumentLibraryPage(service)

    assert service.resolved_ids == []
    assert page._loaded_document_id is None
    page.table.selectRow(0)
    _application().processEvents()

    assert service.resolved_ids == [document.document_id]
    assert page._loaded_document_id == document.document_id
    assert page.pdf_document.pageCount() == 1
    assert page.preview_stack.currentWidget() is page.pdf_view
    assert page.preview_status_label.text() == "PDF cargado · 1 página"
    assert page.preview_name_label.text() == document.name
    assert page.preview_path_label.text() == document.relative_path
    assert str(tmp_path) not in page.preview_path_label.text()
    assert page.fit_width_button.isEnabled() is True


def test_selecting_non_pdf_does_not_resolve_or_load_preview() -> None:
    _application()
    document = _sample_documents()[1]
    service = _FakeDocumentLibraryService([document])
    page = DocumentLibraryPage(service)

    page.table.selectRow(0)

    assert service.resolved_ids == []
    assert page._loaded_document_id is None
    assert "solo para PDF" in page.preview_status_label.text()
    assert page.preview_stack.currentWidget() is page.preview_placeholder


def test_missing_pdf_and_unsafe_path_show_internal_errors() -> None:
    _application()
    document = _sample_documents()[0]
    service = _FakeDocumentLibraryService([document])
    service.resolve_error = DocumentNotFoundError("No existe")
    page = DocumentLibraryPage(service)

    page.table.selectRow(0)
    assert "ha desaparecido" in page.preview_status_label.text()
    assert page._loaded_document_id is None

    page.table.clearSelection()
    service.resolve_error = UnsafeDocumentPathError("Fuera de la biblioteca")
    page.table.selectRow(0)
    assert "no es segura" in page.preview_status_label.text()
    assert page._loaded_document_id is None


def test_corrupt_pdf_shows_internal_error(tmp_path: Path) -> None:
    _application()
    document = _sample_documents()[0]
    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"not a valid pdf")
    service = _FakeDocumentLibraryService([document])
    service.resolved_path = corrupt_pdf
    page = DocumentLibraryPage(service)

    page.table.selectRow(0)

    assert "corrupto" in page.preview_status_label.text()
    assert page.preview_stack.currentWidget() is page.preview_placeholder
    assert page._loaded_document_id is None
    assert page.pdf_document.pageCount() == 0


def test_changing_pdf_replaces_previous_document(tmp_path: Path) -> None:
    _application()
    first = _sample_documents()[0]
    second = _document(
        "d" * 64,
        "Calidad/Fichas/Centeno.pdf",
        area="Calidad",
        category="Fichas",
        extension=".pdf",
    )
    service = _FakeDocumentLibraryService([first, second])
    service.resolved_paths = {
        first.document_id: _write_pdf(tmp_path / "first.pdf", pages=1),
        second.document_id: _write_pdf(tmp_path / "second.pdf", pages=2),
    }
    page = DocumentLibraryPage(service)

    first_row = next(
        row
        for row in range(page.table.rowCount())
        if page.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        == first.document_id
    )
    page.table.selectRow(first_row)
    assert page.pdf_document.pageCount() == 1
    second_row = next(
        row
        for row in range(page.table.rowCount())
        if page.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        == second.document_id
    )
    page.table.selectRow(second_row)

    assert service.resolved_ids == [first.document_id, second.document_id]
    assert page._loaded_document_id == second.document_id
    assert page.pdf_document.pageCount() == 2


def test_losing_selection_or_filtering_document_clears_preview(tmp_path: Path) -> None:
    _application()
    document = _sample_documents()[0]
    service = _FakeDocumentLibraryService([document])
    service.resolved_path = _write_pdf(tmp_path / "valid.pdf")
    page = DocumentLibraryPage(service)
    page.table.selectRow(0)
    assert page._loaded_document_id == document.document_id

    page.table.clearSelection()
    assert page._loaded_document_id is None
    assert page.pdf_document.pageCount() == 0
    assert page.preview_status_label.text() == "Selecciona un PDF para previsualizarlo"

    page.table.selectRow(0)
    page.clear_filters_button.click()
    assert page._loaded_document_id is None
    assert page.pdf_document.pageCount() == 0

    page.table.selectRow(0)
    page.search_input.setText("no-coincide")
    assert page.table.rowCount() == 0
    assert page._loaded_document_id is None
    assert page.pdf_document.pageCount() == 0


def test_zoom_is_limited_and_fit_width_restores_mode(tmp_path: Path) -> None:
    _application()
    document = _sample_documents()[0]
    service = _FakeDocumentLibraryService([document])
    service.resolved_path = _write_pdf(tmp_path / "valid.pdf")
    page = DocumentLibraryPage(service)
    page.table.selectRow(0)

    page.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
    page.pdf_view.setZoomFactor(3.9)
    page._change_zoom(0.25)
    assert page.pdf_view.zoomFactor() == pytest.approx(4.0)
    assert page.zoom_in_button.isEnabled() is False

    page.pdf_view.setZoomFactor(0.3)
    page._change_zoom(-0.25)
    assert page.pdf_view.zoomFactor() == pytest.approx(0.25)
    assert page.zoom_out_button.isEnabled() is False

    page.fit_width_button.click()
    assert page.pdf_view.zoomMode() == QPdfView.ZoomMode.FitToWidth


def test_unavailable_library_is_shown_inside_preview() -> None:
    _application()
    document = _sample_documents()[0]
    service = _FakeDocumentLibraryService([document])
    service.available = False
    page = DocumentLibraryPage(service)

    page.table.selectRow(0)

    assert service.resolved_ids == []
    assert page.preview_status_label.text() == "La biblioteca documental no está disponible."


def test_closing_page_releases_loaded_pdf(tmp_path: Path) -> None:
    _application()
    document = _sample_documents()[0]
    service = _FakeDocumentLibraryService([document])
    service.resolved_path = _write_pdf(tmp_path / "valid.pdf")
    page = DocumentLibraryPage(service)
    page.table.selectRow(0)
    assert page.pdf_document.pageCount() == 1

    page.close()
    _application().processEvents()

    assert page._loaded_document_id is None
    assert page.pdf_document.pageCount() == 0
    assert page.pdf_view.document() is None


def test_repeated_preview_cleanup_keeps_persistent_document_attached(
    tmp_path: Path,
) -> None:
    _application()
    document = _sample_documents()[0]
    service = _FakeDocumentLibraryService([document])
    service.resolved_path = _write_pdf(tmp_path / "valid.pdf")
    page = DocumentLibraryPage(service)
    page.table.selectRow(0)
    assert page.pdf_view.document() is page.pdf_document

    page.table.clearSelection()
    page._clear_preview()
    page._clear_preview()

    assert page.pdf_view.document() is page.pdf_document
    assert page.pdf_document.pageCount() == 0
    assert page._loaded_document_id is None


def test_content_search_dialog_opens_from_documents_page() -> None:
    _application()
    service = _FakeDocumentLibraryService(_sample_documents())
    content_service = _FakeContentIndexService(service)
    semantic_service = _FakeSemanticIndexService(content_service)
    page = DocumentLibraryPage(
        service,
        content_service,  # type: ignore[arg-type]
        semantic_index_service=semantic_service,  # type: ignore[arg-type]
    )

    page.content_search_button.click()
    _application().processEvents()

    assert page._content_search_dialog is not None
    assert page._content_search_dialog.isVisible()
    assert page._content_search_dialog._library_service is service
    assert page._content_search_dialog._content_service is content_service
    assert page._content_search_dialog._semantic_service is semantic_service
    page._content_search_dialog.close()
    _application().processEvents()


def test_content_pdf_result_clears_filters_selects_document_and_converts_page(
    tmp_path: Path,
) -> None:
    _application()
    document = _sample_documents()[0]
    service = _FakeDocumentLibraryService([document])
    service.resolved_path = _write_pdf(tmp_path / "three-pages.pdf", pages=3)
    page = DocumentLibraryPage(service)
    page.search_input.setText("sin coincidencias")
    assert page.table.rowCount() == 0

    page._show_content_search_result(document.document_id, 2)
    _application().processEvents()

    assert page.search_input.text() == ""
    assert page._selected_document_id() == document.document_id
    assert page._loaded_document_id == document.document_id
    assert page.pdf_view.pageNavigator().currentPage() == 1
    assert service.resolved_ids == [document.document_id]


def test_content_pdf_result_clamps_page_to_pdf_range(tmp_path: Path) -> None:
    _application()
    document = _sample_documents()[0]
    service = _FakeDocumentLibraryService([document])
    service.resolved_path = _write_pdf(tmp_path / "two-pages.pdf", pages=2)
    page = DocumentLibraryPage(service)

    page._show_content_search_result(document.document_id, 99)
    _application().processEvents()

    assert page.pdf_view.pageNavigator().currentPage() == 1


def test_content_markdown_result_is_selected_without_loading_pdf() -> None:
    _application()
    document = _document(
        "e" * 64,
        "Calidad/Normas/Manual.md",
        area="Calidad",
        category="Normas",
        extension=".md",
    )
    service = _FakeDocumentLibraryService([document])
    page = DocumentLibraryPage(service)

    page._show_content_search_result(document.document_id, 1)

    assert page._selected_document_id() == document.document_id
    assert page._loaded_document_id is None
    assert service.resolved_ids == []
    assert "solo para PDF" in page.preview_status_label.text()


def test_content_result_for_disappeared_document_uses_safe_existing_state() -> None:
    _application()
    page = DocumentLibraryPage(_FakeDocumentLibraryService([]))

    page._show_content_search_result("f" * 64, 1)

    assert page._loaded_document_id is None
    assert "ya no está disponible" in page.preview_status_label.text()


def test_question_answer_button_opens_only_one_injected_dialog_instance() -> None:
    _application()
    library = _FakeDocumentLibraryService(_sample_documents())
    question_service = _FakeQuestionAnswerService()
    page = DocumentLibraryPage(
        library,
        question_answer_service=question_service,  # type: ignore[arg-type]
    )

    page.question_answer_button.click()
    _application().processEvents()
    first_dialog = page._question_answer_dialog
    page.question_answer_button.click()
    _application().processEvents()

    assert first_dialog is not None
    assert page._question_answer_dialog is first_dialog
    assert first_dialog.isVisible()
    assert first_dialog._question_answer_service is question_service
    first_dialog.close()
    _application().processEvents()


def test_default_question_service_reuses_page_content_index_and_database(
    tmp_path: Path,
) -> None:
    _application()
    library_dir = tmp_path / "library"
    library_dir.mkdir()
    database = tmp_path / "data" / "document_library.sqlite"
    library = DocumentLibraryService(library_dir, database)
    page = DocumentLibraryPage(library)

    page.question_answer_button.click()
    _application().processEvents()

    assert page._question_answer_service is not None
    assert page._content_index_service is not None
    assert (
        page._question_answer_service.content_index_service
        is page._content_index_service
    )
    assert page._content_index_service.database_path == database.resolve()
    assert page._question_answer_dialog is not None
    page._question_answer_dialog.close()
    _application().processEvents()


def test_search_and_question_dialogs_share_semantic_service_and_database(
    tmp_path: Path,
) -> None:
    _application()
    library_dir = tmp_path / "library"
    library_dir.mkdir()
    database = tmp_path / "data" / "document_library.sqlite"
    library = DocumentLibraryService(library_dir, database)
    page = DocumentLibraryPage(library)

    page.content_search_button.click()
    _application().processEvents()
    page.question_answer_button.click()
    _application().processEvents()

    assert page._content_search_dialog is not None
    assert page._question_answer_service is not None
    semantic = page._semantic_index_service
    assert semantic is not None
    assert page._content_search_dialog._semantic_service is semantic
    assert (
        page._question_answer_service.retrieval_service.semantic_index_service
        is semantic
    )
    assert semantic.database_path == database.resolve()
    assert semantic.content_index_service is page._content_index_service

    page._content_search_dialog.close()
    page._question_answer_dialog.close()
    _application().processEvents()


def test_question_source_signal_reuses_pdf_navigation(tmp_path: Path) -> None:
    _application()
    document = _sample_documents()[0]
    library = _FakeDocumentLibraryService([document])
    library.resolved_path = _write_pdf(tmp_path / "three-pages-qa.pdf", pages=3)
    page = DocumentLibraryPage(
        library,
        question_answer_service=_FakeQuestionAnswerService(),  # type: ignore[arg-type]
    )
    page.question_answer_button.click()
    _application().processEvents()
    dialog = page._question_answer_dialog
    assert dialog is not None

    dialog.source_requested.emit(document.document_id, 2)
    _application().processEvents()

    assert page._selected_document_id() == document.document_id
    assert page._loaded_document_id == document.document_id
    assert page.pdf_view.pageNavigator().currentPage() == 1
    dialog.close()


def test_technical_consultant_button_opens_single_dialog() -> None:
    _application()
    service = type(
        "Consultant",
        (),
        {"consult": lambda self, _question: None},
    )()
    page = DocumentLibraryPage(
        _FakeDocumentLibraryService(),
        technical_consultant_service=service,  # type: ignore[arg-type]
    )

    assert page.technical_consultant_button.text() == "Consultor técnico"
    page.technical_consultant_button.click()
    _application().processEvents()
    first_dialog = page._technical_consultant_dialog
    assert first_dialog is not None

    page.technical_consultant_button.click()
    _application().processEvents()
    assert page._technical_consultant_dialog is first_dialog
    first_dialog.close()
    _application().processEvents()
    assert page._technical_consultant_dialog is None


def test_technical_consultant_source_reuses_pdf_navigation(tmp_path: Path) -> None:
    _application()
    document = _sample_documents()[0]
    library = _FakeDocumentLibraryService([document])
    library.resolved_path = _write_pdf(tmp_path / "technical-source.pdf", pages=2)
    service = type(
        "Consultant",
        (),
        {"consult": lambda self, _question: None},
    )()
    page = DocumentLibraryPage(
        library,
        technical_consultant_service=service,  # type: ignore[arg-type]
    )
    page.technical_consultant_button.click()
    _application().processEvents()
    dialog = page._technical_consultant_dialog
    assert dialog is not None

    dialog.source_requested.emit(document.document_id, 2)
    _application().processEvents()

    assert page._selected_document_id() == document.document_id
    assert page._loaded_document_id == document.document_id
    assert page.pdf_view.pageNavigator().currentPage() == 1
    dialog.close()

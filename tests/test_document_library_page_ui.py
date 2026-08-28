from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMessageBox

import app.ui.widgets.document_library_page as page_module
from app.services.document_library_service import (
    DocumentLibraryItem,
    DocumentLibraryScanResult,
    DocumentNotFoundError,
)
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


class _FakeDocumentLibraryService:
    def __init__(self, documents: list[DocumentLibraryItem] | None = None) -> None:
        self.documents = documents or []
        self.available = True
        self.resolved_ids: list[str] = []
        self.resolve_error: Exception | None = None
        self.resolved_path = Path("C:/safe/document.pdf")

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
        return self.resolved_path


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


def test_open_uses_selected_identifier_and_safe_resolved_path(monkeypatch) -> None:
    _application()
    service = _FakeDocumentLibraryService(_sample_documents()[:1])
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

    assert service.resolved_ids == ["a" * 64]
    assert len(opened_urls) == 1
    assert opened_urls[0].toLocalFile().replace("\\", "/").endswith(
        "C:/safe/document.pdf"
    )


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

    assert service.resolved_ids == ["a" * 64]
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

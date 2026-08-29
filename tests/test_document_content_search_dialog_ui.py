from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.services.document_content_index_service import (
    DocumentContentFTSUnavailableError,
    DocumentContentIndexResult,
    DocumentContentSearchResult,
)
from app.services.document_library_service import DocumentLibraryItem
from app.ui.widgets.document_content_search_dialog import (
    DocumentContentSearchDialog,
)


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        _application().processEvents()
        QTest.qWait(5)
    assert predicate()


def _document(
    document_id: str,
    name: str,
    area: str,
    category: str,
    extension: str = ".pdf",
) -> DocumentLibraryItem:
    return DocumentLibraryItem(
        document_id=document_id,
        relative_path=f"{area}/{category}/{name}",
        name=name,
        area=area,
        category=category,
        extension=extension,
        size_bytes=100,
        modified_at="2026-08-29T10:00:00+00:00",
        indexed_at="2026-08-29T10:00:00+00:00",
        active=True,
    )


class _FakeLibraryService:
    def __init__(self) -> None:
        self.documents = [
            _document("a" * 64, "Primero.pdf", "Calidad", "Fichas"),
            _document("b" * 64, "Segundo.md", "Calidad", "Normas", ".md"),
            _document("c" * 64, "Tercero.pdf", "Ventas", "Fichas"),
        ]

    def list_documents(self, *, area=None, active=True, **_filters):
        assert active is True
        rows = list(self.documents)
        if area:
            rows = [item for item in rows if item.area == area]
        return rows


@dataclass
class _UpdateBehavior:
    wait_for_cancel: bool = False
    error: Exception | None = None


class _FakeContentService:
    def __init__(self, library_service: _FakeLibraryService) -> None:
        self.library_service = library_service
        self.search_calls: list[dict[str, object]] = []
        self.search_results: list[DocumentContentSearchResult] = []
        self.search_error: Exception | None = None
        self.update_behavior = _UpdateBehavior()
        self.update_thread_id: int | None = None
        self.cancel_observed = False

    def search(self, query, *, area=None, category=None, limit=20):
        self.search_calls.append(
            {"query": query, "area": area, "category": category, "limit": limit}
        )
        if self.search_error is not None:
            raise self.search_error
        return list(self.search_results)

    def update_index(self, *, progress_callback, cancellation_callback):
        self.update_thread_id = threading.get_ident()
        if self.update_behavior.error is not None:
            raise self.update_behavior.error
        progress_callback(1, 3, "a" * 64)
        if self.update_behavior.wait_for_cancel:
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if cancellation_callback():
                    self.cancel_observed = True
                    return DocumentContentIndexResult(candidates=3, cancelled=2)
                time.sleep(0.005)
        progress_callback(3, 3, "c" * 64)
        return DocumentContentIndexResult(
            candidates=3,
            indexed=1,
            unchanged=1,
            no_text=1,
            failed=0,
            errors=("detalle de prueba",),
        )


def _result(
    document_id: str,
    name: str,
    page: int,
    fragment: str,
    *,
    area: str = "Calidad",
    category: str = "Fichas",
) -> DocumentContentSearchResult:
    return DocumentContentSearchResult(
        document_id=document_id,
        name=name,
        relative_path=f"{area}/{category}/{name}",
        area=area,
        category=category,
        page_number=page,
        fragment=fragment,
        score=-1.0,
    )


def _dialog() -> tuple[DocumentContentSearchDialog, _FakeContentService]:
    _application()
    library = _FakeLibraryService()
    content = _FakeContentService(library)
    return DocumentContentSearchDialog(library, content), content


def test_empty_query_does_not_call_search_service() -> None:
    dialog, content = _dialog()

    dialog.search_button.click()

    assert content.search_calls == []
    assert "Introduce una consulta" in dialog.empty_state_label.text()


def test_search_button_sends_query_filters_and_limit_and_keeps_service_order() -> None:
    dialog, content = _dialog()
    content.search_results = [
        _result("b" * 64, "Segundo.md", 1, "<b>texto</b> [marca]"),
        _result("a" * 64, "Primero.pdf", 4, "otro fragmento"),
    ]
    dialog.query_input.setText("harina especial")
    dialog.area_filter.setCurrentIndex(dialog.area_filter.findData("Calidad"))
    dialog.category_filter.setCurrentIndex(dialog.category_filter.findData("Fichas"))

    dialog.search_button.click()

    assert content.search_calls == [
        {
            "query": "harina especial",
            "area": "Calidad",
            "category": "Fichas",
            "limit": 50,
        }
    ]
    assert [dialog.table.item(row, 0).text() for row in range(2)] == [
        "Segundo.md",
        "Primero.pdf",
    ]
    assert dialog.table.item(0, 3).text() == "1"
    assert dialog.table.item(0, 4).text() == "<b>texto</b> [marca]"
    assert dialog.counter_label.text() == "2 resultados"


def test_enter_executes_search() -> None:
    dialog, content = _dialog()
    dialog.query_input.setText("trigo")

    dialog.query_input.returnPressed.emit()

    assert content.search_calls[0]["query"] == "trigo"


def test_area_change_recalculates_categories_from_catalog() -> None:
    dialog, _content = _dialog()

    dialog.area_filter.setCurrentIndex(dialog.area_filter.findData("Ventas"))

    assert dialog.category_filter.count() == 2
    assert dialog.category_filter.itemData(1) == "Fichas"


def test_no_results_shows_empty_state() -> None:
    dialog, _content = _dialog()
    dialog.query_input.setText("inexistente")

    dialog.search_button.click()

    assert dialog.table.rowCount() == 0
    assert not dialog.empty_state_label.isHidden()
    assert "No hay coincidencias" in dialog.empty_state_label.text()


def test_fts5_error_is_shown_in_comprehensible_language() -> None:
    dialog, content = _dialog()
    content.search_error = DocumentContentFTSUnavailableError("technical")
    dialog.query_input.setText("trigo")

    dialog.search_button.click()

    assert "SQLite no incluye FTS5" in dialog.empty_state_label.text()


def test_index_update_runs_off_main_thread_reports_progress_and_recovers_buttons() -> None:
    dialog, content = _dialog()
    main_thread_id = threading.get_ident()

    dialog.update_index_button.click()
    assert not dialog.update_index_button.isEnabled()
    assert dialog.cancel_button.isEnabled()
    _wait_until(lambda: dialog._worker is None)

    assert content.update_thread_id != main_thread_id
    assert dialog.update_index_button.isEnabled()
    assert dialog.search_button.isEnabled()
    assert not dialog.cancel_button.isEnabled()
    assert "3 candidatos" in dialog.index_status_label.text()
    assert "1 indexados" in dialog.index_status_label.text()
    assert "1 sin cambios" in dialog.index_status_label.text()
    assert "1 sin texto" in dialog.index_status_label.text()
    assert dialog.index_status_label.toolTip() == "detalle de prueba"


def test_index_progress_signal_updates_processed_and_candidate_counts() -> None:
    dialog, content = _dialog()
    progress_messages: list[str] = []
    original = dialog._index_progress

    def capture(processed, candidates, document_id):
        original(processed, candidates, document_id)
        progress_messages.append(dialog.index_status_label.text())

    dialog._index_progress = capture  # type: ignore[method-assign]
    dialog.update_index_button.click()
    _wait_until(lambda: dialog._worker is None)

    assert content.update_thread_id is not None
    assert any("1 / 3" in message for message in progress_messages)
    assert any("3 / 3" in message for message in progress_messages)


def test_cancel_is_cooperative_and_summary_reports_cancelled_documents() -> None:
    dialog, content = _dialog()
    content.update_behavior.wait_for_cancel = True

    dialog.update_index_button.click()
    _wait_until(lambda: content.update_thread_id is not None)
    dialog.cancel_button.click()
    _wait_until(lambda: dialog._worker is None)

    assert content.cancel_observed
    assert "2 cancelados" in dialog.index_status_label.text()
    assert dialog.update_index_button.isEnabled()


def test_buttons_recover_after_worker_exception() -> None:
    dialog, content = _dialog()
    content.update_behavior.error = RuntimeError("fallo simulado")

    dialog.update_index_button.click()
    _wait_until(lambda: dialog._worker is None)

    assert dialog.update_index_button.isEnabled()
    assert dialog.search_button.isEnabled()
    assert not dialog.cancel_button.isEnabled()
    assert "fallo simulado" in dialog.index_status_label.text()


def test_double_click_emits_only_identifier_and_one_based_page() -> None:
    dialog, content = _dialog()
    content.search_results = [
        _result("a" * 64, "Primero.pdf", 7, "coincidencia")
    ]
    emitted: list[tuple[str, int]] = []
    dialog.document_requested.connect(lambda document_id, page: emitted.append((document_id, page)))
    dialog.query_input.setText("texto")
    dialog.search_button.click()
    dialog.table.selectRow(0)

    dialog.table.itemDoubleClicked.emit(dialog.table.item(0, 0))

    assert emitted == [("a" * 64, 7)]
    assert all("/" not in value[0] and "\\" not in value[0] for value in emitted)


def test_show_document_button_requires_selection() -> None:
    dialog, content = _dialog()
    content.search_results = [_result("a" * 64, "Primero.pdf", 2, "texto")]
    dialog.query_input.setText("texto")
    dialog.search_button.click()

    assert not dialog.show_document_button.isEnabled()
    dialog.table.selectRow(0)
    assert dialog.show_document_button.isEnabled()


def test_clear_resets_query_filters_and_results() -> None:
    dialog, content = _dialog()
    content.search_results = [_result("a" * 64, "Primero.pdf", 2, "texto")]
    dialog.query_input.setText("texto")
    dialog.area_filter.setCurrentIndex(dialog.area_filter.findData("Calidad"))
    dialog.search_button.click()

    dialog.clear_button.click()

    assert dialog.query_input.text() == ""
    assert dialog.area_filter.currentData() == ""
    assert dialog.category_filter.currentData() == ""
    assert dialog.table.rowCount() == 0


def test_ui_has_no_sqlite_access_and_backend_service_has_no_pyside_import() -> None:
    ui_source = Path(
        "app/ui/widgets/document_content_search_dialog.py"
    ).read_text(encoding="utf-8")
    service_source = Path(
        "app/services/document_content_index_service.py"
    ).read_text(encoding="utf-8")

    assert "sqlite3" not in ui_source
    assert "PySide6" not in service_source
    assert "IREKS-Servidor" not in ui_source

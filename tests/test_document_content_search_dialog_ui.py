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
from app.services.document_semantic_index_service import (
    DocumentSemanticIndexResult,
    DocumentSemanticIndexStatus,
)
from app.services.local_embedding_service import LocalEmbeddingResult
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


class _FakeEmbeddingService:
    def __init__(self) -> None:
        self.model = "embeddinggemma"
        self.calls = []
        self.ok = True
        self.message = ""
        self.thread_id = None

    def embed(self, texts):
        self.thread_id = threading.get_ident()
        self.calls.append(list(texts))
        if not self.ok:
            return LocalEmbeddingResult(
                False, model=self.model, message=self.message
            )
        return LocalEmbeddingResult(True, ((1.0, 0.0),), self.model, 2)


class _FakeSemanticService:
    def __init__(self, content_service) -> None:
        self.content_index_service = content_service
        self.embedding_service = _FakeEmbeddingService()
        self.status = DocumentSemanticIndexStatus(
            configured_model="embeddinggemma",
            content_documents=3,
            requires_reindex=True,
        )
        self.update_calls = 0
        self.update_thread_id = None
        self.cancel_observed = False
        self.wait_for_cancel = False
        self.error = None

    def get_status(self):
        return self.status

    def update_index(self, *, progress_callback, cancellation_callback):
        self.update_calls += 1
        self.update_thread_id = threading.get_ident()
        if self.error:
            raise self.error
        progress_callback(1, 3, "a" * 64)
        if self.wait_for_cancel:
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if cancellation_callback():
                    self.cancel_observed = True
                    return DocumentSemanticIndexResult(candidates=3, cancelled=2)
                time.sleep(0.005)
        progress_callback(3, 3, "c" * 64)
        self.status = DocumentSemanticIndexStatus(
            configured_model="embeddinggemma",
            indexed_documents=3,
            available_chunks=7,
            content_documents=3,
            available=True,
        )
        return DocumentSemanticIndexResult(
            candidates=3,
            indexed=2,
            unchanged=1,
            chunks_generated=7,
            errors=("detalle seguro",),
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
    semantic = _FakeSemanticService(content)
    content.semantic_service = semantic
    return DocumentContentSearchDialog(
        library, content, semantic_service=semantic
    ), content


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


def test_semantic_section_shows_pending_available_and_incompatible_states() -> None:
    dialog, content = _dialog()
    semantic = content.semantic_service

    assert (
        dialog.semantic_index_title_label.text()
        == "2. Actualizar índice semántico"
    )
    assert dialog.update_semantic_index_button.text() == "Actualizar índice semántico"
    assert "pendiente" in dialog.semantic_status_label.text()
    assert "embeddinggemma" in dialog.semantic_model_label.text()

    semantic.status = DocumentSemanticIndexStatus(
        configured_model="embeddinggemma",
        indexed_documents=2,
        available_chunks=8,
        content_documents=2,
        available=True,
    )
    dialog._refresh_semantic_status()
    assert "2 documentos y 8 fragmentos" in dialog.semantic_status_label.text()

    semantic.status = DocumentSemanticIndexStatus(
        configured_model="new-model",
        other_model_documents=2,
        content_documents=2,
        requires_reindex=True,
    )
    dialog._refresh_semantic_status()
    assert "otro modelo" in dialog.semantic_status_label.text()
    assert "new-model" in dialog.semantic_status_label.text()


def test_semantic_update_preflight_and_index_run_outside_main_thread() -> None:
    dialog, content = _dialog()
    semantic = content.semantic_service
    main_thread_id = threading.get_ident()
    progress_messages = []
    original = dialog._semantic_index_progress

    def capture(*args):
        original(*args)
        progress_messages.append(dialog.semantic_progress_label.text())

    dialog._semantic_index_progress = capture
    dialog.update_semantic_index_button.click()
    assert not dialog.update_index_button.isEnabled()
    assert not dialog.search_button.isEnabled()
    assert dialog.semantic_cancel_button.isEnabled()
    _wait_until(lambda: dialog._worker is None)

    assert semantic.embedding_service.thread_id != main_thread_id
    assert semantic.update_thread_id != main_thread_id
    assert semantic.embedding_service.calls == [
        ["Prueba de búsqueda documental de GestionIREKS."]
    ]
    assert any("1 / 3" in message for message in progress_messages)
    assert "3 candidatos" in dialog.semantic_progress_label.text()
    assert "7 fragmentos" in dialog.semantic_progress_label.text()
    assert "disponible" in dialog.semantic_status_label.text()
    assert dialog.update_index_button.isEnabled()
    assert dialog.update_semantic_index_button.isEnabled()
    assert dialog.search_button.isEnabled()
    assert not dialog.semantic_cancel_button.isEnabled()


def test_semantic_preflight_failure_does_not_update_or_show_vector_or_path() -> None:
    dialog, content = _dialog()
    semantic = content.semantic_service
    semantic.embedding_service.ok = False
    semantic.embedding_service.message = (
        "El modelo no está instalado; detalle C:/secret/vector.bin"
    )

    dialog.update_semantic_index_button.click()
    _wait_until(lambda: dialog._worker is None)

    assert semantic.update_calls == 0
    assert "embeddinggemma" in dialog.semantic_progress_label.text()
    assert "no está instalado" in dialog.semantic_progress_label.text()
    assert "C:/secret" not in dialog.semantic_progress_label.text()
    assert "vector.bin" not in dialog.semantic_progress_label.text()
    assert dialog.update_semantic_index_button.isEnabled()
    assert dialog.search_button.isEnabled()


def test_missing_semantic_model_fails_before_preflight_and_update() -> None:
    dialog, content = _dialog()
    semantic = content.semantic_service
    semantic.embedding_service.model = ""

    dialog.update_semantic_index_button.click()
    _wait_until(lambda: dialog._worker is None)

    assert semantic.embedding_service.calls == []
    assert semantic.update_calls == 0
    assert "modelo de embeddings configurado" in dialog.semantic_progress_label.text()
    assert dialog.update_semantic_index_button.isEnabled()
    assert dialog.search_button.isEnabled()


def test_semantic_cancel_is_cooperative_and_operations_cannot_overlap() -> None:
    dialog, content = _dialog()
    semantic = content.semantic_service
    semantic.wait_for_cancel = True

    dialog.update_semantic_index_button.click()
    _wait_until(lambda: semantic.update_thread_id is not None)
    assert not dialog.update_index_button.isEnabled()
    dialog.update_index_button.click()
    assert content.update_thread_id is None
    dialog.semantic_cancel_button.click()
    _wait_until(lambda: dialog._worker is None)

    assert semantic.cancel_observed
    assert "2 cancelados" in dialog.semantic_progress_label.text()
    assert dialog.update_index_button.isEnabled()
    assert dialog.update_semantic_index_button.isEnabled()


def test_semantic_worker_failure_restores_all_controls() -> None:
    dialog, content = _dialog()
    semantic = content.semantic_service
    semantic.error = RuntimeError("fallo semántico")

    dialog.update_semantic_index_button.click()
    _wait_until(lambda: dialog._worker is None)

    assert "fallo semántico" in dialog.semantic_progress_label.text()
    assert dialog.update_index_button.isEnabled()
    assert dialog.update_semantic_index_button.isEnabled()
    assert dialog.search_button.isEnabled()
    assert not dialog.semantic_cancel_button.isEnabled()


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

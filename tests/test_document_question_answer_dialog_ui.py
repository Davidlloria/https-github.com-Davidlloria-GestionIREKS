from __future__ import annotations

import ast
import os
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.services.document_library_service import (
    DocumentLibraryItem,
    DocumentLibraryService,
)
from app.services.document_question_answer_service import (
    MAX_QUESTION_CHARS,
    NO_INFORMATION_ANSWER,
    DocumentAnswerSource,
    DocumentQuestionAnswerResult,
)
from app.ui.widgets.document_question_answer_dialog import (
    DocumentQuestionAnswerDialog,
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
) -> DocumentLibraryItem:
    return DocumentLibraryItem(
        document_id=document_id,
        relative_path=f"{area}/{category}/{name}",
        name=name,
        area=area,
        category=category,
        extension=Path(name).suffix,
        size_bytes=100,
        modified_at="2026-08-29T10:00:00+00:00",
        indexed_at="2026-08-29T10:00:00+00:00",
        active=True,
    )


class _FakeLibraryService:
    def __init__(self) -> None:
        self.documents = [
            _document("a" * 64, "Manual.pdf", "Calidad", "Manuales"),
            _document("b" * 64, "Norma.md", "Calidad", "Normas"),
            _document("c" * 64, "Tarifa.pdf", "Ventas", "Tarifas"),
        ]

    def list_documents(self, *, area=None, active=True, **_filters):
        assert active is True
        rows = list(self.documents)
        if area:
            rows = [item for item in rows if item.area == area]
        return rows


class _FakeQuestionAnswerService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.thread_id: int | None = None
        self.result = _valid_result()
        self.error: Exception | None = None
        self.block = False
        self.started = threading.Event()
        self.release = threading.Event()

    def answer(self, question, *, area=None, category=None):
        self.thread_id = threading.get_ident()
        self.calls.append(
            {"question": question, "area": area, "category": category}
        )
        self.started.set()
        if self.block:
            self.release.wait(timeout=2)
        if self.error is not None:
            raise self.error
        return self.result


def _source(
    source_id: str,
    document_id: str,
    name: str,
    page: int,
    fragment: str,
) -> DocumentAnswerSource:
    return DocumentAnswerSource(
        source_id=source_id,
        document_id=document_id,
        name=name,
        relative_path=f"Calidad/Manuales/{name}",
        area="Calidad",
        category="Manuales",
        page_number=page,
        fragment=fragment,
    )


def _valid_result() -> DocumentQuestionAnswerResult:
    return DocumentQuestionAnswerResult(
        True,
        "La respuesta se apoya en el manual.",
        "Respuesta generada con IA local y fuentes documentales verificadas.",
        True,
        (
            _source("S1", "a" * 64, "Manual.pdf", 2, "Primer fragmento"),
            _source("S2", "b" * 64, "Norma.md", 1, "Segundo fragmento"),
        ),
    )


def _dialog() -> tuple[DocumentQuestionAnswerDialog, _FakeQuestionAnswerService]:
    _application()
    library = _FakeLibraryService()
    service = _FakeQuestionAnswerService()
    return DocumentQuestionAnswerDialog(library, service), service  # type: ignore[arg-type]


def test_default_services_share_library_database_and_content_index(tmp_path: Path) -> None:
    _application()
    library_dir = tmp_path / "library"
    library_dir.mkdir()
    database = tmp_path / "data" / "document_library.sqlite"
    library = DocumentLibraryService(library_dir, database)

    dialog = DocumentQuestionAnswerDialog(library)

    content = dialog._question_answer_service.content_index_service
    assert content.library_service is library
    assert content.database_path == library.database_path == database.resolve()


def test_empty_question_does_not_start_worker() -> None:
    dialog, service = _dialog()

    dialog.ask_button.click()

    assert dialog._worker is None
    assert service.calls == []
    assert "Escribe una pregunta" in dialog.status_label.text()


def test_overlong_question_does_not_start_worker_and_counter_shows_limit() -> None:
    dialog, service = _dialog()
    dialog.question_input.setPlainText("x" * (MAX_QUESTION_CHARS + 1))

    dialog.ask_button.click()

    assert dialog._worker is None
    assert service.calls == []
    assert str(MAX_QUESTION_CHARS + 1) in dialog.question_counter_label.text()
    assert "no puede superar" in dialog.status_label.text()


def test_question_filters_and_call_run_outside_main_thread() -> None:
    dialog, service = _dialog()
    main_thread_id = threading.get_ident()
    dialog.question_input.setPlainText("¿Qué indica el manual?")
    dialog.area_filter.setCurrentIndex(dialog.area_filter.findData("Calidad"))
    dialog.category_filter.setCurrentIndex(
        dialog.category_filter.findData("Manuales")
    )

    dialog.ask_button.click()
    _wait_until(lambda: dialog._worker is None)

    assert service.thread_id != main_thread_id
    assert service.calls == [
        {
            "question": "¿Qué indica el manual?",
            "area": "Calidad",
            "category": "Manuales",
        }
    ]


def test_controls_are_disabled_while_query_runs_and_restored_after_success() -> None:
    dialog, service = _dialog()
    service.block = True
    dialog.question_input.setPlainText("consulta")

    dialog.ask_button.click()
    _wait_until(service.started.is_set)

    assert not dialog.question_input.isEnabled()
    assert not dialog.area_filter.isEnabled()
    assert not dialog.category_filter.isEnabled()
    assert not dialog.ask_button.isEnabled()
    assert not dialog.close_button.isEnabled()
    assert "Consultando el índice" in dialog.status_label.text()
    service.release.set()
    _wait_until(lambda: dialog._worker is None)
    assert dialog.question_input.isEnabled()
    assert dialog.area_filter.isEnabled()
    assert dialog.ask_button.isEnabled()
    assert dialog.close_button.isEnabled()


def test_controls_are_restored_after_worker_exception() -> None:
    dialog, service = _dialog()
    service.error = RuntimeError("fallo simulado")
    dialog.question_input.setPlainText("consulta")

    dialog.ask_button.click()
    _wait_until(lambda: dialog._worker is None)

    assert dialog.ask_button.isEnabled()
    assert dialog.question_input.isEnabled()
    assert "fallo simulado" in dialog.status_label.text()
    assert dialog.answer_output.toPlainText() == ""


def test_valid_ai_answer_and_indicator_are_visible_as_plain_text() -> None:
    dialog, _service = _dialog()
    result = _valid_result()
    result = DocumentQuestionAnswerResult(
        result.ok,
        "**Respuesta** <b>sin interpretar</b>",
        result.message,
        result.used_ai,
        result.sources,
    )

    dialog._question_succeeded(result)

    assert dialog.answer_output.toPlainText() == "**Respuesta** <b>sin interpretar</b>"
    assert dialog.ai_indicator_label.text() == "IA local · fuentes verificadas"
    assert "fuentes verificadas" in dialog.status_label.text()


def test_no_information_result_is_visible_without_ai_or_sources() -> None:
    dialog, _service = _dialog()
    result = DocumentQuestionAnswerResult(
        True,
        NO_INFORMATION_ANSWER,
        "La búsqueda no recuperó páginas con texto utilizable.",
        False,
        (),
    )

    dialog._question_succeeded(result)

    assert dialog.answer_output.toPlainText() == NO_INFORMATION_ANSWER
    assert dialog.ai_indicator_label.text() == "Sin uso de IA local"
    assert dialog.sources_table.rowCount() == 0
    assert "actualiza el índice" in dialog.status_label.text()


def test_disabled_ai_shows_configuration_instruction_without_old_result() -> None:
    dialog, _service = _dialog()
    dialog._question_succeeded(_valid_result())

    dialog._question_succeeded(
        DocumentQuestionAnswerResult(
            False,
            "",
            "La IA local no está activada. Actívala en Configuración > API.",
        )
    )

    assert dialog.answer_output.toPlainText() == ""
    assert dialog.sources_table.rowCount() == 0
    assert dialog.ai_indicator_label.text() == ""
    assert "Configuración > API" in dialog.status_label.text()


def test_failed_result_clears_previous_answer_and_sources() -> None:
    dialog, _service = _dialog()
    dialog._question_succeeded(_valid_result())
    assert dialog.sources_table.rowCount() == 2

    dialog._question_succeeded(
        DocumentQuestionAnswerResult(False, "", "Respuesta inválida")
    )

    assert dialog.answer_output.toPlainText() == ""
    assert dialog.sources_table.rowCount() == 0
    assert dialog.status_label.text() == "Respuesta inválida"


def test_sources_keep_order_page_and_plain_fragment() -> None:
    dialog, _service = _dialog()
    result = _valid_result()
    unsafe_markup = _source(
        "S3", "c" * 64, "Tercero.pdf", 7, "<b>texto</b> **markdown**"
    )
    result = DocumentQuestionAnswerResult(
        True,
        result.answer,
        result.message,
        True,
        (*result.sources, unsafe_markup),
    )

    dialog._question_succeeded(result)

    assert [dialog.sources_table.item(row, 0).text() for row in range(3)] == [
        "S1",
        "S2",
        "S3",
    ]
    assert dialog.sources_table.item(2, 4).text() == "7"
    assert dialog.sources_table.item(2, 5).text() == "<b>texto</b> **markdown**"


def test_show_source_button_requires_single_selection() -> None:
    dialog, _service = _dialog()
    dialog._question_succeeded(_valid_result())

    assert not dialog.show_source_button.isEnabled()
    dialog.sources_table.selectRow(0)
    assert dialog.show_source_button.isEnabled()


def test_double_click_emits_only_document_identifier_and_page() -> None:
    dialog, _service = _dialog()
    emitted: list[tuple[str, int]] = []
    dialog.source_requested.connect(
        lambda document_id, page: emitted.append((document_id, page))
    )
    dialog._question_succeeded(_valid_result())
    dialog.sources_table.selectRow(1)

    dialog.sources_table.itemDoubleClicked.emit(dialog.sources_table.item(1, 0))

    assert emitted == [("b" * 64, 1)]
    assert all("/" not in document_id and "\\" not in document_id for document_id, _ in emitted)


def test_dialog_cannot_close_or_be_destroyed_while_worker_is_active() -> None:
    dialog, service = _dialog()
    service.block = True
    dialog.question_input.setPlainText("consulta larga")
    dialog.show()
    dialog.ask_button.click()
    _wait_until(service.started.is_set)

    dialog.close()
    _application().processEvents()

    assert dialog.isVisible()
    assert dialog._worker is not None and dialog._worker.isRunning()
    assert "Espera a que finalice" in dialog.status_label.text()
    service.release.set()
    _wait_until(lambda: dialog._worker is None)
    dialog.close()


def test_ui_has_no_sqlite_access_and_tests_do_not_import_real_local_ai() -> None:
    ui_source = Path(
        "app/ui/widgets/document_question_answer_dialog.py"
    ).read_text(encoding="utf-8")
    test_source = Path(__file__).read_text(encoding="utf-8")
    imports = [
        node.module
        for node in ast.walk(ast.parse(test_source))
        if isinstance(node, ast.ImportFrom)
    ]

    assert "sqlite3" not in ui_source
    assert "app.services.local_ai_service" not in imports
    assert "IREKS" + "-Servidor" not in test_source

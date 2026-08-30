from __future__ import annotations

import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.services.technical_consultant_service import (
    TechnicalConsultantProduct,
    TechnicalConsultantResult,
)
from app.services.technical_product_comparison_service import (
    TechnicalProductProfileSource,
)
from app.services.technical_product_decision_service import TechnicalRequirement
from app.ui.widgets.technical_consultant_dialog import (
    MAX_TECHNICAL_QUESTION_CHARS,
    TechnicalConsultantDialog,
)


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    app = _application()
    while not predicate():
        app.processEvents()
        if time.monotonic() >= deadline:
            raise AssertionError("La condición esperada no se cumplió.")
        time.sleep(0.01)


class _FakeConsultantService:
    def __init__(self, result: TechnicalConsultantResult) -> None:
        self.result = result
        self.calls: list[str] = []
        self.thread_id: int | None = None
        self.started = threading.Event()
        self.release = threading.Event()
        self.block = False
        self.error: Exception | None = None

    def consult(self, question: str) -> TechnicalConsultantResult:
        self.calls.append(question)
        self.thread_id = threading.get_ident()
        self.started.set()
        if self.block:
            self.release.wait(timeout=2)
        if self.error is not None:
            raise self.error
        return self.result


def _source(
    source_id: str = "P1-S1",
    document_id: str = "a" * 64,
) -> TechnicalProductProfileSource:
    return TechnicalProductProfileSource(
        source_id=source_id,
        document_id=document_id,
        name="PREBACK.pdf",
        relative_path="CALIDAD/FICHAS TECNICAS/IREKS/PREBACK.pdf",
        page_number=1,
    )


def _product() -> TechnicalConsultantProduct:
    return TechnicalConsultantProduct(
        product_key="preback",
        product_name="PREBACK",
        status="complementary",
        application="Mejorante para pan precocido",
        dosage="10 a 30 g por kg de harina",
        reason="Confirma precocción, pero no congelación.",
        source_ids=("P1-S1",),
    )


def _technical_result() -> TechnicalConsultantResult:
    return TechnicalConsultantResult(
        ok=True,
        answer="No hay una solución completa documentada.",
        message="Respuesta redactada con IA local y decisiones verificadas.",
        requirements=(
            TechnicalRequirement("precooked", "precocción"),
            TechnicalRequirement("freezing", "congelación"),
        ),
        products=(_product(),),
        sources=(_source(),),
        used_ai=True,
        retrieval_mode="hybrid",
    )


def _dialog(
    result: TechnicalConsultantResult | None = None,
) -> tuple[TechnicalConsultantDialog, _FakeConsultantService]:
    _application()
    service = _FakeConsultantService(result or _technical_result())
    return TechnicalConsultantDialog(service), service  # type: ignore[arg-type]


def test_empty_and_oversized_questions_do_not_start_worker() -> None:
    dialog, service = _dialog()

    dialog.ask_button.click()
    assert service.calls == []
    assert "Escribe" in dialog.status_label.text()

    dialog.question_input.setPlainText("x" * (MAX_TECHNICAL_QUESTION_CHARS + 1))
    dialog.ask_button.click()
    assert service.calls == []
    assert "no puede superar" in dialog.status_label.text()


def test_consultation_runs_outside_main_thread() -> None:
    dialog, service = _dialog()
    main_thread_id = threading.get_ident()
    dialog.question_input.setPlainText("pan precocido y congelado")

    dialog.ask_button.click()
    _wait_until(lambda: dialog._worker is None)

    assert service.calls == ["pan precocido y congelado"]
    assert service.thread_id != main_thread_id


def test_controls_are_disabled_during_consultation_and_restored() -> None:
    dialog, service = _dialog()
    service.block = True
    dialog.question_input.setPlainText("consulta técnica")

    dialog.ask_button.click()
    _wait_until(service.started.is_set)

    assert not dialog.question_input.isEnabled()
    assert not dialog.ask_button.isEnabled()
    assert not dialog.close_button.isEnabled()
    service.release.set()
    _wait_until(lambda: dialog._worker is None)
    assert dialog.question_input.isEnabled()
    assert dialog.ask_button.isEnabled()
    assert dialog.close_button.isEnabled()


def test_technical_result_renders_answer_product_and_source() -> None:
    dialog, _service = _dialog()

    dialog._question_succeeded(_technical_result())

    assert dialog.answer_output.toPlainText().startswith("No hay")
    assert dialog.products_table.rowCount() == 1
    assert dialog.products_table.item(0, 0).text() == "Complementario"
    assert dialog.products_table.item(0, 1).text() == "PREBACK"
    assert "10 a 30" in dialog.products_table.item(0, 3).text()
    assert dialog.sources_table.rowCount() == 1
    assert dialog.sources_table.item(0, 1).text() == "PREBACK"
    assert dialog.ai_indicator_label.text() == "IA local · datos verificados"
    assert dialog.retrieval_mode_label.text() == "Búsqueda híbrida"


def test_clarification_result_is_separate_from_answer_and_uses_no_ai() -> None:
    dialog, _service = _dialog()
    result = TechnicalConsultantResult(
        ok=True,
        answer="Faltan requisitos técnicos reconocibles.",
        message="Se necesita información adicional antes de recomendar productos.",
        needs_clarification=True,
        clarification_questions=(
            "¿Qué proceso debe soportar?",
            "¿Qué tipo de producto elaboras?",
            "¿Qué resultado quieres mejorar?",
        ),
    )

    dialog._question_succeeded(result)

    assert dialog.clarification_list.isVisibleTo(dialog)
    assert dialog.clarification_list.count() == 3
    assert dialog.products_table.rowCount() == 0
    assert dialog.sources_table.rowCount() == 0
    assert dialog.ai_indicator_label.text() == "Pendiente de aclaración"


def test_source_selection_emits_identifier_and_page_only() -> None:
    dialog, _service = _dialog()
    emitted: list[tuple[str, int]] = []
    dialog.source_requested.connect(
        lambda document_id, page: emitted.append((document_id, page))
    )
    dialog._question_succeeded(_technical_result())

    dialog.sources_table.selectRow(0)
    assert dialog.show_source_button.isEnabled()
    dialog.show_source_button.click()

    assert emitted == [("a" * 64, 1)]


def test_worker_error_is_redacted_and_clears_previous_result() -> None:
    dialog, service = _dialog()
    dialog._question_succeeded(_technical_result())
    service.error = RuntimeError("Fallo en C:/privado/modelo.bin")
    dialog.question_input.setPlainText("consulta")

    dialog.ask_button.click()
    _wait_until(lambda: dialog._worker is None)

    assert dialog.answer_output.toPlainText() == ""
    assert dialog.products_table.rowCount() == 0
    assert "C:/privado" not in dialog.status_label.text()
    assert "[RUTA OMITIDA]" in dialog.status_label.text()


def test_dialog_cannot_close_while_worker_is_active() -> None:
    dialog, service = _dialog()
    service.block = True
    dialog.question_input.setPlainText("consulta larga")
    dialog.show()
    dialog.ask_button.click()
    _wait_until(service.started.is_set)

    dialog.close()
    _application().processEvents()

    assert dialog.isVisible()
    assert "Espera a que finalice" in dialog.status_label.text()
    service.release.set()
    _wait_until(lambda: dialog._worker is None)
    dialog.close()

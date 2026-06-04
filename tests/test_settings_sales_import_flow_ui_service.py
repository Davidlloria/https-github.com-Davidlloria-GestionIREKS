from __future__ import annotations

from app.services.settings_sales_import_flow_ui_service import SettingsSalesImportFlowUiService
from app.services.settings_sales_import_service import SettingsSalesImportOutcome


def test_pdf_preview_can_be_cancelled_without_import() -> None:
    service = SettingsSalesImportFlowUiService()
    calls: list[str] = []

    result = service.run_pdf_preview_import_flow(
        confirmed=False,
        lines=[{"row": 1}],
        importer=lambda _lines: calls.append("import") or SettingsSalesImportOutcome(
            ok=True,
            title="Importacion PDF IGSA",
            message="ok",
            log_message="log",
        ),
    )

    assert result.outcome is None
    assert calls == []


def test_pdf_preview_confirmed_executes_import() -> None:
    service = SettingsSalesImportFlowUiService()
    calls: list[str] = []

    def importer(lines: list[object]) -> SettingsSalesImportOutcome:
        calls.append(f"import:{len(lines)}")
        return SettingsSalesImportOutcome(
            ok=True,
            title="Importacion PDF IGSA",
            message="ok",
            log_message="log",
        )

    result = service.run_pdf_preview_import_flow(
        confirmed=True,
        lines=[{"row": 1}],
        importer=importer,
    )

    assert result.outcome is not None
    assert result.outcome.ok is True
    assert calls == ["import:1"]


def test_pdf_preview_errors_are_propagated() -> None:
    service = SettingsSalesImportFlowUiService()

    try:
        service.run_pdf_preview_import_flow(
            confirmed=True,
            lines=[{"row": 1}],
            importer=lambda _lines: (_ for _ in ()).throw(ValueError("pdf roto")),
        )
    except ValueError as exc:
        assert str(exc) == "pdf roto"
    else:
        raise AssertionError("Expected ValueError")


def test_workbook_preview_executes_import_once_when_reimport_is_declined() -> None:
    service = SettingsSalesImportFlowUiService()
    calls: list[str] = []

    def importer(lines: list[dict[str, object]], force_reimport: bool) -> SettingsSalesImportOutcome:
        calls.append(f"import:{len(lines)}:{force_reimport}")
        return SettingsSalesImportOutcome(
            ok=True,
            title="Importacion IGSA libro",
            message="ok",
            log_message="log",
        )

    result = service.run_workbook_preview_import_flow(
        confirmed=True,
        lines=[{"row": 1}],
        importer=importer,
        ask_reimport=lambda _text: False,
    )

    assert result.outcome is not None
    assert result.outcome.ok is True
    assert calls == ["import:1:False"]


def test_workbook_preview_reimport_is_honoured() -> None:
    service = SettingsSalesImportFlowUiService()
    calls: list[str] = []
    responses = iter([True, False])

    def importer(lines: list[dict[str, object]], force_reimport: bool) -> SettingsSalesImportOutcome:
        calls.append(f"import:{len(lines)}:{force_reimport}")
        return SettingsSalesImportOutcome(
            ok=True,
            title="Importacion IGSA libro",
            message=f"ok-{force_reimport}",
            log_message="log",
        )

    result = service.run_workbook_preview_import_flow(
        confirmed=True,
        lines=[{"row": 1}],
        importer=importer,
        ask_reimport=lambda _text: next(responses),
    )

    assert result.outcome is not None
    assert result.outcome.ok is True
    assert calls == ["import:1:False", "import:1:True"]


def test_workbook_preview_can_be_cancelled_without_import() -> None:
    service = SettingsSalesImportFlowUiService()
    calls: list[str] = []

    result = service.run_workbook_preview_import_flow(
        confirmed=False,
        lines=[{"row": 1}],
        importer=lambda _lines, _force: calls.append("import") or SettingsSalesImportOutcome(
            ok=True,
            title="Importacion IGSA libro",
            message="ok",
            log_message="log",
        ),
        ask_reimport=lambda _text: True,
    )

    assert result.outcome is None
    assert calls == []


def test_workbook_preview_errors_are_propagated() -> None:
    service = SettingsSalesImportFlowUiService()

    try:
        service.run_workbook_preview_import_flow(
            confirmed=True,
            lines=[{"row": 1}],
            importer=lambda _lines, _force: (_ for _ in ()).throw(ValueError("book roto")),
            ask_reimport=lambda _text: False,
        )
    except ValueError as exc:
        assert str(exc) == "book roto"
    else:
        raise AssertionError("Expected ValueError")

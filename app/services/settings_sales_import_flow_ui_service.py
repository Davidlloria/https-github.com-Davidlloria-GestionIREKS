from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.services.settings_sales_import_service import SettingsSalesImportOutcome


@dataclass(frozen=True)
class SettingsSalesImportFlowResult:
    outcome: SettingsSalesImportOutcome | None
    reimport_requested: bool = False


class SettingsSalesImportFlowUiService:
    def run_pdf_preview_import_flow(
        self,
        *,
        confirmed: bool,
        lines: list[object],
        importer: Callable[[list[object]], SettingsSalesImportOutcome],
    ) -> SettingsSalesImportFlowResult:
        if not confirmed:
            return SettingsSalesImportFlowResult(outcome=None, reimport_requested=False)
        outcome = importer(list(lines or []))
        return SettingsSalesImportFlowResult(outcome=outcome, reimport_requested=False)

    def run_workbook_preview_import_flow(
        self,
        *,
        confirmed: bool,
        lines: list[dict[str, object]],
        importer: Callable[[list[dict[str, object]], bool], SettingsSalesImportOutcome],
        ask_reimport: Callable[[str], bool],
    ) -> SettingsSalesImportFlowResult:
        if not confirmed:
            return SettingsSalesImportFlowResult(outcome=None, reimport_requested=False)

        clean_lines = list(lines or [])
        force_reimport = False
        while True:
            outcome = importer(clean_lines, force_reimport)
            if not outcome.ok:
                return SettingsSalesImportFlowResult(outcome=outcome, reimport_requested=force_reimport)
            if not ask_reimport(outcome.message):
                return SettingsSalesImportFlowResult(outcome=outcome, reimport_requested=force_reimport)
            force_reimport = True

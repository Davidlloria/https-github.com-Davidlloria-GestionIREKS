from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.services.sales_reconciliation_service import SalesReconciliationService
from app.services.settings_import_service import SettingsImportService


@dataclass(frozen=True)
class SettingsSalesPreviewView:
    pdf_title: str = "Seleccionar PDFs IGSA"
    pdf_filter: str = "PDF (*.pdf)"
    workbook_title: str = "Seleccionar libro IGSA"
    workbook_filter: str = "Excel (*.xlsx *.xlsm)"
    pdf_preview_title: str = "Vista previa temporal - PDF IGSA"
    pdf_preview_error_title: str = "Vista previa PDF IGSA"
    pdf_import_button_label: str = "Importar datos"
    pdf_close_button_label: str = "Cerrar"
    pdf_import_error_title: str = "Importacion PDF IGSA"
    workbook_preview_title: str = "Vista previa - Libro IGSA"
    workbook_preview_error_title: str = "Vista previa IGSA libro"
    workbook_import_result_title: str = "Importacion IGSA libro"
    workbook_import_button_label: str = "Importar datos"
    workbook_reimport_button_label: str = "Reimportar"
    workbook_close_button_label: str = "Cerrar"
    workbook_import_error_title: str = "Importacion IGSA libro"


@dataclass
class SettingsSalesPdfPreviewOutcome:
    lines: list[object] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class SettingsSalesWorkbookPreviewOutcome:
    raw_lines: list[object] = field(default_factory=list)
    preview_rows: list[dict[str, object]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SettingsSalesPreviewService:
    def __init__(
        self,
        sales_service: SalesReconciliationService | None = None,
        settings_import_service: SettingsImportService | None = None,
    ) -> None:
        self.sales_service = sales_service or SalesReconciliationService()
        self.settings_import_service = settings_import_service or SettingsImportService()

    def build_preview_view(self) -> SettingsSalesPreviewView:
        return SettingsSalesPreviewView()

    def preview_igsa_pdf_files(self, file_paths: list[Path]) -> SettingsSalesPdfPreviewOutcome:
        clean_paths = self._validate_paths(file_paths, allowed_suffixes={".pdf"})
        lines, errors = self.sales_service.parse_igsa_pdf_files(clean_paths)
        if not lines:
            detail = "\n".join(errors[:10]) if errors else "No se pudieron extraer lineas."
            raise ValueError(detail)
        return SettingsSalesPdfPreviewOutcome(lines=list(lines), errors=list(errors))

    def preview_igsa_workbook(self, file_path: Path) -> SettingsSalesWorkbookPreviewOutcome:
        clean_file = self._validate_path(file_path, allowed_suffixes={".xlsx", ".xlsm"})
        lines, parse_errors = self.sales_service.parse_igsa_workbook_by_sheets(clean_file)
        if not lines:
            detail = "\n".join(parse_errors[:20]) if parse_errors else "No se pudieron extraer lineas."
            raise ValueError(detail)
        igsa_cliente_id = str(self.settings_import_service.resolve_igsa_cliente_id() or "").strip()
        if not igsa_cliente_id:
            raise ValueError("No se encontro el cliente/distribuidor IGSA.")
        preview_rows, preview_errors = self.sales_service.build_igsa_workbook_preview(lines, igsa_cliente_id)
        return SettingsSalesWorkbookPreviewOutcome(
            raw_lines=list(lines),
            preview_rows=list(preview_rows),
            errors=list(parse_errors) + list(preview_errors),
        )

    def _validate_paths(self, file_paths: list[Path], *, allowed_suffixes: set[str]) -> list[Path]:
        clean_paths = [self._validate_path(path, allowed_suffixes=allowed_suffixes) for path in file_paths or []]
        if not clean_paths:
            raise ValueError("Selecciona al menos un archivo valido.")
        return clean_paths

    def _validate_path(self, file_path: Path, *, allowed_suffixes: set[str]) -> Path:
        clean_file = Path(file_path)
        if not clean_file.exists() or not clean_file.is_file():
            raise ValueError(f"No existe el archivo: {clean_file}")
        if clean_file.suffix.lower() not in allowed_suffixes:
            allowed = ", ".join(sorted(allowed_suffixes))
            raise ValueError(f"El archivo seleccionado debe tener extension {allowed}.")
        return clean_file

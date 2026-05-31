from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.sales_reconciliation_service import SalesReconciliationService


@dataclass
class SettingsSalesImportOutcome:
    ok: bool
    title: str
    message: str
    log_message: str
    imported: int = 0
    incidencias: int = 0


class SettingsSalesImportService:
    def __init__(self, sales_service: SalesReconciliationService | None = None) -> None:
        self.sales_service = sales_service or SalesReconciliationService()

    def import_ireks_json(self, source: Path) -> SettingsSalesImportOutcome:
        clean_source = self._validate_source(source, allowed_suffixes={".json"})
        result = self.sales_service.import_ireks_json(clean_source)
        text, imported, incidencias = self._build_message(
            result=result,
            imported_label="Registros",
            incidencias_label="Filas omitidas",
        )
        return self._build_outcome(
            title="Importacion ventas IREKS",
            log_prefix="Importacion IREKS",
            ok=bool(getattr(result, "ok", False)),
            text=text,
            imported=imported,
            incidencias=incidencias,
        )

    def import_igsa_excel(self, source: Path) -> SettingsSalesImportOutcome:
        clean_source = self._validate_source(source, allowed_suffixes={".xlsx", ".xlsm"})
        result = self.sales_service.import_igsa_excel(clean_source)
        text, imported, incidencias = self._build_message(
            result=result,
            imported_label="Registros",
            incidencias_label="Filas omitidas",
        )
        return self._build_outcome(
            title="Importacion ventas IGSA",
            log_prefix="Importacion IGSA",
            ok=bool(getattr(result, "ok", False)),
            text=text,
            imported=imported,
            incidencias=incidencias,
        )

    def import_igsa_pdf_lines(self, lines: list[object], cliente_id: str) -> SettingsSalesImportOutcome:
        clean_lines = self._validate_lines(lines)
        clean_cliente_id = self._validate_cliente_id(cliente_id)
        result = self.sales_service.import_igsa_pdf_lines(clean_lines, cliente_id=clean_cliente_id)
        text, imported, incidencias = self._build_message(
            result=result,
            imported_label="Registros",
            incidencias_label="Filas omitidas",
        )
        return self._build_outcome(
            title="Importacion PDF IGSA",
            log_prefix="Importacion PDF IGSA",
            ok=bool(getattr(result, "ok", False)),
            text=text,
            imported=imported,
            incidencias=incidencias,
        )

    def import_igsa_workbook_lines(
        self,
        lines: list[object],
        cliente_id: str,
        *,
        force_reimport: bool = False,
    ) -> SettingsSalesImportOutcome:
        clean_lines = self._validate_lines(lines)
        clean_cliente_id = self._validate_cliente_id(cliente_id)
        result = self.sales_service.import_igsa_workbook_lines(
            clean_lines,
            cliente_id=clean_cliente_id,
            force_reimport=bool(force_reimport),
        )
        text, imported, incidencias = self._build_message(
            result=result,
            imported_label="Registros",
            incidencias_label="Filas omitidas",
        )
        return self._build_outcome(
            title="Importacion IGSA libro",
            log_prefix="Importacion IGSA libro",
            ok=bool(getattr(result, "ok", False)),
            text=text,
            imported=imported,
            incidencias=incidencias,
        )

    def rebuild_igsa_warehouse_movements(self, periodo: str) -> SettingsSalesImportOutcome:
        clean_periodo = str(periodo or "").strip()
        if clean_periodo and not re.fullmatch(r"\d{4}-\d{2}", clean_periodo):
            raise ValueError("El periodo debe tener formato AAAA-MM.")
        result = self.sales_service.rebuild_igsa_warehouse_movements(clean_periodo)
        text, imported, incidencias = self._build_message(
            result=result,
            imported_label="Filas procesadas",
            incidencias_label="Incidencias",
        )
        return self._build_outcome(
            title="Regenerar salidas IGSA",
            log_prefix="Regenerar IGSA",
            ok=bool(getattr(result, "ok", False)),
            text=text,
            imported=imported,
            incidencias=incidencias,
        )

    def _validate_source(self, source: Path, *, allowed_suffixes: set[str]) -> Path:
        clean_source = Path(source)
        if not clean_source.exists() or not clean_source.is_file():
            raise ValueError("El archivo seleccionado no existe.")
        if clean_source.suffix.lower() not in allowed_suffixes:
            allowed = ", ".join(sorted(allowed_suffixes))
            raise ValueError(f"El archivo seleccionado debe tener extension {allowed}.")
        return clean_source

    def _validate_lines(self, lines: list[object]) -> list[object]:
        clean_lines = list(lines or [])
        if not clean_lines:
            raise ValueError("Primero carga los datos y revisa la vista previa.")
        return clean_lines

    def _validate_cliente_id(self, cliente_id: str) -> str:
        clean_cliente_id = str(cliente_id or "").strip()
        if not clean_cliente_id:
            raise ValueError("No se encontro el cliente/distribuidor IGSA.")
        return clean_cliente_id

    def _build_message(
        self,
        *,
        result: Any,
        imported_label: str,
        incidencias_label: str,
    ) -> tuple[str, int, int]:
        text = str(getattr(result, "message", "") or "")
        imported = int(getattr(result, "imported", 0) or 0)
        incidencias = int(getattr(result, "incidencias", 0) or 0)
        if imported:
            text += f"\n{imported_label}: {imported}"
        if incidencias:
            text += f"\n{incidencias_label}: {incidencias}"
        return text, imported, incidencias

    def _build_outcome(
        self,
        *,
        title: str,
        log_prefix: str,
        ok: bool,
        text: str,
        imported: int,
        incidencias: int,
    ) -> SettingsSalesImportOutcome:
        status = "OK" if ok else "ERROR"
        return SettingsSalesImportOutcome(
            ok=ok,
            title=title,
            message=text,
            log_message=f"{log_prefix} {status}: {text.replace(chr(10), ' | ')}",
            imported=imported,
            incidencias=incidencias,
        )

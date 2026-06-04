from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.services.settings_import_service import SettingsImportService
from app.services.order_query_service import WarehouseFilterOption


@dataclass(frozen=True)
class SettingsOrdersImportView:
    section_info_label: str = "Importacion de pedidos (JSON)"
    selector_label: str = "Cliente/Distribuidor"
    import_button_label: str = "Importar pedidos"
    warehouse_options: list[WarehouseFilterOption] = field(default_factory=list)


@dataclass
class SettingsOrdersImportOutcome:
    ok: bool
    message: str
    log_message: str = ""
    summary_lines: list[str] = field(default_factory=list)
    imported_items: int = 0
    skipped_unknown_count: int = 0
    skipped_invalid: int = 0


class SettingsOrdersImportService:
    def __init__(self, settings_import_service: SettingsImportService | None = None) -> None:
        self.settings_import_service = settings_import_service or SettingsImportService()

    def build_orders_import_view(self) -> SettingsOrdersImportView:
        return SettingsOrdersImportView(warehouse_options=list(self.settings_import_service.warehouse_filter_options()))

    def import_orders_json(self, source: Path, almacen_id: str) -> SettingsOrdersImportOutcome:
        clean_almacen_id = str(almacen_id or "").strip()
        if not clean_almacen_id:
            raise ValueError("Selecciona un Cliente/Distribuidor.")

        clean_source = Path(source)
        if not clean_source.exists() or not clean_source.is_file():
            raise ValueError("El archivo seleccionado no existe.")
        if clean_source.suffix.lower() != ".json":
            raise ValueError("El archivo seleccionado debe tener extension .json.")

        result = self.settings_import_service.import_order_json(clean_source, clean_almacen_id)
        unknown_unique = sorted(set(result.skipped_unknown))
        unknown_preview = ", ".join(unknown_unique[:10])
        unknown_extra = "" if len(unknown_unique) <= 10 else f" ... (+{len(unknown_unique) - 10})"
        summary = [
            "Pedido importado: (sin numero)",
            f"Lineas importadas: {result.imported_items}",
            f"Lineas con codigo inexistente: {len(result.skipped_unknown)}",
            f"Lineas invalidas: {result.skipped_invalid}",
        ]
        if unknown_unique:
            summary.append(f"Codigos no encontrados: {unknown_preview}{unknown_extra}")
        return SettingsOrdersImportOutcome(
            ok=True,
            message="Importacion de pedidos completada.",
            log_message=f"Importacion pedidos OK: {clean_source.name} | lineas={result.imported_items}",
            summary_lines=summary,
            imported_items=int(result.imported_items or 0),
            skipped_unknown_count=len(result.skipped_unknown or []),
            skipped_invalid=int(result.skipped_invalid or 0),
        )

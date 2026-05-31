from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.order_service import OrderService


@dataclass
class OrdersItemsImportOutcome:
    ok: bool
    title: str
    message: str
    imported: int = 0
    errors_count: int = 0


class OrdersItemsImportUiService:
    def __init__(self, order_service: OrderService | None = None) -> None:
        self.order_service = order_service or OrderService()

    def import_order_items_file(self, source: Path) -> OrdersItemsImportOutcome:
        clean_source = Path(source)
        if not clean_source.exists() or not clean_source.is_file():
            raise ValueError("El archivo seleccionado no existe.")
        if clean_source.suffix.lower() not in {".xlsx", ".xlsm", ".csv"}:
            raise ValueError("El archivo seleccionado debe ser .xlsx, .xlsm o .csv.")

        result = self.order_service.import_order_items_file(clean_source)
        imported = int(getattr(result, "imported", 0) or 0)
        errors = list(getattr(result, "errors", []) or [])
        if errors:
            preview = "\n".join(errors[:8])
            extra = "" if len(errors) <= 8 else f"\n... y {len(errors) - 8} errores mas."
            return OrdersItemsImportOutcome(
                ok=False,
                title="Importacion completada con incidencias",
                message=f"Registros importados: {imported}\nErrores: {len(errors)}\n\n{preview}{extra}",
                imported=imported,
                errors_count=len(errors),
            )
        return OrdersItemsImportOutcome(
            ok=True,
            title="Importacion completada",
            message=f"Items importados: {imported}",
            imported=imported,
            errors_count=0,
        )

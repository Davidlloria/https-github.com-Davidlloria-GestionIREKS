from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.services.order_service import OrderService


@dataclass
class OrdersJsonImportOutcome:
    ok: bool
    message: str
    pedido_id: str = ""
    summary_lines: list[str] = field(default_factory=list)
    imported_items: int = 0
    skipped_unknown_count: int = 0
    skipped_invalid: int = 0


class OrdersJsonImportUiService:
    def __init__(self, order_service: OrderService | None = None) -> None:
        self.order_service = order_service or OrderService()

    def resolve_almacen_id(self, filter_almacen_id: str, selected_almacen_id: str) -> str:
        almacen_id = str(filter_almacen_id or "").strip()
        if not almacen_id:
            almacen_id = str(selected_almacen_id or "").strip()
        if not almacen_id:
            raise ValueError("Selecciona un Cliente/Distribuidor en el filtro para importar pedidos JSON.")
        return almacen_id

    def import_orders_json(self, source: Path, almacen_id: str) -> OrdersJsonImportOutcome:
        clean_source = Path(source)
        if not clean_source.exists() or not clean_source.is_file():
            raise ValueError("El archivo seleccionado no existe.")
        if clean_source.suffix.lower() != ".json":
            raise ValueError("El archivo seleccionado debe tener extension .json.")

        result = self.order_service.import_order_json(clean_source, str(almacen_id or "").strip())
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

        return OrdersJsonImportOutcome(
            ok=True,
            message="Importacion completada.",
            pedido_id=str(result.pedido_id or ""),
            summary_lines=summary,
            imported_items=int(result.imported_items or 0),
            skipped_unknown_count=len(result.skipped_unknown or []),
            skipped_invalid=int(result.skipped_invalid or 0),
        )

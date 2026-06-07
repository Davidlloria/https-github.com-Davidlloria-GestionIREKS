from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services.warehouse_inventory_service import WarehouseInventoryService


@dataclass
class WarehouseHistoryRow:
    inventario_id: str
    fecha_text: str
    contador: str
    aprobador: str
    lineas: str
    ajustes: str
    estado: str


@dataclass
class WarehouseHistoryDetailRow:
    inventario_id: str
    articulo_id: str
    ref: str
    nombre: str
    lote: str
    caduca_text: str
    teorico_text: str
    conteo_text: str
    diferencia_text: str
    kg_ajuste_text: str


@dataclass
class WarehouseHistoryExportPayload:
    headers: list[Any] = field(default_factory=list)
    details: list[Any] = field(default_factory=list)
    items: list[Any] = field(default_factory=list)


@dataclass
class WarehouseHistoryFlowResult:
    status: str
    message: str = ""
    rows: list[WarehouseHistoryRow] = field(default_factory=list)
    selected_id: str = ""
    detail_rows: list[WarehouseHistoryDetailRow] = field(default_factory=list)
    export_payload: WarehouseHistoryExportPayload | None = None


class WarehouseHistoryFlowService:
    def __init__(self, *, inventory_service: WarehouseInventoryService | None = None) -> None:
        self.inventory_service = inventory_service or WarehouseInventoryService()

    def load_history(self, almacen_id: str) -> WarehouseHistoryFlowResult:
        rows = self.inventory_service.history(str(almacen_id or "").strip())
        history_rows = self._build_history_rows(rows)
        if not history_rows:
            return WarehouseHistoryFlowResult(status="empty", message="No hay historial para el almacen actual.")
        selected_id = history_rows[0].inventario_id
        detail_rows = self.load_history_detail(selected_id)
        return WarehouseHistoryFlowResult(
            status="ready",
            rows=history_rows,
            selected_id=selected_id,
            detail_rows=detail_rows,
            export_payload=self.prepare_export_payload(str(almacen_id or "").strip(), selected_id),
        )

    def load_history_detail(self, inventario_id: str) -> list[WarehouseHistoryDetailRow]:
        clean_id = str(inventario_id or "").strip()
        if not clean_id:
            return []
        payload = self.inventory_service.history_detail(clean_id)
        return self._build_detail_rows(payload.details, payload.items)

    def resolve_selected_id(self, rows: Iterable[object], selected_index: int) -> str:
        items = list(rows or [])
        if selected_index < 0 or selected_index >= len(items):
            return ""
        row = items[selected_index]
        if isinstance(row, str):
            return row.strip()
        return str(self._get(row, "inventario_id") or "").strip()

    def prepare_export_payload(self, almacen_id: str, selected_id: str = "") -> WarehouseHistoryExportPayload:
        payload = self.inventory_service.export_payload(
            almacen_id=str(almacen_id or "").strip(),
            selected_id=str(selected_id or "").strip(),
        )
        return WarehouseHistoryExportPayload(
            headers=list(payload.headers),
            details=list(payload.details),
            items=list(payload.items),
        )

    def export_rows(self, almacen_id: str, selected_id: str = "") -> WarehouseHistoryFlowResult:
        export_payload = self.prepare_export_payload(almacen_id, selected_id)
        if not export_payload.headers:
            return WarehouseHistoryFlowResult(
                status="empty",
                message="No hay historial para exportar con el filtro actual.",
                export_payload=export_payload,
            )
        return WarehouseHistoryFlowResult(status="ready", export_payload=export_payload)

    def _build_history_rows(self, rows: Iterable[object]) -> list[WarehouseHistoryRow]:
        out: list[WarehouseHistoryRow] = []
        for inv in rows or []:
            fecha = self._get(inv, "fecha")
            out.append(
                WarehouseHistoryRow(
                    inventario_id=str(self._get(inv, "inventario_id") or "").strip(),
                    fecha_text=fecha.strftime("%d/%m/%Y") if fecha else "",
                    contador=str(self._get(inv, "contador") or "").strip(),
                    aprobador=str(self._get(inv, "aprobador") or "").strip(),
                    lineas=str(int(self._get(inv, "lineas", 0) or 0)),
                    ajustes=str(int(self._get(inv, "ajustes", 0) or 0)),
                    estado=str(self._get(inv, "estado") or "").strip(),
                )
            )
        return out

    def _build_detail_rows(self, details: Iterable[object], items: Iterable[object]) -> list[WarehouseHistoryDetailRow]:
        ref_by_articulo = {
            str(self._get(x, "articulo_id") or "").strip(): str(self._get(x, "articulo_referencia_corta") or "").strip()
            for x in items or []
        }
        nombre_by_articulo = {
            str(self._get(x, "articulo_id") or "").strip(): str(self._get(x, "articulo_descripcion") or "").strip()
            for x in items or []
        }
        out: list[WarehouseHistoryDetailRow] = []
        for det in details or []:
            art_id = str(self._get(det, "articulo_id") or "").strip()
            cad = self._get(det, "articulo_caducidad")
            out.append(
                WarehouseHistoryDetailRow(
                    inventario_id=str(self._get(det, "inventario_id") or "").strip(),
                    articulo_id=art_id,
                    ref=ref_by_articulo.get(art_id, "") or art_id,
                    nombre=nombre_by_articulo.get(art_id, "") or art_id,
                    lote=str(self._get(det, "articulo_lote") or "").strip(),
                    caduca_text=cad.strftime("%d/%m/%Y") if cad else "",
                    teorico_text=f"{float(self._get(det, 'teorico_uds', 0.0) or 0.0):.2f}",
                    conteo_text=f"{float(self._get(det, 'conteo_uds', 0.0) or 0.0):.2f}",
                    diferencia_text=f"{float(self._get(det, 'diferencia_uds', 0.0) or 0.0):.2f}",
                    kg_ajuste_text=f"{float(self._get(det, 'kg_ajuste', 0.0) or 0.0):.2f} kg",
                )
            )
        return out

    @staticmethod
    def _get(value: object, key: str, default: Any = None) -> Any:
        return getattr(value, key, default)

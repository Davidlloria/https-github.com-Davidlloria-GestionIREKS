from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable
from uuid import uuid4

from app.models import AlmacenMovimiento


@dataclass(frozen=True)
class WarehouseInventoryAdjustmentRowInput:
    articulo_id: str = ""
    articulo_lote: str = ""
    articulo_caducidad_iso: str = ""
    conteo_text: str = ""
    teorico_text: str = ""
    peso: float = 0.0


@dataclass
class WarehouseInventoryAdjustmentPreparationResult:
    status: str
    message: str = ""
    pending: list[dict[str, Any]] = field(default_factory=list)
    inventory_code: str = ""
    prepared_count: int = 0


class WarehouseInventoryAdjustmentPreparationService:
    def prepare_adjustments(
        self,
        rows: Iterable[WarehouseInventoryAdjustmentRowInput | dict[str, Any]],
        *,
        almacen_id: str,
        today: date | None = None,
    ) -> WarehouseInventoryAdjustmentPreparationResult:
        clean_almacen_id = str(almacen_id or "").strip()
        if not clean_almacen_id:
            return WarehouseInventoryAdjustmentPreparationResult(
                status="error",
                message="Indica almacen_id.",
            )

        current_day = today or date.today()
        inv_code = f"INV-{current_day.strftime('%Y%m%d')}"
        ajustes: list[dict[str, Any]] = []

        try:
            for raw_row in rows:
                row = self._normalize_row(raw_row)
                conteo_txt = str(row.conteo_text or "").strip().replace(",", ".")
                if conteo_txt == "":
                    continue
                try:
                    conteo = float(conteo_txt)
                except ValueError:
                    continue

                teorico_txt = str(row.teorico_text or "").strip().replace(",", ".")
                teorico = float(teorico_txt or 0.0)
                diff = conteo - teorico
                if abs(diff) < 0.0001:
                    continue

                cad = date.fromisoformat(str(row.articulo_caducidad_iso or "").strip()) if str(row.articulo_caducidad_iso or "").strip() else None
                peso = float(row.peso or 0.0)
                mov = AlmacenMovimiento(
                    almacen_id=clean_almacen_id,
                    articulo_id=str(row.articulo_id or "").strip(),
                    pedido_numero=inv_code,
                    pedido_albaran_numero="INV-AJUSTE",
                    cantidad=diff,
                    articulo_lote=str(row.articulo_lote or "").strip(),
                    articulo_caducidad=cad,
                    fecha_pedido=current_day,
                    albaran_item_id=str(uuid4()),
                )
                ajustes.append(
                    {
                        "mov": mov,
                        "articulo_id": str(row.articulo_id or "").strip(),
                        "articulo_lote": str(row.articulo_lote or "").strip(),
                        "articulo_caducidad": cad,
                        "teorico_uds": teorico,
                        "conteo_uds": conteo,
                        "diferencia_uds": diff,
                        "kg_ajuste": diff * peso,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            return WarehouseInventoryAdjustmentPreparationResult(
                status="error",
                message=f"No se pudieron preparar los ajustes.\n{exc}",
            )

        if not ajustes:
            return WarehouseInventoryAdjustmentPreparationResult(
                status="no_differences",
                message="No hay diferencias para ajustar.",
                inventory_code=inv_code,
            )

        return WarehouseInventoryAdjustmentPreparationResult(
            status="ready",
            message=f"Ajustes preparados: {len(ajustes)}\nRevisa y pulsa 'Aprobar y aplicar'.",
            pending=ajustes,
            inventory_code=inv_code,
            prepared_count=len(ajustes),
        )

    @staticmethod
    def _normalize_row(row: WarehouseInventoryAdjustmentRowInput | dict[str, Any]) -> WarehouseInventoryAdjustmentRowInput:
        if isinstance(row, WarehouseInventoryAdjustmentRowInput):
            return row
        return WarehouseInventoryAdjustmentRowInput(
            articulo_id=str(row.get("articulo_id", "") or ""),
            articulo_lote=str(row.get("articulo_lote", "") or ""),
            articulo_caducidad_iso=str(row.get("articulo_caducidad_iso", "") or ""),
            conteo_text=str(row.get("conteo_text", "") or ""),
            teorico_text=str(row.get("teorico_text", "") or ""),
            peso=float(row.get("peso", 0.0) or 0.0),
        )

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.models import AlmacenMovimiento
from app.services.warehouse_movement_service import WarehouseMovementService, WarehouseStockConflictError


@dataclass
class WarehouseManualMoveFlowResult:
    status: str
    message: str = ""
    mode: str = ""
    almacen_id: str = ""
    existing: AlmacenMovimiento | None = None
    fecha_pedido: date | None = None
    caducidad: date | None = None
    albaran: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    quantity_signed: float = 0.0
    stock: float = 0.0
    move: AlmacenMovimiento | None = None


class WarehouseManualMoveFlowService:
    def __init__(self, *, movement_service: WarehouseMovementService | None = None) -> None:
        self.movement_service = movement_service or WarehouseMovementService()

    def build_manual_move_context(
        self,
        payload: dict[str, Any],
        *,
        mode: str,
        almacen_id: str,
        existing: AlmacenMovimiento | None,
    ) -> WarehouseManualMoveFlowResult:
        clean_mode = str(mode or "").strip().lower()
        clean_almacen_id = str(almacen_id or "").strip()
        articulo_id = str((payload or {}).get("articulo_id") or "").strip()
        if not articulo_id:
            return WarehouseManualMoveFlowResult(status="invalid_payload", message="Articulo_ID es obligatorio.")

        cantidad_raw = str((payload or {}).get("cantidad") or "").strip().replace(",", ".")
        try:
            cantidad_abs = abs(float(cantidad_raw))
        except Exception:
            return WarehouseManualMoveFlowResult(status="invalid_payload", message="Cantidad no valida.")
        if cantidad_abs <= 0:
            return WarehouseManualMoveFlowResult(status="invalid_payload", message="La cantidad debe ser mayor que 0.")

        fecha_raw = str((payload or {}).get("fecha_pedido") or "").strip()
        if not fecha_raw:
            fecha_pedido = date.today()
        else:
            fecha_pedido = self._parse_date(fecha_raw)
            if fecha_pedido is None:
                return WarehouseManualMoveFlowResult(status="invalid_payload", message=f"Fecha no valida: {fecha_raw}")
        cad_raw = str((payload or {}).get("articulo_caducidad") or "").strip()
        caducidad = None
        if cad_raw:
            caducidad = self._parse_date(cad_raw, allow_empty=False)
            if caducidad is None:
                return WarehouseManualMoveFlowResult(status="invalid_payload", message=f"Fecha no valida: {cad_raw}")
        lote = str((payload or {}).get("articulo_lote") or "").strip()
        motivo = str((payload or {}).get("motivo") or "").strip()
        usuario = str((payload or {}).get("usuario") or "").strip()
        observacion = str((payload or {}).get("observacion") or "").strip()
        if not motivo:
            return WarehouseManualMoveFlowResult(status="invalid_payload", message="Motivo es obligatorio.")
        if not usuario:
            return WarehouseManualMoveFlowResult(status="invalid_payload", message="Usuario es obligatorio.")
        if clean_mode not in {"in", "out"}:
            return WarehouseManualMoveFlowResult(status="invalid_payload", message="Modo de movimiento no valido.")

        quantity_signed = cantidad_abs if clean_mode == "in" else -cantidad_abs
        stock = 0.0
        if clean_mode == "out":
            stock = self.movement_service.current_stock_for(
                almacen_id=clean_almacen_id,
                articulo_id=articulo_id,
                lote=lote,
                caducidad=caducidad,
            )
            if existing is not None:
                stock -= float(getattr(existing, "cantidad", 0.0) or 0.0)
            if stock + quantity_signed < -0.0001:
                return WarehouseManualMoveFlowResult(
                    status="insufficient_stock",
                    message="La salida manual dejarÃ­a stock negativo para ese producto/lote.",
                    mode=clean_mode,
                    almacen_id=clean_almacen_id,
                    existing=existing,
                    fecha_pedido=fecha_pedido,
                    caducidad=caducidad,
                    payload={
                        "articulo_id": articulo_id,
                        "cantidad": cantidad_abs,
                        "articulo_lote": lote,
                        "motivo": motivo,
                        "usuario": usuario,
                        "observacion": observacion,
                    },
                    quantity_signed=quantity_signed,
                    stock=stock,
                )

        albaran = self._build_manual_albaran(clean_mode, motivo=motivo, usuario=usuario, observacion=observacion)
        return WarehouseManualMoveFlowResult(
            status="ready",
            mode=clean_mode,
            almacen_id=clean_almacen_id,
            existing=existing,
            fecha_pedido=fecha_pedido,
            caducidad=caducidad,
            albaran=albaran,
            payload={
                "articulo_id": articulo_id,
                "cantidad": cantidad_abs,
                "articulo_lote": lote,
                "motivo": motivo,
                "usuario": usuario,
                "observacion": observacion,
            },
            quantity_signed=quantity_signed,
            stock=stock,
        )

    def submit_manual_move(self, context: WarehouseManualMoveFlowResult) -> WarehouseManualMoveFlowResult:
        if context.status != "ready":
            return WarehouseManualMoveFlowResult(
                status="error",
                message=context.message or "No se pudo guardar el movimiento manual.",
                mode=context.mode,
                almacen_id=context.almacen_id,
                existing=context.existing,
                fecha_pedido=context.fecha_pedido,
                caducidad=context.caducidad,
                albaran=context.albaran,
                payload=dict(context.payload or {}),
                quantity_signed=context.quantity_signed,
                stock=context.stock,
            )
        try:
            move = self.movement_service.save_manual_move(
                payload=context.payload,
                mode=context.mode,
                almacen_id=context.almacen_id,
                existing=context.existing,
                fecha_pedido=context.fecha_pedido or date.today(),
                caducidad=context.caducidad,
                albaran=context.albaran,
            )
        except WarehouseStockConflictError as exc:
            return WarehouseManualMoveFlowResult(
                status="insufficient_stock",
                message=str(exc),
                mode=context.mode,
                almacen_id=context.almacen_id,
                existing=context.existing,
                fecha_pedido=context.fecha_pedido,
                caducidad=context.caducidad,
                albaran=context.albaran,
                payload=dict(context.payload or {}),
                quantity_signed=context.quantity_signed,
                stock=context.stock,
            )
        except ValueError as exc:
            return WarehouseManualMoveFlowResult(
                status="invalid_payload",
                message=str(exc),
                mode=context.mode,
                almacen_id=context.almacen_id,
                existing=context.existing,
                fecha_pedido=context.fecha_pedido,
                caducidad=context.caducidad,
                albaran=context.albaran,
                payload=dict(context.payload or {}),
                quantity_signed=context.quantity_signed,
                stock=context.stock,
            )
        except Exception as exc:  # noqa: BLE001
            return WarehouseManualMoveFlowResult(
                status="error",
                message=str(exc),
                mode=context.mode,
                almacen_id=context.almacen_id,
                existing=context.existing,
                fecha_pedido=context.fecha_pedido,
                caducidad=context.caducidad,
                albaran=context.albaran,
                payload=dict(context.payload or {}),
                quantity_signed=context.quantity_signed,
                stock=context.stock,
            )
        return WarehouseManualMoveFlowResult(
            status="success",
            mode=context.mode,
            almacen_id=context.almacen_id,
            existing=context.existing,
            fecha_pedido=context.fecha_pedido,
            caducidad=context.caducidad,
            albaran=context.albaran,
            payload=dict(context.payload or {}),
            quantity_signed=context.quantity_signed,
            stock=context.stock,
            move=move,
        )

    @staticmethod
    def _parse_date(raw: str, *, allow_empty: bool = False) -> date | None:
        text = str(raw or "").strip()
        if not text:
            return None if allow_empty else None
        try:
            if "/" in text:
                dd, mm, yy = text.split("/")
                return date(int(yy), int(mm), int(dd))
            return date.fromisoformat(text)
        except Exception:
            return None

    @staticmethod
    def _build_manual_albaran(mode: str, *, motivo: str, usuario: str, observacion: str) -> str:
        mot = str(motivo or "").strip()
        usr = str(usuario or "").strip()
        obs = str(observacion or "").strip().replace("|", "/")
        base = f"MANUAL-{str(mode or '').upper()}|MOT:{mot}|USR:{usr}"
        if obs:
            base = f"{base}|OBS:{obs}"
        return base[:255]

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class IngredientIreksAutosaveRequest:
    row_id: int
    articulo_id: str
    articulo_referencia_corta: str
    articulo_descripcion: str
    articulo_referencia: str
    fabricante_id: str
    articulo_familia_id: str
    articulo_subfamilia_id: str
    distribuidor_id: str
    articulo_envase_id: str
    articulo_contenido_unidad: str
    articulo_envase_cantidad: float
    articulo_envase_peso: float
    articulo_envase_unidad_medida: str
    transporte_pallet_tipo: str
    transporte_cajas_por_capa: float
    transporte_capas_por_pallet: float
    transporte_observaciones: str
    articulo_status_activo: bool
    articulo_status_en_lista: bool
    categoria: str
    referencia_distribuidor: str
    descripcion_distribuidor: str


@dataclass(slots=True)
class IngredientIreksAutosaveResult:
    ok: bool
    status: str
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    row_updates: dict[str, Any] = field(default_factory=dict)


class IngredientIreksAutosaveFlowService:
    def autosave_selected(
        self,
        request: IngredientIreksAutosaveRequest,
        *,
        update_product: Callable[[int, dict[str, Any]], None],
        upsert_distributor_reference: Callable[..., None],
    ) -> IngredientIreksAutosaveResult:
        clean_row_id = int(request.row_id or 0)
        if clean_row_id <= 0:
            return IngredientIreksAutosaveResult(
                ok=False,
                status="invalid_selection",
            )

        payload = self._build_payload(request)
        try:
            update_product(clean_row_id, payload)
            upsert_distributor_reference(
                articulo_id=self._clean_text(request.articulo_id),
                distribuidor_id=self._clean_text(request.distribuidor_id),
                referencia=self._clean_text(request.referencia_distribuidor),
                descripcion=self._clean_text(request.descripcion_distribuidor),
            )
        except Exception as exc:  # noqa: BLE001
            return IngredientIreksAutosaveResult(
                ok=False,
                status="error",
                message=str(exc),
                payload=payload,
            )

        row_updates = dict(payload)
        row_updates.update(self._derived_transport_values(request))
        return IngredientIreksAutosaveResult(
            ok=True,
            status="saved",
            payload=payload,
            row_updates=row_updates,
        )

    def _build_payload(self, request: IngredientIreksAutosaveRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "articulo_referencia_corta": self._clean_text(request.articulo_referencia_corta),
            "articulo_descripcion": self._clean_text(request.articulo_descripcion),
            "articulo_referencia": self._clean_text(request.articulo_referencia),
            "fabricante_id": self._clean_text(request.fabricante_id),
            "articulo_familia_id": self._clean_text(request.articulo_familia_id),
            "articulo_subfamilia_id": self._clean_text(request.articulo_subfamilia_id),
            "distribuidor_id": self._clean_text(request.distribuidor_id),
            "articulo_envase_id": self._clean_text(request.articulo_envase_id),
            "articulo_contenido_unidad": self._clean_text(request.articulo_contenido_unidad),
            "articulo_envase_cantidad": float(request.articulo_envase_cantidad or 0.0),
            "articulo_envase_peso": float(request.articulo_envase_peso or 0.0),
            "articulo_envase_unidad_medida": self._clean_text(request.articulo_envase_unidad_medida),
            "transporte_pallet_tipo": self._clean_text(request.transporte_pallet_tipo),
            "transporte_cajas_por_capa": float(request.transporte_cajas_por_capa or 0.0),
            "transporte_capas_por_pallet": float(request.transporte_capas_por_pallet or 0.0),
            "transporte_observaciones": self._clean_text(request.transporte_observaciones),
            "articulo_status_activo": bool(request.articulo_status_activo),
            "articulo_status_en_lista": bool(request.articulo_status_en_lista),
            "categoria": self._clean_text(request.categoria),
        }
        payload.update(self._derived_transport_values(request))
        return payload

    def _derived_transport_values(self, request: IngredientIreksAutosaveRequest) -> dict[str, float]:
        cajas_por_capa = float(request.transporte_cajas_por_capa or 0.0)
        capas_por_pallet = float(request.transporte_capas_por_pallet or 0.0)
        envase_cantidad = float(request.articulo_envase_cantidad or 0.0)
        envase_peso = float(request.articulo_envase_peso or 0.0)
        cajas_por_pallet = cajas_por_capa * capas_por_pallet
        unidades_por_pallet = cajas_por_pallet * envase_cantidad
        kg_por_pallet = unidades_por_pallet * envase_peso
        return {
            "transporte_cajas_por_pallet": cajas_por_pallet,
            "transporte_unidades_por_pallet": unidades_por_pallet,
            "transporte_kg_por_pallet": kg_por_pallet,
        }

    @staticmethod
    def _clean_text(value: object) -> str:
        return str(value or "").strip()

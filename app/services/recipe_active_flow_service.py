from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import Receta, RecetaLinea
from app.services.recipe_service import RecipeService


@dataclass(frozen=True)
class RecipeActivePayload:
    recipe_id: int | None
    cliente_id: str
    nombre: str
    codigo_receta: str
    version: str
    es_base: bool
    receta_base_id: int | None
    masa_final_deseada_g: float
    peso_pieza_g: float
    numero_piezas: int
    merma_pct: float
    observaciones: str
    proceso: str
    escandallo_data: dict[str, Any]
    elaboracion_data: dict[str, Any]
    proceso_rich_html: str
    images_gallery: list[dict[str, Any]]
    estado: str


@dataclass
class RecipeActiveFlowResult:
    status: str
    message: str = ""
    receta: Receta | None = None
    lineas: list[RecetaLinea] = field(default_factory=list)
    saved_recipe_id: int = 0
    issues: list[Any] = field(default_factory=list)


class RecipeActiveFlowService:
    def __init__(self, *, recipe_service: RecipeService | None = None) -> None:
        self.recipe_service = recipe_service or RecipeService()

    def build_recipe_model(self, payload: RecipeActivePayload) -> Receta:
        elaboracion_payload = dict(payload.elaboracion_data or {})
        rich_html = str(payload.proceso_rich_html or "").strip()
        if rich_html:
            elaboracion_payload["proceso_rich_html"] = rich_html
        else:
            elaboracion_payload.pop("proceso_rich_html", None)

        images_gallery = [dict(row) for row in (payload.images_gallery or []) if isinstance(row, dict)]
        if images_gallery:
            elaboracion_payload["images_gallery"] = images_gallery
        else:
            elaboracion_payload.pop("images_gallery", None)

        return Receta(
            id=payload.recipe_id,
            cliente_id=str(payload.cliente_id or "").strip(),
            nombre=str(payload.nombre or "").strip(),
            codigo_receta=str(payload.codigo_receta or "").strip() or str(payload.nombre or "").strip(),
            version=str(payload.version or "").strip() or "1.0",
            es_base=bool(payload.es_base),
            receta_base_id=payload.receta_base_id,
            masa_final_deseada_g=float(payload.masa_final_deseada_g or 0.0),
            peso_pieza_g=float(payload.peso_pieza_g or 0.0),
            numero_piezas=int(payload.numero_piezas or 0),
            merma_pct=float(payload.merma_pct or 0.0),
            observaciones=str(payload.observaciones or "").strip(),
            proceso=str(payload.proceso or "").strip(),
            escandallo_detalle_json=self._dump_json(payload.escandallo_data),
            parametros_elaboracion_json=self._dump_json(elaboracion_payload),
            estado=str(payload.estado or "").strip() or "borrador",
        )

    def save_recipe(
        self,
        payload: RecipeActivePayload,
        lineas: list[RecetaLinea],
        *,
        selected_cliente_id: str,
        recipe_tab_index: int,
    ) -> RecipeActiveFlowResult:
        receta = self.build_recipe_model(payload)
        validation = self._validate_recipe_for_save(
            receta,
            selected_cliente_id=selected_cliente_id,
            recipe_tab_index=recipe_tab_index,
        )
        if validation.status != "ready":
            return validation
        try:
            calculated = self.recipe_service.calculate(receta, list(lineas or []), sync_categories=True)
            saved = self.recipe_service.save_recipe(calculated.receta, calculated.lineas)
        except Exception as exc:  # noqa: BLE001
            return RecipeActiveFlowResult(status="error", message=str(exc), receta=receta, lineas=list(lineas or []))
        return RecipeActiveFlowResult(
            status="saved",
            receta=saved.receta,
            lineas=saved.lineas,
            saved_recipe_id=int(getattr(saved.receta, "id", 0) or 0),
            issues=list(getattr(calculated, "issues", [])),
        )

    def autosave_recipe(
        self,
        payload: RecipeActivePayload,
        lineas: list[RecetaLinea],
        *,
        selected_cliente_id: str,
        recipe_tab_index: int,
    ) -> RecipeActiveFlowResult:
        receta = self.build_recipe_model(payload)
        if not receta.nombre:
            return RecipeActiveFlowResult(status="skipped", receta=receta, lineas=list(lineas or []))
        if recipe_tab_index == 1 and not str(selected_cliente_id or "").strip():
            return RecipeActiveFlowResult(status="skipped", receta=receta, lineas=list(lineas or []))
        try:
            calculated = self.recipe_service.calculate(receta, list(lineas or []), sync_categories=True)
            saved = self.recipe_service.save_recipe(calculated.receta, calculated.lineas)
        except Exception as exc:  # noqa: BLE001
            return RecipeActiveFlowResult(status="error", message=str(exc), receta=receta, lineas=list(lineas or []))
        return RecipeActiveFlowResult(
            status="saved",
            receta=saved.receta,
            lineas=saved.lineas,
            saved_recipe_id=int(getattr(saved.receta, "id", 0) or 0),
            issues=list(getattr(calculated, "issues", [])),
        )

    def save_version(
        self,
        payload: RecipeActivePayload,
        lineas: list[RecetaLinea],
        comentario: str,
        *,
        selected_cliente_id: str,
        recipe_tab_index: int,
    ) -> RecipeActiveFlowResult:
        receta = self.build_recipe_model(payload)
        validation = self._validate_recipe_for_save(
            receta,
            selected_cliente_id=selected_cliente_id,
            recipe_tab_index=recipe_tab_index,
        )
        if validation.status != "ready":
            return validation
        try:
            self.recipe_service.save_version(receta, list(lineas or []), comentario.strip())
        except Exception as exc:  # noqa: BLE001
            return RecipeActiveFlowResult(status="error", message=str(exc), receta=receta, lineas=list(lineas or []))
        return RecipeActiveFlowResult(status="version_saved", receta=receta, lineas=list(lineas or []))

    @staticmethod
    def _validate_recipe_for_save(
        receta: Receta,
        *,
        selected_cliente_id: str,
        recipe_tab_index: int,
    ) -> RecipeActiveFlowResult:
        if not str(getattr(receta, "nombre", "") or "").strip():
            return RecipeActiveFlowResult(status="missing_name", message="El nombre de receta es obligatorio.", receta=receta)
        if recipe_tab_index == 1 and not str(selected_cliente_id or "").strip():
            return RecipeActiveFlowResult(
                status="missing_customer",
                message="Selecciona un cliente para guardar una receta de cliente.",
                receta=receta,
            )
        return RecipeActiveFlowResult(status="ready", receta=receta)

    @staticmethod
    def _dump_json(data: dict[str, Any]) -> str:
        try:
            import json

            return json.dumps(data or {}, ensure_ascii=False)
        except Exception:
            return "{}"

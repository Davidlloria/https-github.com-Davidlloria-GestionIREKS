from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.ingredient_ireks_service import IngredientIreksService


@dataclass(slots=True)
class IngredientProductsImportResult:
    status: str
    imported: int = 0
    errors: list[str] = field(default_factory=list)
    preview: str = ""


class IngredientProductsImportFlowService:
    def __init__(self, ingredient_service: Any | None = None) -> None:
        self.ingredient_service = ingredient_service or IngredientIreksService()

    def import_products(self, file_path: str | Path) -> IngredientProductsImportResult:
        path = Path(file_path)
        try:
            imported, errors = self.ingredient_service.import_products(
                str(path),
                self._build_schema(),
                self._build_aliases(),
            )
        except Exception as exc:
            message = str(exc).strip() or "No se pudo importar el archivo."
            return IngredientProductsImportResult(status="error", imported=0, errors=[message], preview=message)

        errors = list(errors or [])
        preview = self._build_preview(errors)
        status = "warning" if errors else "success"
        return IngredientProductsImportResult(status=status, imported=int(imported or 0), errors=errors, preview=preview)

    @staticmethod
    def _build_schema() -> list[dict[str, Any]]:
        return [
            {"name": "almacen_id", "label": "Almacen_ID"},
            {"name": "fabricante_id", "label": "Fabricante_ID"},
            {"name": "distribuidor_id", "label": "Distribuidor_ID"},
            {"name": "articulo_id", "label": "Articulo_ID"},
            {"name": "articulo_referencia", "label": "Articulo_Referencia"},
            {"name": "articulo_referencia_corta", "label": "Articulo_Referencia_Corta"},
            {"name": "articulo_descripcion", "label": "Articulo_Descripcion"},
            {"name": "articulo_envase_id", "label": "Articulo_Envase_ID"},
            {"name": "articulo_contenido_unidad", "label": "Articulo_Contenido_Unidad"},
            {"name": "articulo_envase_cantidad", "label": "Articulo_Envase_Cantidad", "type": "float"},
            {"name": "articulo_envase_peso", "label": "Articulo_Envase_Peso", "type": "float"},
            {"name": "articulo_envase_unidad_medida", "label": "Articulo_Envase_Unidad_Medida"},
            {"name": "articulo_envase_peso_total", "label": "Articulo_Envase_Peso_Total", "type": "float"},
            {"name": "transporte_pallet_tipo", "label": "Transporte_Pallet_Tipo"},
            {"name": "transporte_cajas_por_capa", "label": "Transporte_Cajas_Por_Capa", "type": "float"},
            {"name": "transporte_capas_por_pallet", "label": "Transporte_Capas_Por_Pallet", "type": "float"},
            {"name": "transporte_observaciones", "label": "Transporte_Observaciones"},
            {"name": "articulo_familia_id", "label": "Articulo_Familia_ID"},
            {"name": "articulo_grupo_id", "label": "Articulo_Grupo_ID"},
            {"name": "articulo_subfamilia_id", "label": "Articulo_Subfamilia_ID"},
            {"name": "articulo_status_activo", "label": "Articulo_Status_Activo", "type": "bool", "default": True},
            {"name": "articulo_status_en_lista", "label": "Articulo_Status_En_Lista", "type": "bool", "default": False},
        ]

    @staticmethod
    def _build_aliases() -> dict[str, list[str]]:
        return {
            "almacen_id": ["almacen", "almacen_id"],
            "fabricante_id": ["fabricante", "fabricante_id", "marca_id"],
            "distribuidor_id": ["distribuidor", "distribuidor_id"],
            "articulo_id": ["articulo", "articulo_id", "id_articulo"],
            "articulo_referencia": ["referencia", "ref", "codigo"],
            "articulo_referencia_corta": ["referencia_corta", "ref_corta", "codigo_corto"],
            "articulo_descripcion": ["descripcion", "nombre", "articulo_descripcion"],
            "articulo_envase_id": ["envase", "envase_id", "articulo_envase_id"],
            "articulo_contenido_unidad": ["unidad_contenido", "contenido_unidad", "unidad_interior", "tipo_contenido"],
            "articulo_envase_cantidad": ["envase_cantidad", "cantidad_envase"],
            "articulo_envase_peso": ["envase_peso", "peso_envase"],
            "articulo_envase_unidad_medida": ["unidad_medida", "unidad", "um"],
            "articulo_envase_peso_total": ["peso_total", "envase_peso_total"],
            "articulo_familia_id": ["familia", "familia_id"],
            "articulo_grupo_id": ["grupo", "grupo_id"],
            "articulo_subfamilia_id": ["subfamilia", "subfamilia_id"],
            "articulo_status_activo": ["status_activo", "activo_status", "activo_producto", "estado", "habilitado"],
            "articulo_status_en_lista": ["status_en_lista", "en_lista", "lista"],
        }

    @staticmethod
    def _build_preview(errors: list[str]) -> str:
        if not errors:
            return ""
        preview = "\n".join(errors[:8])
        if len(errors) > 8:
            preview += f"\n... y {len(errors) - 8} errores mas."
        return preview

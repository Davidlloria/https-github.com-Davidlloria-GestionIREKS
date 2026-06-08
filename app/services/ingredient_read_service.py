from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.core.database import engine
from app.core.pagination import DEFAULT_PAGE_LIMIT, page_items
from app.models import IngredienteIreks, IngredienteStd
from app.schemas.ingredients import IngredientDetail, IngredientListItem, IngredientListResponse
from app.services.ingredient_ireks_service import IngredientIreksService
from app.services.ingredient_std_service import IngredientStdService


@dataclass(slots=True)
class IngredientReadService:
    engine: object | None = None
    ireks_service: IngredientIreksService | None = None
    std_service: IngredientStdService | None = None

    def __post_init__(self) -> None:
        if self.engine is None:
            self.engine = engine
        if self.ireks_service is None:
            self.ireks_service = IngredientIreksService()
        if self.std_service is None:
            self.std_service = IngredientStdService()

    def list_payload(
        self,
        *,
        q: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
        fabricante_id: str = "",
        activity_filter: str = "all",
        distributor_filter_id: str = "",
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> IngredientListResponse:
        with Session(self.engine) as session:
            ireks_rows = self.ireks_service.vm.list(
                session,
                q,
                familia_id,
                subfamilia_id,
                fabricante_id,
                activity_filter,
                distributor_filter_id,
            )
            std_rows = self.std_service.vm.list(
                session,
                q,
                familia_id,
                subfamilia_id,
                activity_filter=activity_filter,
            )
            items = [self._from_ireks(row) for row in ireks_rows]
            items.extend(self._from_std(row) for row in std_rows)
        items.sort(key=lambda item: (item.nombre.lower(), item.id))
        paged = page_items(items, limit=limit, offset=offset)
        return IngredientListResponse(total=len(items), limit=limit, offset=offset, items=paged)

    def detail_payload(self, ingredient_id: str) -> IngredientDetail | None:
        clean_id = str(ingredient_id or "").strip()
        if not clean_id:
            return None
        with Session(self.engine) as session:
            item = self._get_ireks(session, clean_id)
            if item is not None:
                return item
            item = self._get_std(session, clean_id)
            if item is not None:
                return item
        return None

    def _get_ireks(self, session: Session, ingredient_id: str) -> IngredientDetail | None:
        lookup = ingredient_id
        if lookup.lower().startswith("ireks:"):
            lookup = lookup.split(":", 1)[1].strip()
        try:
            row_id = int(lookup)
        except Exception:
            return None
        if row_id <= 0:
            return None
        row = session.get(IngredienteIreks, row_id)
        return self._from_ireks(row) if row is not None else None

    def _get_std(self, session: Session, ingredient_id: str) -> IngredientDetail | None:
        lookup = ingredient_id
        if lookup.lower().startswith("std:"):
            lookup = lookup.split(":", 1)[1].strip()
        if not lookup:
            return None
        row = session.get(IngredienteStd, lookup)
        return self._from_std(row) if row is not None else None

    @staticmethod
    def _from_ireks(row: IngredienteIreks) -> IngredientDetail:
        return IngredientDetail(
            id=f"ireks:{int(row.id or 0)}",
            codigo=str(row.articulo_referencia or row.articulo_id or ""),
            nombre=str(row.articulo_descripcion or ""),
            fabricante_id=str(row.fabricante_id or ""),
            proveedor_id=str(row.distribuidor_id or ""),
            familia_id=str(row.articulo_familia_id or ""),
            subfamilia_id=str(row.articulo_subfamilia_id or ""),
            unidad=str(row.articulo_envase_unidad_medida or row.articulo_contenido_unidad or ""),
            activo=bool(getattr(row, "articulo_status_activo", True)),
            precio=0.0,
            source="ireks",
        )

    @staticmethod
    def _from_std(row: IngredienteStd) -> IngredientDetail:
        return IngredientDetail(
            id=f"std:{str(row.articulo_id or '').strip()}",
            codigo=str(row.articulo_referencia_distribuidor or row.articulo_id or ""),
            nombre=str(row.articulo_descripcion or ""),
            proveedor_id=str(row.proveedor_id or ""),
            familia_id=str(row.articulo_familia_id or ""),
            subfamilia_id=str(row.articulo_subfamilia_id or ""),
            unidad=str(row.formato_unidad or ""),
            activo=bool(getattr(row, "activo", True)),
            precio=float(getattr(row, "pvp_formato", 0.0) or 0.0),
            source="std",
        )

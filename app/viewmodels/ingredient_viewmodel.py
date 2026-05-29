from dataclasses import dataclass
import re
from typing import Any, Generic, TypeVar, cast
from uuid import uuid4

from sqlmodel import Session
from sqlmodel import col, select

from app.models import IngredienteIreks, IngredienteStd, MateriaPrimaPrecio
from app.repositories.ingredient_repository import (
    IngredientWarehouseRepository,
    IngredientIreksRepository,
    IngredientRepository,
    IngredientStdRepository,
)

IngredientModel = TypeVar("IngredientModel", IngredienteIreks, IngredienteStd)


@dataclass
class MateriaPrimaListItem:
    articulo_id: str
    articulo_referencia_distribuidor: str
    articulo_descripcion: str
    proveedor_id: str
    distribuidor_nombre: str
    articulo_grupo_id: str
    articulo_familia_id: str
    articulo_subfamilia_id: str
    categoria: str
    formato: str
    formato_cantidad: float
    formato_unidad: str
    pvp_formato: float
    pvp_unidad_medida: float
    activo: bool

    @property
    def distribuidor_id(self) -> str:
        return self.proveedor_id


class IngredientViewModel(Generic[IngredientModel]):
    def __init__(self, repository: IngredientRepository[IngredientModel]) -> None:
        self.repository = repository

    def list(
        self, session: Session, term: str = "", familia: str = "", subfamilia: str = "", **kwargs: Any
    ) -> list[Any]:
        return self.repository.search(session, term, familia, subfamilia, **kwargs)

    def create(self, session: Session, payload: dict) -> IngredientModel:
        entity = self.repository.model(**payload)
        return self.repository.create(session, entity)

    def update(self, session: Session, entity_id: str | int, payload: dict) -> IngredientModel:
        entity = self.repository.get_by_id(session, entity_id)
        if not entity:
            raise ValueError("Ingrediente no encontrado")
        for key, value in payload.items():
            setattr(entity, key, value)
        return self.repository.update(session, entity)

    def delete(self, session: Session, entity_id: str | int) -> bool:
        return self.repository.delete(session, entity_id)


class IngredientIreksViewModel(IngredientViewModel[IngredienteIreks]):
    def __init__(self) -> None:
        super().__init__(IngredientIreksRepository())
        self.repository = cast(IngredientIreksRepository, self.repository)

    def list(
        self,
        session: Session,
        term: str = "",
        familia: str = "",
        subfamilia: str = "",
        fabricante_id: str = "",
        active_filter: str = "all",
        distribuidor_id_filter: str = "",
        **kwargs: Any,
    ) -> list[IngredienteIreks]:
        return self.repository.search(
            session,
            term,
            familia,
            subfamilia,
            fabricante_id=fabricante_id,
            active_filter=active_filter,
            distribuidor_id_filter=distribuidor_id_filter,
        )

    def create(self, session: Session, payload: dict) -> IngredienteIreks:
        payload = dict(payload)
        self._normalize_status_fields(payload)
        self._normalize_category(payload)
        self._compute_envase_total(payload)
        self._compute_transport_totals(payload)
        return super().create(session, payload)

    def update(self, session: Session, entity_id: str | int, payload: dict) -> IngredienteIreks:
        payload = dict(payload)
        current = self.repository.get_by_id(session, entity_id)
        current_activo = bool(getattr(current, "articulo_status_activo", True)) if current else True
        current_en_lista = bool(getattr(current, "articulo_status_en_lista", False)) if current else False
        self._normalize_status_fields(payload, current_activo=current_activo, current_en_lista=current_en_lista)
        self._normalize_category(payload)
        self._compute_envase_total(payload)
        self._compute_transport_totals(payload)
        return super().update(session, entity_id, payload)

    def _normalize_category(self, payload: dict) -> None:
        if "categoria" in payload:
            payload["categoria"] = str(payload.get("categoria") or "").strip().lower()

    def _compute_envase_total(self, payload: dict) -> None:
        cantidad = self._to_float(payload.get("articulo_envase_cantidad"))
        peso = self._to_float(payload.get("articulo_envase_peso"))
        if "articulo_contenido_unidad" in payload:
            payload["articulo_contenido_unidad"] = str(payload.get("articulo_contenido_unidad") or "").strip()
        payload["articulo_envase_cantidad"] = cantidad
        payload["articulo_envase_peso"] = peso
        payload["articulo_envase_peso_total"] = cantidad * peso

    def _compute_transport_totals(self, payload: dict) -> None:
        cajas_capa = self._to_float(payload.get("transporte_cajas_por_capa"))
        capas = self._to_float(payload.get("transporte_capas_por_pallet"))
        envase_cantidad = self._to_float(payload.get("articulo_envase_cantidad"))
        envase_peso = self._to_float(payload.get("articulo_envase_peso"))
        cajas_pallet = cajas_capa * capas
        unidades_pallet = cajas_pallet * envase_cantidad
        kg_pallet = unidades_pallet * envase_peso
        if any(key in payload for key in ("transporte_cajas_por_capa", "transporte_capas_por_pallet")):
            payload["transporte_cajas_por_capa"] = cajas_capa
            payload["transporte_capas_por_pallet"] = capas
            payload["transporte_cajas_por_pallet"] = cajas_pallet
            payload["transporte_unidades_por_pallet"] = unidades_pallet
            payload["transporte_kg_por_pallet"] = kg_pallet
            payload["transporte_pallet_tipo"] = str(payload.get("transporte_pallet_tipo") or "").strip()
            payload["transporte_observaciones"] = str(payload.get("transporte_observaciones") or "").strip()

    def _to_float(self, value) -> float:
        if value in (None, ""):
            return 0.0
        try:
            return float(str(value).replace(",", ".").strip())
        except Exception:
            return 0.0

    def _to_bool(self, value, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "si", "sí", "s"}:
            return True
        if text in {"0", "false", "no", "n", ""}:
            return False
        return default

    def _normalize_status_fields(
        self,
        payload: dict,
        *,
        current_activo: bool = True,
        current_en_lista: bool = False,
    ) -> None:
        has_legacy_active = "activo" in payload
        has_status_activo = "articulo_status_activo" in payload
        has_status_en_lista = "articulo_status_en_lista" in payload

        if not has_legacy_active and not has_status_activo and not has_status_en_lista:
            return

        if has_status_activo:
            status_activo = self._to_bool(payload.get("articulo_status_activo"), default=current_activo)
        elif has_legacy_active:
            status_activo = self._to_bool(payload.get("activo"), default=current_activo)
        else:
            status_activo = current_activo

        if has_status_en_lista:
            status_en_lista = self._to_bool(payload.get("articulo_status_en_lista"), default=current_en_lista)
        elif has_status_activo or has_legacy_active:
            status_en_lista = current_en_lista
        else:
            status_en_lista = current_en_lista

        payload["articulo_status_activo"] = status_activo
        payload["articulo_status_en_lista"] = status_en_lista


class IngredientStdViewModel(IngredientViewModel[IngredienteStd]):
    def __init__(self) -> None:
        super().__init__(IngredientStdRepository())
        self.repository = cast(IngredientStdRepository, self.repository)
        self._distributor_name_cache: dict[str, str] | None = None

    def list(
        self,
        session: Session,
        term: str = "",
        familia: str = "",
        subfamilia: str = "",
        active_filter: str = "all",
        **kwargs: Any,
    ) -> list[Any]:
        rows = self.repository.search(session, term, familia, subfamilia, active_filter=active_filter)
        articulo_ids = [str(row.articulo_id or "").strip() for row in rows if str(row.articulo_id or "").strip()]
        latest_price_by_articulo: dict[str, float] = {}
        if articulo_ids:
            price_rows = list(
                session.exec(
                    select(MateriaPrimaPrecio)
                    .where(col(MateriaPrimaPrecio.articulo_id).in_(articulo_ids))
                    .order_by(
                        col(MateriaPrimaPrecio.articulo_id),
                        col(MateriaPrimaPrecio.fecha_precio).desc(),
                        col(MateriaPrimaPrecio.id).desc(),
                    )
                )
            )
            for price in price_rows:
                aid = str(price.articulo_id or "").strip()
                if aid and aid not in latest_price_by_articulo:
                    latest_price_by_articulo[aid] = float(price.costo_neto or 0.0)
        pending_persist = False
        if self._distributor_name_cache is None:
            self._distributor_name_cache = self.repository.distributor_name_map(session)
        distributor_name_by_id = self._distributor_name_cache or {}
        if any(str(row.distribuidor_id or "") not in distributor_name_by_id for row in rows):
            self._distributor_name_cache = self.repository.distributor_name_map(session)
            distributor_name_by_id = self._distributor_name_cache
        result: list[MateriaPrimaListItem] = []
        for row in rows:
            fmt = str(row.formato or "").strip()
            qty = float(row.formato_cantidad or 0.0)
            unit = str(row.formato_unidad or "").strip()
            if not fmt or qty <= 0:
                inferred_fmt, inferred_qty, inferred_unit = self._infer_format_from_text(str(row.articulo_descripcion or ""))
                if not fmt and inferred_fmt:
                    fmt = inferred_fmt
                    row.formato = inferred_fmt
                    pending_persist = True
                if qty <= 0 and inferred_qty > 0:
                    qty = inferred_qty
                    row.formato_cantidad = inferred_qty
                    pending_persist = True
                if (not unit or unit.lower() == "kg") and inferred_unit:
                    unit = inferred_unit
                    row.formato_unidad = inferred_unit
                    pending_persist = True
            aid = str(row.articulo_id or "").strip()
            pvp_formato = float(latest_price_by_articulo.get(aid, 0.0))
            pvp_unidad = (pvp_formato / qty) if qty > 0 else 0.0
            result.append(
                MateriaPrimaListItem(
                    articulo_id=str(row.articulo_id or ""),
                    articulo_referencia_distribuidor=str(row.articulo_referencia_distribuidor or ""),
                    articulo_descripcion=str(row.articulo_descripcion or ""),
                    proveedor_id=str(row.proveedor_id or ""),
                    distribuidor_nombre=str(distributor_name_by_id.get(str(row.proveedor_id or ""), "")),
                    articulo_grupo_id=str(row.articulo_grupo_id or ""),
                    articulo_familia_id=str(row.articulo_familia_id or ""),
                    articulo_subfamilia_id=str(row.articulo_subfamilia_id or ""),
                    categoria=str(row.categoria or ""),
                    formato=fmt,
                    formato_cantidad=qty,
                    formato_unidad=unit,
                    pvp_formato=pvp_formato,
                    pvp_unidad_medida=pvp_unidad,
                    activo=bool(row.activo),
                )
            )
        if pending_persist:
            session.commit()
        return result

    def create(self, session: Session, payload: dict) -> IngredienteStd:
        payload = dict(payload)
        articulo_id = str(payload.get("articulo_id") or "").strip()
        if not articulo_id:
            payload["articulo_id"] = str(uuid4())
        proveedor_id = str(payload.get("proveedor_id") or payload.get("distribuidor_id") or "").strip()
        payload["proveedor_id"] = proveedor_id
        payload["distribuidor_id"] = proveedor_id
        payload["articulo_descripcion"] = str(payload.get("articulo_descripcion") or "").strip()
        self._normalize_payload(payload)
        entity = self.repository.model(**payload)
        return self.repository.create(session, entity)

    def update(self, session: Session, entity_id: str | int, payload: dict) -> IngredienteStd:
        entity = self.repository.get_by_id(session, entity_id)
        if not entity:
            raise ValueError("Materia prima no encontrada")
        for key, value in payload.items():
            setattr(entity, key, value)
        if not str(getattr(entity, "articulo_id", "") or "").strip():
            entity.articulo_id = str(uuid4())
        if not str(getattr(entity, "proveedor_id", "") or "").strip():
            entity.proveedor_id = str(getattr(entity, "distribuidor_id", "") or "").strip()
        if not str(getattr(entity, "distribuidor_id", "") or "").strip():
            entity.distribuidor_id = str(getattr(entity, "proveedor_id", "") or "").strip()
        self._normalize_entity(entity)
        return self.repository.update(session, entity)

    def _to_float(self, value) -> float:
        if value in (None, ""):
            return 0.0
        try:
            return float(str(value).replace(",", ".").strip())
        except Exception:
            return 0.0

    def _normalize_payload(self, payload: dict) -> None:
        payload["categoria"] = str(payload.get("categoria") or "").strip().lower()
        payload["formato"] = str(payload.get("formato") or "").strip()
        payload["formato_unidad"] = str(payload.get("formato_unidad") or "kg").strip() or "kg"
        payload["formato_cantidad"] = self._to_float(payload.get("formato_cantidad"))
        payload["pvp_formato"] = self._to_float(payload.get("pvp_formato"))
        payload["pvp_unidad_medida"] = self._to_float(payload.get("pvp_unidad_medida"))

    def _normalize_entity(self, entity: IngredienteStd) -> None:
        entity.categoria = str(entity.categoria or "").strip().lower()
        entity.formato = str(entity.formato or "").strip()
        entity.formato_unidad = str(entity.formato_unidad or "kg").strip() or "kg"
        entity.formato_cantidad = self._to_float(entity.formato_cantidad)
        entity.pvp_formato = self._to_float(entity.pvp_formato)
        entity.pvp_unidad_medida = self._to_float(entity.pvp_unidad_medida)

    def _infer_format_from_text(self, text: str) -> tuple[str, float, str]:
        raw = str(text or "").upper()
        formato = ""
        for token, label in (
            ("BAGINBOX", "BAGINBOX"),
            ("BAG IN BOX", "BAGINBOX"),
            ("GARRAFA", "GARRAFA"),
            ("BOTELLA", "BOTELLA"),
            ("SACO", "SACO"),
            ("BIDON", "BIDON"),
            ("BANDEJA", "BANDEJA"),
            ("CAJA", "CAJA"),
        ):
            if token in raw:
                formato = label
                break

        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(KG|KGS|G|GR|L|LT|LTR|LTS|ML|UD|U)\b", raw)
        if not match:
            return formato, 0.0, ""

        qty = self._to_float(match.group(1))
        unit_raw = match.group(2)
        unit_map = {
            "KG": "kg",
            "KGS": "kg",
            "G": "g",
            "GR": "g",
            "L": "L",
            "LT": "L",
            "LTR": "L",
            "LTS": "L",
            "ML": "ml",
            "UD": "Ud",
            "U": "Ud",
        }
        unit = unit_map.get(unit_raw, "")
        return formato, qty, unit


class IngredientWarehouseViewModel(IngredientIreksViewModel):
    def __init__(self) -> None:
        IngredientViewModel.__init__(self, IngredientWarehouseRepository())
        self.repository = cast(IngredientWarehouseRepository, self.repository)

    def list(
        self,
        session: Session,
        term: str = "",
        familia: str = "",
        subfamilia: str = "",
        fabricante_id: str = "",
        active_filter: str = "all",
        distribuidor_id_filter: str = "",
        **kwargs: Any,
    ) -> list[IngredienteIreks]:
        return self.repository.search(
            session,
            term,
            familia,
            subfamilia,
            fabricante_id=fabricante_id,
            active_filter=active_filter,
            distribuidor_id_filter=distribuidor_id_filter,
        )

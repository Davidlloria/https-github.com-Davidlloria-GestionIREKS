from __future__ import annotations

from datetime import date
from datetime import datetime
from typing import Any, cast

from sqlmodel import Session, col, select

from app.models import MateriaPrimaPrecio
from app.models import TarifaPrecioIreks


class DbMaintenancePriceImportService:
    _PROFILE_KEYS = {"tarifa_precios_ireks", "precios_materias_primas"}

    def handles(self, profile_key: str) -> bool:
        return profile_key in self._PROFILE_KEYS

    def normalize_payload(self, profile_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        if profile_key == "tarifa_precios_ireks":
            return self._normalize_tarifa_payload(payload)
        if profile_key == "precios_materias_primas":
            return self._normalize_materia_prima_precio_payload(payload)
        raise ValueError(f"Perfil de normalizacion no soportado: {profile_key}")

    def build_lookup(self, *, session: Session, profile_key: str, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        if profile_key == "tarifa_precios_ireks":
            return self._build_tarifa_lookup(session, payloads)
        if profile_key == "precios_materias_primas":
            return self._build_materia_prima_precio_lookup(session, payloads)
        raise ValueError(f"Perfil de lookup no soportado: {profile_key}")

    def find_match(self, *, profile_key: str, payload: dict[str, Any], lookup: dict[str, Any]) -> Any | None:
        if profile_key == "tarifa_precios_ireks":
            return self._find_tarifa_match(payload, lookup)
        if profile_key == "precios_materias_primas":
            return self._find_materia_prima_precio_match(payload, lookup)
        raise ValueError(f"Perfil de coincidencia no soportado: {profile_key}")

    def create_entity(self, *, session: Session, profile_key: str, payload: dict[str, Any]) -> Any:
        if profile_key == "tarifa_precios_ireks":
            entity = TarifaPrecioIreks(
                articulo_id=str(payload.get("articulo_id") or "").strip(),
                tarifa_ano=int(payload.get("tarifa_ano") or 0),
                precio_fabricante=float(payload.get("precio_fabricante") or 0.0),
                precio_distribuidor=float(payload.get("precio_distribuidor") or 0.0),
            )
        elif profile_key == "precios_materias_primas":
            entity = MateriaPrimaPrecio(
                articulo_id=str(payload.get("articulo_id") or "").strip(),
                fecha_precio=cast(date, payload["fecha_precio"]),
                costo_neto=float(payload.get("costo_neto") or 0.0),
            )
        else:
            raise ValueError(f"Perfil no soportado para insercion: {profile_key}")
        session.add(entity)
        session.flush()
        return entity

    def apply_updates(self, *, profile_key: str, entity: Any, payload: dict[str, Any]) -> bool:
        changed = False
        if profile_key == "tarifa_precios_ireks":
            for field in ("precio_fabricante", "precio_distribuidor"):
                if field not in payload:
                    continue
                value = payload[field]
                if getattr(entity, field) != value:
                    setattr(entity, field, value)
                    changed = True
            return changed
        if profile_key == "precios_materias_primas":
            if "costo_neto" in payload and getattr(entity, "costo_neto") != payload["costo_neto"]:
                setattr(entity, "costo_neto", payload["costo_neto"])
                changed = True
            return changed
        raise ValueError(f"Perfil no soportado para actualizacion: {profile_key}")

    def update_lookup_after_insert(self, *, profile_key: str, lookup: dict[str, Any], entity: Any) -> None:
        if profile_key == "tarifa_precios_ireks":
            key = (str(entity.articulo_id or "").strip(), int(entity.tarifa_ano or 0))
            lookup["by_pk"][key] = entity
            return
        if profile_key == "precios_materias_primas":
            key = (str(entity.articulo_id or "").strip(), entity.fecha_precio)
            lookup["by_pk"][key] = entity
            return
        raise ValueError(f"Perfil no soportado para actualizar lookup: {profile_key}")

    def _build_tarifa_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        articulo_ids = {str(payload.get("articulo_id") or "").strip() for payload in payloads}
        articulo_ids.discard("")
        years = {int(payload.get("tarifa_ano") or 0) for payload in payloads}
        years.discard(0)
        rows: list[TarifaPrecioIreks] = []
        if articulo_ids and years:
            rows = list(
                session.exec(
                    select(TarifaPrecioIreks).where(
                        col(TarifaPrecioIreks.articulo_id).in_(articulo_ids),
                        col(TarifaPrecioIreks.tarifa_ano).in_(years),
                    )
                )
            )
        by_pk = {
            (str(row.articulo_id or "").strip(), int(row.tarifa_ano or 0)): row
            for row in rows
            if str(row.articulo_id or "").strip() and int(row.tarifa_ano or 0) > 0
        }
        return {"by_pk": by_pk}

    def _find_tarifa_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> TarifaPrecioIreks | None:
        key = (str(payload.get("articulo_id") or "").strip(), int(payload.get("tarifa_ano") or 0))
        if not key[0] or key[1] <= 0:
            return None
        return lookup["by_pk"].get(key)

    def _build_materia_prima_precio_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        articulo_ids = {str(payload.get("articulo_id") or "").strip() for payload in payloads}
        articulo_ids.discard("")
        fechas = {payload.get("fecha_precio") for payload in payloads if payload.get("fecha_precio")}
        rows: list[MateriaPrimaPrecio] = []
        if articulo_ids and fechas:
            rows = list(
                session.exec(
                    select(MateriaPrimaPrecio).where(
                        col(MateriaPrimaPrecio.articulo_id).in_(articulo_ids),
                        col(MateriaPrimaPrecio.fecha_precio).in_(fechas),
                    )
                )
            )
        by_pk = {
            (str(row.articulo_id or "").strip(), row.fecha_precio): row
            for row in rows
            if str(row.articulo_id or "").strip() and row.fecha_precio
        }
        return {"by_pk": by_pk}

    def _find_materia_prima_precio_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> MateriaPrimaPrecio | None:
        key = (str(payload.get("articulo_id") or "").strip(), payload.get("fecha_precio"))
        if not key[0] or not key[1]:
            return None
        return lookup["by_pk"].get(key)

    def _normalize_tarifa_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        articulo_id = str(data.get("articulo_id") or "").strip()
        if not articulo_id:
            raise ValueError("Campo obligatorio vacio: articulo_id")
        data["articulo_id"] = articulo_id

        ano_raw = str(data.get("tarifa_ano") or "").strip()
        if not ano_raw:
            raise ValueError("Campo obligatorio vacio: tarifa_ano")
        try:
            tarifa_ano = int(float(ano_raw.replace(",", ".")))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Ano de tarifa invalido: {ano_raw}") from exc
        if tarifa_ano < 1900 or tarifa_ano > 2100:
            raise ValueError(f"Ano de tarifa fuera de rango: {tarifa_ano}")
        data["tarifa_ano"] = tarifa_ano
        data["precio_fabricante"] = self._to_float(data.get("precio_fabricante"))
        data["precio_distribuidor"] = self._to_float(data.get("precio_distribuidor"))
        return data

    def _normalize_materia_prima_precio_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        articulo_id = str(data.get("articulo_id") or "").strip()
        if not articulo_id:
            raise ValueError("Campo obligatorio vacio: articulo_id")
        data["articulo_id"] = articulo_id

        fecha = self._to_date(data.get("fecha_precio"))
        if fecha is None:
            raise ValueError("Campo obligatorio vacio o invalido: fecha_precio")
        data["fecha_precio"] = fecha
        data["costo_neto"] = self._to_float(data.get("costo_neto"))
        return data

    def _to_float(self, value: Any) -> float:
        if value in (None, ""):
            return 0.0
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return 0.0
        try:
            return float(text.replace(",", "."))
        except Exception:  # noqa: BLE001
            return 0.0

    def _to_date(self, value: Any) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip()
        if not text:
            return None
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text).date()
        except ValueError as exc:  # noqa: BLE001
            raise ValueError(f"Fecha invalida: {value}") from exc

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlmodel import Session, select

from app.core.database import engine
from app.core.pagination import DEFAULT_PAGE_LIMIT, page_items
from app.models import IngredienteStd, MateriaPrimaPrecio, MateriaPrimaValorNutricional, Proveedor
from app.schemas.ingredients import (
    IngredientActiveUpdate,
    IngredientStdCreate,
    IngredientStdRead,
    IngredientStdUpdate,
    MateriaPrimaPrecioRead,
    NutritionValues,
)


class IngredientStdService:
    def __init__(self, vm=None) -> None:
        if vm is None:
            from app.viewmodels.ingredient_viewmodel import IngredientStdViewModel

            vm = IngredientStdViewModel()
        self.vm = vm

    def api_list_payload(
        self,
        *,
        search: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
        activity_filter: str = "all",
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> list[IngredientStdRead]:
        with Session(engine) as session:
            rows = self.vm.list(
                session,
                term=search,
                familia=familia_id,
                subfamilia=subfamilia_id,
                active_filter=activity_filter,
            )
        return IngredientStdRead.list_from_entities(page_items(rows, limit=limit, offset=offset))

    def api_detail_payload(self, articulo_id: str) -> IngredientStdRead | None:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return None
        with Session(engine) as session:
            row = session.get(IngredienteStd, clean_articulo_id)
            if row is None:
                return None
            provider_map = self.vm.repository.distributor_name_map(session)
            payload = IngredientStdRead.from_entity(row)
            payload.distribuidor_nombre = provider_map.get(str(row.proveedor_id or ""), "")
            return payload

    def providers(self) -> list[Proveedor]:
        with Session(engine) as session:
            return list(session.exec(select(Proveedor).order_by(Proveedor.proveedor_nombre_comercial)))

    def price_history(self, articulo_id: str) -> list[MateriaPrimaPrecio]:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return []
        with Session(engine) as session:
            return list(
                session.exec(
                    select(MateriaPrimaPrecio)
                    .where(MateriaPrimaPrecio.articulo_id == clean_articulo_id)
                    .order_by(text("fecha_precio DESC"), text("id DESC"))
                )
            )

    def price_history_payload(self, articulo_id: str) -> list[MateriaPrimaPrecioRead]:
        return MateriaPrimaPrecioRead.list_from_entities(self.price_history(articulo_id))

    def nutrition(self, articulo_id: str) -> MateriaPrimaValorNutricional | None:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return None
        with Session(engine) as session:
            return session.get(MateriaPrimaValorNutricional, clean_articulo_id)

    def nutrition_payload(self, articulo_id: str) -> NutritionValues | None:
        row = self.nutrition(articulo_id)
        return NutritionValues.from_entity(row) if row is not None else None

    def upsert_price(self, articulo_id: str, pvp_formato: float, price_date: date | None = None) -> None:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id or float(pvp_formato or 0.0) <= 0:
            return
        day = price_date if isinstance(price_date, date) else date.today()
        with Session(engine) as session:
            existing = session.exec(
                select(MateriaPrimaPrecio).where(
                    MateriaPrimaPrecio.articulo_id == clean_articulo_id,
                    MateriaPrimaPrecio.fecha_precio == day,
                )
            ).first()
            if existing:
                existing.costo_neto = float(pvp_formato or 0.0)
                session.add(existing)
            else:
                session.add(
                    MateriaPrimaPrecio(
                        articulo_id=clean_articulo_id,
                        fecha_precio=day,
                        costo_neto=float(pvp_formato or 0.0),
                    )
                )
            session.commit()

    def delete_price(self, price_id: int) -> None:
        if int(price_id or 0) <= 0:
            return
        with Session(engine) as session:
            entity = session.get(MateriaPrimaPrecio, int(price_id))
            if entity:
                session.delete(entity)
                session.commit()

    def upsert_nutrition(self, articulo_id: str, nutrition: dict[str, float]) -> None:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return
        with Session(engine) as session:
            row = session.get(MateriaPrimaValorNutricional, clean_articulo_id)
            if row is None:
                row = MateriaPrimaValorNutricional(articulo_id=clean_articulo_id, **nutrition)
                session.add(row)
            else:
                for key, value in nutrition.items():
                    setattr(row, key, float(value or 0.0))
                session.add(row)
            session.commit()

    def create_article(self, payload: dict, *, price_date: date | None, nutrition: dict[str, float]) -> str:
        with Session(engine) as session:
            created = self.vm.create(session, payload)
            articulo_id = str(created.articulo_id or "")
        self.upsert_price(articulo_id, float(payload.get("pvp_formato") or 0.0), price_date)
        self.upsert_nutrition(articulo_id, nutrition)
        return articulo_id

    def create_from_payload(self, payload: IngredientStdCreate | dict) -> IngredientStdRead:
        data = self._payload_dict(payload, IngredientStdCreate, exclude_none=True)
        articulo_id = self.create_article(data, price_date=None, nutrition={})
        created = self.api_detail_payload(articulo_id)
        if created is None:
            raise ValueError("No se pudo crear la materia prima.")
        return created

    def update_article(
        self,
        articulo_id: str,
        payload: dict,
        *,
        price_date: date | None,
        nutrition: dict[str, float],
    ) -> None:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return
        with Session(engine) as session:
            self.vm.update(session, clean_articulo_id, payload)
        self.upsert_price(clean_articulo_id, float(payload.get("pvp_formato") or 0.0), price_date)
        self.upsert_nutrition(clean_articulo_id, nutrition)

    def update_from_payload(self, articulo_id: str, payload: IngredientStdUpdate | dict) -> IngredientStdRead | None:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return None
        data = self._payload_dict(payload, IngredientStdUpdate, exclude_none=True)
        try:
            self.update_article(clean_articulo_id, data, price_date=None, nutrition={})
        except ValueError:
            return None
        return self.api_detail_payload(clean_articulo_id)

    def delete_if_exists(self, articulo_id: str) -> bool:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return False
        with Session(engine) as session:
            row = session.get(IngredienteStd, clean_articulo_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def delete_blockers(self, articulo_id: str) -> list[str]:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return []
        with engine.begin() as conn:
            counts = {
                "pedidos_items": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM pedidos_items WHERE articulo_id = ?",
                    (clean_articulo_id,),
                ).scalar_one(),
                "albaranes_items": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM albaranes_items WHERE articulo_id = ?",
                    (clean_articulo_id,),
                ).scalar_one(),
                "facturas_items": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM facturas_items WHERE articulo_id = ?",
                    (clean_articulo_id,),
                ).scalar_one(),
                "pedidos_pendientes": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM pedidos_pendientes WHERE articulo_id = ?",
                    (clean_articulo_id,),
                ).scalar_one(),
                "almacen_movimientos": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM almacen_movimientos WHERE articulo_id = ?",
                    (clean_articulo_id,),
                ).scalar_one(),
                "almacen_stock": conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM almacen_stock WHERE articulo_id = ?",
                    (clean_articulo_id,),
                ).scalar_one(),
            }
        labels = {
            "pedidos_items": "linea(s) de pedido",
            "albaranes_items": "linea(s) de albaran",
            "facturas_items": "linea(s) de factura",
            "pedidos_pendientes": "pendiente(s) de pedido",
            "almacen_movimientos": "movimiento(s) de almacen",
            "almacen_stock": "registro(s) de stock",
        }
        return [f"{int(count)} {labels[name]}" for name, count in counts.items() if int(count or 0) > 0]

    def update_active(self, articulo_id: str, activo: bool) -> None:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return
        with Session(engine) as session:
            self.vm.update(session, clean_articulo_id, {"activo": bool(activo)})

    def update_active_from_payload(self, articulo_id: str, payload: IngredientActiveUpdate | dict) -> IngredientStdRead | None:
        data = self._payload_dict(payload, IngredientActiveUpdate)
        try:
            self.update_active(articulo_id, bool(data["activo"]))
        except ValueError:
            return None
        return self.api_detail_payload(articulo_id)

    @staticmethod
    def _payload_dict(payload: object, schema_cls: type, *, exclude_none: bool = False) -> dict:
        if isinstance(payload, dict):
            model = schema_cls.model_validate(payload)
        else:
            model = schema_cls.model_validate(payload)
        return model.model_dump(exclude_none=exclude_none)

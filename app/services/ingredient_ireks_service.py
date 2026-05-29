from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.core.database import engine
from sqlalchemy import text

from app.models import (
    AlmacenMovimiento,
    Distribuidor,
    Envase,
    Fabricante,
    Familia,
    IngredienteIreks,
    MateriaPrimaValorNutricional,
    PedidoItem,
    ReferenciaDistribuidor,
    Subfamilia,
    TarifaPrecioIreks,
)
from app.schemas.ingredients import (
    CatalogOption,
    IngredientIreksCatalogsPayload as ApiIngredientIreksCatalogsPayload,
    IngredientIreksCreate,
    IngredientIreksListPayload as ApiIngredientIreksListPayload,
    IngredientIreksRead,
    IngredientIreksUpdate,
    NutritionValues,
    TarifaPrecioIreksCreate,
    TarifaPrecioIreksRead,
    TarifaPrecioIreksUpdate,
)
from app.services.import_service import ImportService


@dataclass
class IngredientIreksCatalogs:
    distribuidores: list[Distribuidor]
    fabricantes: list[Fabricante]
    familias: list[Familia]
    subfamilias: list[Subfamilia]
    envases: list[Envase]


@dataclass
class IngredientIreksListPayload:
    rows: list
    catalogs: IngredientIreksCatalogs


class IngredientIreksService:
    def __init__(self, vm=None) -> None:
        if vm is None:
            from app.viewmodels.ingredient_viewmodel import IngredientIreksViewModel

            vm = IngredientIreksViewModel()
        self.vm = vm
        self.import_service = ImportService()

    def list_payload(
        self,
        *,
        search: str,
        familia_id: str,
        subfamilia_id: str,
        fabricante_id: str,
        activity_filter: str,
        distributor_filter_id: str,
    ) -> IngredientIreksListPayload:
        with Session(engine) as session:
            catalogs = self.catalogs(session)
            rows = self.vm.list(
                session,
                search,
                familia_id,
                subfamilia_id,
                fabricante_id,
                activity_filter,
                distributor_filter_id,
            )
        return IngredientIreksListPayload(rows=rows, catalogs=catalogs)

    def api_list_payload(
        self,
        *,
        search: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
        fabricante_id: str = "",
        activity_filter: str = "all",
        distributor_filter_id: str = "",
    ) -> ApiIngredientIreksListPayload:
        payload = self.list_payload(
            search=search,
            familia_id=familia_id,
            subfamilia_id=subfamilia_id,
            fabricante_id=fabricante_id,
            activity_filter=activity_filter,
            distributor_filter_id=distributor_filter_id,
        )
        return ApiIngredientIreksListPayload(
            rows=IngredientIreksRead.list_from_entities(payload.rows),
            catalogs=self.api_catalogs_payload(payload.catalogs),
        )

    def api_detail_payload(self, row_id: int) -> IngredientIreksRead | None:
        if int(row_id or 0) <= 0:
            return None
        with Session(engine) as session:
            row = session.get(IngredienteIreks, int(row_id))
        return IngredientIreksRead.from_entity(row) if row is not None else None

    def api_catalogs_payload(
        self,
        catalogs: IngredientIreksCatalogs | None = None,
    ) -> ApiIngredientIreksCatalogsPayload:
        catalogs = catalogs or self.catalogs()
        return ApiIngredientIreksCatalogsPayload(
            distribuidores=[
                CatalogOption(
                    id=str(row.distribuidor_id or ""),
                    name=(str(row.distribuidor_nombre_comercial or "").strip() or str(row.distribuidor_razon_social or "").strip()),
                    code=str(row.distribuidor_codigo or ""),
                )
                for row in catalogs.distribuidores
            ],
            fabricantes=[
                CatalogOption(
                    id=str(row.fabricante_id or ""),
                    name=str(row.fabricante_nombre or ""),
                    code=str(row.fabricante_codigo or ""),
                )
                for row in catalogs.fabricantes
            ],
            familias=[
                CatalogOption(
                    id=str(row.articulo_familia_id or ""),
                    name=str(row.articulo_familia_nombre or ""),
                    code=str(row.articulo_familia_codigo or ""),
                    parent_id=str(row.fabricante_id or ""),
                )
                for row in catalogs.familias
            ],
            subfamilias=[
                CatalogOption(
                    id=str(row.articulo_subfamilia_id or ""),
                    name=str(row.articulo_subfamilia_nombre or ""),
                    code=str(row.articulo_subfamilia_codigo or ""),
                    parent_id=str(row.articulo_familia_id or ""),
                )
                for row in catalogs.subfamilias
            ],
            envases=[
                CatalogOption(
                    id=str(row.envase_id or ""),
                    name=str(row.envase_nombre or ""),
                    code=str(row.envase_codigo or ""),
                )
                for row in catalogs.envases
            ],
        )

    def catalogs(self, session: Session | None = None) -> IngredientIreksCatalogs:
        if session is not None:
            return self._catalogs(session)
        with Session(engine) as owned_session:
            return self._catalogs(owned_session)

    def _catalogs(self, session: Session) -> IngredientIreksCatalogs:
        return IngredientIreksCatalogs(
            distribuidores=list(
                session.exec(
                    select(Distribuidor).order_by(
                        Distribuidor.distribuidor_nombre_comercial,
                        Distribuidor.distribuidor_razon_social,
                    )
                )
            ),
            fabricantes=list(
                session.exec(select(Fabricante).order_by(Fabricante.fabricante_nombre, Fabricante.fabricante_id))
            ),
            familias=list(
                session.exec(select(Familia).order_by(Familia.articulo_familia_codigo, Familia.articulo_familia_nombre))
            ),
            subfamilias=list(
                session.exec(
                    select(Subfamilia).order_by(
                        Subfamilia.articulo_subfamilia_codigo,
                        Subfamilia.articulo_subfamilia_nombre,
                    )
                )
            ),
            envases=list(session.exec(select(Envase).order_by(Envase.envase_nombre, Envase.envase_id))),
        )

    def distributor_reference(self, articulo_id: str, distribuidor_id: str) -> ReferenciaDistribuidor | None:
        clean_articulo_id = str(articulo_id or "").strip()
        clean_distribuidor_id = str(distribuidor_id or "").strip()
        if not clean_articulo_id or not clean_distribuidor_id:
            return None
        with Session(engine) as session:
            return session.get(ReferenciaDistribuidor, (clean_articulo_id, clean_distribuidor_id))

    def movement_payload(self, articulo_id: str) -> tuple[list[AlmacenMovimiento], list[IngredienteIreks]]:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return [], []
        with Session(engine) as session:
            moves = list(
                session.exec(
                    select(AlmacenMovimiento)
                    .where(AlmacenMovimiento.articulo_id == clean_articulo_id)
                    .order_by(text("fecha_pedido DESC"), text("id DESC"))
                )
            )
            items = list(session.exec(select(IngredienteIreks).where(IngredienteIreks.articulo_id == clean_articulo_id)))
        return moves, items

    def pedido_items(self, articulo_id: str) -> list[PedidoItem]:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return []
        with Session(engine) as session:
            return list(
                session.exec(
                    select(PedidoItem)
                    .where(PedidoItem.articulo_id == clean_articulo_id)
                    .order_by(text("pedido_item_fecha DESC"), text("pedido_id DESC"))
                )
            )

    def nutrition(self, articulo_id: str) -> MateriaPrimaValorNutricional | None:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return None
        with Session(engine) as session:
            return session.get(MateriaPrimaValorNutricional, clean_articulo_id)

    def nutrition_payload(self, articulo_id: str) -> NutritionValues | None:
        row = self.nutrition(articulo_id)
        return NutritionValues.from_entity(row) if row is not None else None

    def save_nutrition(self, articulo_id: str, values: dict[str, float]) -> None:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return
        with Session(engine) as session:
            nutrition = session.get(MateriaPrimaValorNutricional, clean_articulo_id)
            if nutrition is None:
                nutrition = MateriaPrimaValorNutricional(articulo_id=clean_articulo_id, **values)
                session.add(nutrition)
            else:
                for key, value in values.items():
                    setattr(nutrition, key, value)
                session.add(nutrition)
            session.commit()

    def tarifas(self, articulo_id: str) -> list[TarifaPrecioIreks]:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return []
        with Session(engine) as session:
            return list(
                session.exec(
                    select(TarifaPrecioIreks)
                    .where(TarifaPrecioIreks.articulo_id == clean_articulo_id)
                    .order_by(text("tarifa_ano DESC"), text("id DESC"))
                )
            )

    def tarifas_payload(self, articulo_id: str) -> list[TarifaPrecioIreksRead]:
        return TarifaPrecioIreksRead.list_from_entities(self.tarifas(articulo_id))

    def get_tarifa(self, tarifa_id: int) -> TarifaPrecioIreks | None:
        if not tarifa_id:
            return None
        with Session(engine) as session:
            return session.get(TarifaPrecioIreks, tarifa_id)

    def upsert_tarifa(
        self,
        *,
        articulo_id: str,
        tarifa_ano: int,
        precio_fabricante: float,
        precio_distribuidor: float,
        descuento_pct: float,
    ) -> None:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return
        with Session(engine) as session:
            existing = session.exec(
                select(TarifaPrecioIreks).where(
                    TarifaPrecioIreks.articulo_id == clean_articulo_id,
                    TarifaPrecioIreks.tarifa_ano == tarifa_ano,
                )
            ).first()
            if existing is None:
                session.add(
                    TarifaPrecioIreks(
                        articulo_id=clean_articulo_id,
                        tarifa_ano=tarifa_ano,
                        precio_fabricante=precio_fabricante,
                        precio_distribuidor=precio_distribuidor,
                        descuento_pct=descuento_pct,
                    )
                )
            else:
                existing.precio_fabricante = precio_fabricante
                existing.precio_distribuidor = precio_distribuidor
                existing.descuento_pct = descuento_pct
                session.add(existing)
            session.commit()

    def upsert_tarifa_from_payload(self, payload: TarifaPrecioIreksCreate | dict) -> TarifaPrecioIreksRead:
        data = self._payload_dict(payload, TarifaPrecioIreksCreate)
        self.upsert_tarifa(
            articulo_id=str(data["articulo_id"]),
            tarifa_ano=int(data["tarifa_ano"]),
            precio_fabricante=float(data.get("precio_fabricante") or 0.0),
            precio_distribuidor=float(data.get("precio_distribuidor") or 0.0),
            descuento_pct=float(data.get("descuento_pct") or 0.0),
        )
        with Session(engine) as session:
            row = session.exec(
                select(TarifaPrecioIreks).where(
                    TarifaPrecioIreks.articulo_id == str(data["articulo_id"]),
                    TarifaPrecioIreks.tarifa_ano == int(data["tarifa_ano"]),
                )
            ).first()
        if row is None:
            raise ValueError("No se pudo guardar la tarifa.")
        return TarifaPrecioIreksRead.from_entity(row)

    def update_tarifa(
        self,
        *,
        tarifa_id: int,
        tarifa_ano: int,
        precio_fabricante: float,
        precio_distribuidor: float,
        descuento_pct: float,
    ) -> bool:
        with Session(engine) as session:
            tarifa = session.get(TarifaPrecioIreks, tarifa_id)
            if tarifa is None:
                return False
            tarifa.tarifa_ano = tarifa_ano
            tarifa.precio_fabricante = precio_fabricante
            tarifa.precio_distribuidor = precio_distribuidor
            tarifa.descuento_pct = descuento_pct
            session.add(tarifa)
            session.commit()
        return True

    def update_tarifa_from_payload(self, tarifa_id: int, payload: TarifaPrecioIreksUpdate | dict) -> TarifaPrecioIreksRead | None:
        data = self._payload_dict(payload, TarifaPrecioIreksUpdate)
        updated = self.update_tarifa(
            tarifa_id=int(tarifa_id),
            tarifa_ano=int(data["tarifa_ano"]),
            precio_fabricante=float(data.get("precio_fabricante") or 0.0),
            precio_distribuidor=float(data.get("precio_distribuidor") or 0.0),
            descuento_pct=float(data.get("descuento_pct") or 0.0),
        )
        if not updated:
            return None
        row = self.get_tarifa(int(tarifa_id))
        return TarifaPrecioIreksRead.from_entity(row) if row is not None else None

    def delete_tarifa(self, tarifa_id: int) -> None:
        with Session(engine) as session:
            tarifa = session.get(TarifaPrecioIreks, tarifa_id)
            if tarifa is not None:
                session.delete(tarifa)
                session.commit()

    def delete_tarifa_if_exists(self, tarifa_id: int) -> bool:
        with Session(engine) as session:
            tarifa = session.get(TarifaPrecioIreks, int(tarifa_id))
            if tarifa is None:
                return False
            session.delete(tarifa)
            session.commit()
            return True

    def create_product(self):
        with Session(engine) as session:
            row = self.vm.create(session, {})
            row_id = row.id
            session.commit()
        return row_id

    def delete_product(self, row_id: int) -> bool:
        with Session(engine) as session:
            return self.vm.delete(session, int(row_id))

    def update_product(self, row_id: int, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.update(session, int(row_id), payload)

    def create_from_payload(self, payload: IngredientIreksCreate | dict) -> IngredientIreksRead:
        data = self._payload_dict(payload, IngredientIreksCreate)
        data = self._clean_api_payload(data)
        with Session(engine) as session:
            row = self.vm.create(session, data)
            return IngredientIreksRead.from_entity(row)

    def update_from_payload(self, row_id: int, payload: IngredientIreksUpdate | dict) -> IngredientIreksRead | None:
        if int(row_id or 0) <= 0:
            return None
        data = self._payload_dict(payload, IngredientIreksUpdate, exclude_none=True)
        data = self._clean_api_payload(data)
        try:
            with Session(engine) as session:
                row = self.vm.update(session, int(row_id), data)
                return IngredientIreksRead.from_entity(row)
        except ValueError:
            return None

    def delete_if_exists(self, row_id: int) -> bool:
        if int(row_id or 0) <= 0:
            return False
        return self.delete_product(int(row_id))

    def upsert_distributor_reference(
        self,
        *,
        articulo_id: str,
        distribuidor_id: str,
        referencia: str,
        descripcion: str,
    ) -> None:
        clean_articulo_id = str(articulo_id or "").strip()
        clean_distribuidor_id = str(distribuidor_id or "").strip()
        if not clean_articulo_id or not clean_distribuidor_id:
            return
        with Session(engine) as session:
            ref_row = session.get(ReferenciaDistribuidor, (clean_articulo_id, clean_distribuidor_id))
            if ref_row is None:
                ref_row = ReferenciaDistribuidor(
                    articulo_id=clean_articulo_id,
                    distribuidor_id=clean_distribuidor_id,
                )
            ref_row.articulo_referencia_distribuidor = str(referencia or "").strip()
            ref_row.articulo_descripcion_distribuidor = str(descripcion or "").strip()
            session.add(ref_row)
            session.commit()

    def import_products(self, file_path: str, schema: list[dict], aliases: dict[str, list[str]]) -> tuple[int, list[str]]:
        with Session(engine) as session:

            def create_row(payload: dict[str, object]) -> None:
                articulo_id = str(payload.get("articulo_id") or "").strip()
                existing = None
                if articulo_id:
                    existing = session.exec(
                        select(IngredienteIreks).where(IngredienteIreks.articulo_id == articulo_id)
                    ).first()
                if existing:
                    existing_id = existing.id
                    if existing_id is None:
                        return
                    self.vm.update(session, int(existing_id), payload)
                else:
                    self.vm.create(session, payload)

            return self.import_service.import_with_schema(
                file_path=file_path,
                schema=schema,
                create_fn=create_row,
                required_fields=["almacen_id", "articulo_id"],
                aliases=aliases,
            )

    @staticmethod
    def _payload_dict(payload: object, schema_cls: type, *, exclude_none: bool = False) -> dict:
        if isinstance(payload, dict):
            model = schema_cls.model_validate(payload)
        else:
            model = schema_cls.model_validate(payload)
        return model.model_dump(exclude_none=exclude_none)

    @staticmethod
    def _clean_api_payload(data: dict) -> dict:
        payload = dict(data)
        if not str(payload.get("articulo_id") or "").strip():
            payload.pop("articulo_id", None)
        if payload.get("id") is None:
            payload.pop("id", None)
        return payload

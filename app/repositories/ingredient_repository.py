from typing import TypeVar

from sqlalchemy import exists
from sqlmodel import Session, and_, col, or_, select

from app.models import AlmacenStock, IngredienteIreks, IngredienteStd, Proveedor
from app.repositories.base import BaseRepository

IngredientModel = TypeVar("IngredientModel", IngredienteIreks, IngredienteStd)


class IngredientRepository(BaseRepository[IngredientModel]):
    def search(
        self,
        session: Session,
        term: str = "",
        familia: str = "",
        subfamilia: str = "",
    ) -> list[IngredientModel]:
        conditions = []
        if term.strip():
            like_term = f"%{term.strip()}%"
            conditions.append(
                or_(
                    col(self.model.articulo_id).like(like_term),
                    col(self.model.articulo_descripcion).like(like_term),
                    col(self.model.articulo_familia_id).like(like_term),
                    col(self.model.articulo_subfamilia_id).like(like_term),
                )
            )
        if familia.strip():
            conditions.append(col(self.model.articulo_familia_id) == familia.strip())
        if subfamilia.strip():
            conditions.append(col(self.model.articulo_subfamilia_id) == subfamilia.strip())

        stmt = select(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(col(self.model.articulo_descripcion))
        return list(session.exec(stmt))


class IngredientIreksRepository(IngredientRepository[IngredienteIreks]):
    def __init__(self) -> None:
        super().__init__(IngredienteIreks)

    def search(
        self,
        session: Session,
        term: str = "",
        familia: str = "",
        subfamilia: str = "",
        fabricante_id: str = "",
        active_filter: str = "all",
        distribuidor_id_filter: str = "",
    ) -> list[IngredienteIreks]:
        conditions = []
        if term.strip():
            like_term = f"%{term.strip()}%"
            conditions.append(
                or_(
                    col(self.model.articulo_id).like(like_term),
                    col(self.model.articulo_referencia).like(like_term),
                    col(self.model.articulo_referencia_corta).like(like_term),
                    col(self.model.articulo_descripcion).like(like_term),
                    col(self.model.almacen_id).like(like_term),
                    col(self.model.fabricante_id).like(like_term),
                    col(self.model.distribuidor_id).like(like_term),
                )
            )
        if familia.strip():
            conditions.append(col(self.model.articulo_familia_id) == familia.strip())
        if subfamilia.strip():
            conditions.append(col(self.model.articulo_subfamilia_id) == subfamilia.strip())
        if fabricante_id.strip():
            conditions.append(col(self.model.fabricante_id) == fabricante_id.strip())
        if active_filter == "active":
            conditions.append(col(self.model.articulo_status_activo).is_(True))
        elif active_filter == "inactive":
            conditions.append(col(self.model.articulo_status_activo).is_(False))

        stmt = select(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(col(self.model.articulo_descripcion))
        return list(session.exec(stmt))

    def list_all(self, session: Session) -> list[IngredienteIreks]:
        stmt = select(self.model).order_by(col(self.model.articulo_descripcion))
        return list(session.exec(stmt))


class IngredientWarehouseRepository(IngredientRepository[IngredienteIreks]):
    def __init__(self) -> None:
        super().__init__(IngredienteIreks)

    def search(
        self,
        session: Session,
        term: str = "",
        familia: str = "",
        subfamilia: str = "",
        fabricante_id: str = "",
        active_filter: str = "all",
        distribuidor_id_filter: str = "",
    ) -> list[IngredienteIreks]:
        conditions = []
        if term.strip():
            like_term = f"%{term.strip()}%"
            conditions.append(
                or_(
                    col(self.model.articulo_id).like(like_term),
                    col(self.model.articulo_referencia).like(like_term),
                    col(self.model.articulo_referencia_corta).like(like_term),
                    col(self.model.articulo_descripcion).like(like_term),
                    col(self.model.fabricante_id).like(like_term),
                    col(self.model.distribuidor_id).like(like_term),
                )
            )
        if familia.strip():
            conditions.append(col(self.model.articulo_familia_id) == familia.strip())
        if subfamilia.strip():
            conditions.append(col(self.model.articulo_subfamilia_id) == subfamilia.strip())
        if fabricante_id.strip():
            conditions.append(col(self.model.fabricante_id) == fabricante_id.strip())
        if active_filter == "active":
            conditions.append(col(self.model.articulo_status_activo).is_(True))
        elif active_filter == "inactive":
            conditions.append(col(self.model.articulo_status_activo).is_(False))

        stmt = select(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(col(self.model.articulo_descripcion))
        return list(session.exec(stmt))

    def list_all(self, session: Session) -> list[IngredienteIreks]:
        stmt = select(self.model).order_by(col(self.model.articulo_descripcion))
        return list(session.exec(stmt))


class IngredientStdRepository(IngredientRepository[IngredienteStd]):
    def __init__(self) -> None:
        super().__init__(IngredienteStd)

    def search(
        self,
        session: Session,
        term: str = "",
        familia: str = "",
        subfamilia: str = "",
        active_filter: str = "all",
    ) -> list[IngredienteStd]:
        conditions = []
        if term.strip():
            like_term = f"%{term.strip()}%"
            conditions.append(
                or_(
                    col(self.model.articulo_referencia_distribuidor).like(like_term),
                    col(self.model.articulo_descripcion).like(like_term),
                    col(self.model.proveedor_id).like(like_term),
                    col(self.model.articulo_grupo_id).like(like_term),
                    col(self.model.articulo_familia_id).like(like_term),
                    col(self.model.articulo_subfamilia_id).like(like_term),
                    col(self.model.categoria).like(like_term),
                    col(self.model.formato).like(like_term),
                    col(self.model.formato_unidad).like(like_term),
                )
            )
        if familia.strip():
            conditions.append(col(self.model.articulo_familia_id) == familia.strip())
        if subfamilia.strip():
            conditions.append(col(self.model.articulo_subfamilia_id) == subfamilia.strip())
        if active_filter == "active":
            conditions.append(col(self.model.activo).is_(True))
        elif active_filter == "inactive":
            conditions.append(col(self.model.activo).is_(False))

        stmt = select(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(col(self.model.articulo_descripcion))
        return list(session.exec(stmt))

    def list_all(self, session: Session) -> list[IngredienteStd]:
        stmt = select(self.model).order_by(col(self.model.articulo_descripcion))
        return list(session.exec(stmt))

    def distributor_name_map(self, session: Session) -> dict[str, str]:
        rows = list(session.exec(select(Proveedor)))
        mapping: dict[str, str] = {}
        for row in rows:
            name = (row.proveedor_nombre_comercial or "").strip() or (row.proveedor_razon_social or "").strip()
            mapping[row.proveedor_id] = name
        return mapping

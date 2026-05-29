from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import String, cast as sa_cast
from sqlmodel import Session, or_, select

from app.core.database import engine
from app.models import Cliente, Envase, Fabricante, Familia, Subfamilia
from app.services.import_service import ImportService


def _col(expr: object) -> Any:
    return cast(Any, expr)


class WarehouseCatalogService:
    def __init__(self) -> None:
        self.import_service = ImportService()

    def list_warehouse_clients(self) -> list[Cliente]:
        with Session(engine) as session:
            return list(session.exec(select(Cliente).order_by(Cliente.cliente_nombre_comercial)))

    def _next_fabricante_codigo(self, session: Session) -> int:
        rows = list(session.exec(select(Fabricante.fabricante_codigo)))
        max_code = max([int(x or 0) for x in rows], default=0)
        return max_code + 1

    def _next_envase_codigo(self, session: Session) -> int:
        rows = list(session.exec(select(Envase.envase_codigo)))
        max_code = max([int(x or 0) for x in rows], default=0)
        return max_code + 1

    def list_fabricantes(self, term: str) -> list[Fabricante]:
        with Session(engine) as session:
            stmt = select(Fabricante)
            if term.strip():
                like_term = f"%{term.strip()}%"
                stmt = stmt.where(
                    or_(
                        _col(Fabricante.fabricante_nombre).like(like_term),
                        _col(sa_cast(Fabricante.fabricante_codigo, String)).like(like_term),
                        _col(Fabricante.fabricante_id).like(like_term),
                    )
                )
            stmt = stmt.order_by(_col(Fabricante.fabricante_codigo), _col(Fabricante.fabricante_nombre))
            return list(session.exec(stmt))

    def create_fabricante(self, payload: dict) -> None:
        with Session(engine) as session:
            payload = dict(payload)
            payload["fabricante_id"] = str(payload.get("fabricante_id") or "").strip() or str(uuid4())
            raw = str(payload.get("fabricante_codigo") or "").strip()
            payload["fabricante_codigo"] = int(raw) if raw.isdigit() else self._next_fabricante_codigo(session)
            payload["fabricante_nombre"] = str(payload.get("fabricante_nombre") or "").strip()
            session.add(Fabricante(**payload))
            session.commit()

    def update_fabricante(self, fabricante_id: str, payload: dict) -> None:
        with Session(engine) as session:
            row = session.get(Fabricante, fabricante_id)
            if not row:
                raise ValueError("Fabricante no encontrado")
            for key, value in payload.items():
                setattr(row, key, value)
            row.fabricante_nombre = str(row.fabricante_nombre or "").strip()
            if not int(row.fabricante_codigo or 0):
                row.fabricante_codigo = self._next_fabricante_codigo(session)
            session.add(row)
            session.commit()

    def delete_fabricante(self, fabricante_id: str) -> bool:
        with Session(engine) as session:
            row = session.get(Fabricante, fabricante_id)
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    def import_fabricantes(self, file_path: str) -> tuple[int, list[str]]:
        schema = [
            {"name": "fabricante_id", "label": "Fabricante_ID"},
            {"name": "fabricante_codigo", "label": "Fabricante_Codigo"},
            {"name": "fabricante_nombre", "label": "Fabricante_Nombre"},
        ]
        aliases = {
            "fabricante_id": ["id"],
            "fabricante_codigo": ["codigo", "cod"],
            "fabricante_nombre": ["nombre"],
        }

        def create_row(payload: dict[str, Any]) -> None:
            payload = dict(payload)
            fabricante_id = str(payload.get("fabricante_id") or "").strip()
            if not fabricante_id:
                raise ValueError("Campo obligatorio vacio: fabricante_id")
            raw = str(payload.get("fabricante_codigo") or "").strip()
            nombre = str(payload.get("fabricante_nombre") or "").strip()
            if not nombre:
                raise ValueError("Campo obligatorio vacio: fabricante_nombre")
            with Session(engine) as session:
                row = session.get(Fabricante, fabricante_id)
                codigo = int(raw) if raw.isdigit() else 0
                if codigo <= 0:
                    codigo = self._next_fabricante_codigo(session)
                if row:
                    row.fabricante_codigo = codigo
                    row.fabricante_nombre = nombre
                    session.add(row)
                else:
                    session.add(Fabricante(fabricante_id=fabricante_id, fabricante_codigo=codigo, fabricante_nombre=nombre))
                session.commit()

        return self.import_service.import_with_schema(
            file_path=Path(file_path),
            schema=schema,
            create_fn=create_row,
            required_fields=["fabricante_id", "fabricante_nombre"],
            aliases=aliases,
        )

    def list_familias(self, term: str) -> list[Familia]:
        with Session(engine) as session:
            stmt = select(Familia)
            if term.strip():
                like_term = f"%{term.strip()}%"
                stmt = stmt.where(
                    or_(
                        _col(Familia.articulo_familia_codigo).like(like_term),
                        _col(Familia.articulo_familia_nombre).like(like_term),
                        _col(Familia.articulo_familia_id).like(like_term),
                        _col(Familia.fabricante_id).like(like_term),
                    )
                )
            stmt = stmt.order_by(_col(Familia.articulo_familia_codigo), _col(Familia.articulo_familia_nombre))
            return list(session.exec(stmt))

    def create_familia(self, payload: dict) -> None:
        with Session(engine) as session:
            payload = dict(payload)
            payload["fabricante_id"] = str(payload.get("fabricante_id") or "").strip()
            payload["articulo_familia_id"] = str(payload.get("articulo_familia_id") or "").strip()
            payload["articulo_familia_nombre"] = str(payload.get("articulo_familia_nombre") or "").strip()
            payload["articulo_familia_codigo"] = str(payload.get("articulo_familia_codigo") or "").strip()
            session.add(Familia(**payload))
            session.commit()

    def update_familia(self, familia_id: str, payload: dict) -> None:
        with Session(engine) as session:
            row = session.get(Familia, familia_id)
            if not row:
                raise ValueError("Familia no encontrada")
            for key, value in payload.items():
                setattr(row, key, value)
            session.add(row)
            session.commit()

    def delete_familia(self, familia_id: str) -> bool:
        with Session(engine) as session:
            row = session.get(Familia, familia_id)
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    def import_familias(self, file_path: str) -> tuple[int, list[str]]:
        schema = [
            {"name": "fabricante_id", "label": "Fabricante_ID"},
            {"name": "articulo_familia_id", "label": "Articulo_Familia_ID"},
            {"name": "articulo_familia_nombre", "label": "Articulo_Familia_Nombre"},
            {"name": "articulo_familia_codigo", "label": "Articulo_Familia_Codigo"},
        ]
        aliases = {
            "fabricante_id": ["fabricante", "fabricante_id"],
            "articulo_familia_id": ["familia_id"],
            "articulo_familia_nombre": ["nombre"],
            "articulo_familia_codigo": ["codigo", "cod"],
        }

        def create_row(payload: dict[str, Any]) -> None:
            familia_id = str(payload.get("articulo_familia_id") or "").strip()
            if not familia_id:
                raise ValueError("Campo obligatorio vacio: articulo_familia_id")
            clean = {
                "fabricante_id": str(payload.get("fabricante_id") or "").strip(),
                "articulo_familia_id": familia_id,
                "articulo_familia_nombre": str(payload.get("articulo_familia_nombre") or "").strip(),
                "articulo_familia_codigo": str(payload.get("articulo_familia_codigo") or "").strip(),
            }
            with Session(engine) as session:
                row = session.get(Familia, familia_id)
                if row:
                    for key, value in clean.items():
                        setattr(row, key, value)
                    session.add(row)
                else:
                    session.add(Familia(**clean))
                session.commit()

        return self.import_service.import_with_schema(
            file_path=Path(file_path),
            schema=schema,
            create_fn=create_row,
            required_fields=["fabricante_id", "articulo_familia_id", "articulo_familia_nombre", "articulo_familia_codigo"],
            aliases=aliases,
        )

    def list_subfamilias(self, term: str) -> list[Subfamilia]:
        with Session(engine) as session:
            stmt = select(Subfamilia)
            if term.strip():
                like_term = f"%{term.strip()}%"
                stmt = stmt.where(
                    or_(
                        _col(Subfamilia.articulo_subfamilia_codigo).like(like_term),
                        _col(Subfamilia.articulo_subfamilia_nombre).like(like_term),
                        _col(Subfamilia.articulo_subfamilia_id).like(like_term),
                        _col(Subfamilia.articulo_familia_id).like(like_term),
                    )
                )
            stmt = stmt.order_by(_col(Subfamilia.articulo_subfamilia_codigo), _col(Subfamilia.articulo_subfamilia_nombre))
            return list(session.exec(stmt))

    def create_subfamilia(self, payload: dict) -> None:
        with Session(engine) as session:
            payload = dict(payload)
            payload["articulo_familia_id"] = str(payload.get("articulo_familia_id") or "").strip()
            payload["articulo_subfamilia_id"] = str(payload.get("articulo_subfamilia_id") or "").strip()
            payload["articulo_subfamilia_nombre"] = str(payload.get("articulo_subfamilia_nombre") or "").strip()
            payload["articulo_subfamilia_codigo"] = str(payload.get("articulo_subfamilia_codigo") or "").strip()
            session.add(Subfamilia(**payload))
            session.commit()

    def update_subfamilia(self, subfamilia_id: str, payload: dict) -> None:
        with Session(engine) as session:
            row = session.exec(select(Subfamilia).where(Subfamilia.articulo_subfamilia_id == subfamilia_id)).first()
            if not row:
                raise ValueError("Subfamilia no encontrada")
            for key, value in payload.items():
                setattr(row, key, value)
            session.add(row)
            session.commit()

    def delete_subfamilia(self, subfamilia_id: str) -> bool:
        with Session(engine) as session:
            row = session.exec(select(Subfamilia).where(Subfamilia.articulo_subfamilia_id == subfamilia_id)).first()
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    def import_subfamilias(self, file_path: str) -> tuple[int, list[str]]:
        schema = [
            {"name": "articulo_familia_id", "label": "Articulo_Familia_ID"},
            {"name": "articulo_subfamilia_id", "label": "Articulo_SubFamilia_ID"},
            {"name": "articulo_subfamilia_nombre", "label": "Articulo_SubFamilia_Nombre"},
            {"name": "articulo_subfamilia_codigo", "label": "Articulo_SubFamilia_Codigo"},
        ]
        aliases = {
            "articulo_familia_id": ["familia_id"],
            "articulo_subfamilia_id": ["subfamilia_id"],
            "articulo_subfamilia_nombre": ["nombre"],
            "articulo_subfamilia_codigo": ["codigo", "cod"],
        }

        def create_row(payload: dict[str, Any]) -> None:
            sub_id = str(payload.get("articulo_subfamilia_id") or "").strip()
            if not sub_id:
                raise ValueError("Campo obligatorio vacio: articulo_subfamilia_id")
            clean = {
                "articulo_familia_id": str(payload.get("articulo_familia_id") or "").strip(),
                "articulo_subfamilia_id": sub_id,
                "articulo_subfamilia_nombre": str(payload.get("articulo_subfamilia_nombre") or "").strip(),
                "articulo_subfamilia_codigo": str(payload.get("articulo_subfamilia_codigo") or "").strip(),
            }
            with Session(engine) as session:
                row = session.exec(select(Subfamilia).where(Subfamilia.articulo_subfamilia_id == sub_id)).first()
                if row:
                    for key, value in clean.items():
                        setattr(row, key, value)
                    session.add(row)
                else:
                    session.add(Subfamilia(**clean))
                session.commit()

        return self.import_service.import_with_schema(
            file_path=Path(file_path),
            schema=schema,
            create_fn=create_row,
            required_fields=[
                "articulo_familia_id",
                "articulo_subfamilia_id",
                "articulo_subfamilia_nombre",
                "articulo_subfamilia_codigo",
            ],
            aliases=aliases,
        )

    def list_envases(self, term: str) -> list[Envase]:
        with Session(engine) as session:
            stmt = select(Envase)
            if term.strip():
                like_term = f"%{term.strip()}%"
                stmt = stmt.where(
                    or_(
                        _col(sa_cast(Envase.envase_codigo, String)).like(like_term),
                        _col(Envase.envase_nombre).like(like_term),
                        _col(Envase.envase_id).like(like_term),
                    )
                )
            stmt = stmt.order_by(_col(Envase.envase_codigo), _col(Envase.envase_nombre))
            return list(session.exec(stmt))

    def create_envase(self, payload: dict) -> None:
        with Session(engine) as session:
            payload = dict(payload)
            payload["envase_id"] = str(payload.get("envase_id") or "").strip() or str(uuid4())
            payload["envase_nombre"] = str(payload.get("envase_nombre") or "").strip()
            raw = str(payload.get("envase_codigo") or "").strip()
            payload["envase_codigo"] = int(raw) if raw.isdigit() else self._next_envase_codigo(session)
            if not payload["envase_nombre"]:
                raise ValueError("Envase nombre obligatorio")
            session.add(Envase(**payload))
            session.commit()

    def update_envase(self, envase_id: str, payload: dict) -> None:
        with Session(engine) as session:
            row = session.get(Envase, envase_id)
            if not row:
                raise ValueError("Envase no encontrado")
            for key, value in payload.items():
                setattr(row, key, value)
            row.envase_nombre = str(row.envase_nombre or "").strip()
            if not row.envase_nombre:
                raise ValueError("Envase nombre obligatorio")
            if int(row.envase_codigo or 0) <= 0:
                row.envase_codigo = self._next_envase_codigo(session)
            session.add(row)
            session.commit()

    def delete_envase(self, envase_id: str) -> bool:
        with Session(engine) as session:
            row = session.get(Envase, envase_id)
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    def import_envases(self, file_path: str) -> tuple[int, list[str]]:
        schema = [
            {"name": "envase_id", "label": "Envase_ID"},
            {"name": "envase_codigo", "label": "Envase_Codigo"},
            {"name": "envase_nombre", "label": "Envase_Nombre"},
        ]
        aliases = {
            "envase_id": ["id"],
            "envase_codigo": ["codigo", "cod"],
            "envase_nombre": ["nombre", "descripcion"],
        }

        def create_row(payload: dict[str, Any]) -> None:
            envase_id = str(payload.get("envase_id") or "").strip()
            if not envase_id:
                raise ValueError("Campo obligatorio vacio: envase_id")
            envase_nombre = str(payload.get("envase_nombre") or "").strip()
            if not envase_nombre:
                raise ValueError("Campo obligatorio vacio: envase_nombre")
            raw = str(payload.get("envase_codigo") or "").strip()
            with Session(engine) as session:
                row = session.get(Envase, envase_id)
                envase_codigo = int(raw) if raw.isdigit() else 0
                if envase_codigo <= 0:
                    envase_codigo = self._next_envase_codigo(session)
                if row:
                    row.envase_codigo = envase_codigo
                    row.envase_nombre = envase_nombre
                    session.add(row)
                else:
                    session.add(
                        Envase(
                            envase_id=envase_id,
                            envase_codigo=envase_codigo,
                            envase_nombre=envase_nombre,
                        )
                    )
                session.commit()

        return self.import_service.import_with_schema(
            file_path=Path(file_path),
            schema=schema,
            create_fn=create_row,
            required_fields=["envase_id", "envase_nombre"],
            aliases=aliases,
        )

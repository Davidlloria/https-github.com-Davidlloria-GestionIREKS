from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from sqlmodel import Session, or_, select

from app.core.database import engine
from app.models import CodigoPostal, Isla, Localidad, Municipio, Provincia
from app.services.import_service import ImportService


def _col(expr: object) -> Any:
    return cast(Any, expr)


class AddressCatalogService:
    def __init__(self) -> None:
        self.import_service = ImportService()

    def list_provincias(self, term: str = "") -> list[Provincia]:
        with Session(engine) as session:
            stmt = select(Provincia)
            if term:
                like_term = f"%{term}%"
                stmt = stmt.where(
                    or_(
                        _col(Provincia.provincia_codigo).like(like_term),
                        _col(Provincia.provincia_nombre).like(like_term),
                        _col(Provincia.provincia_id).like(like_term),
                    )
                )
            stmt = stmt.order_by(_col(Provincia.provincia_codigo), _col(Provincia.provincia_nombre))
            return list(session.exec(stmt))

    def create_provincia(self, payload: dict) -> None:
        self.validate_provincia(payload)
        with Session(engine) as session:
            session.add(Provincia(**payload))
            session.commit()

    def update_provincia_cells(self, provincia_id: str, codigo: str, nombre: str) -> bool:
        if not provincia_id or not codigo or not nombre:
            return False
        with Session(engine) as session:
            entity = session.get(Provincia, provincia_id)
            if not entity:
                return False
            entity.provincia_codigo = codigo
            entity.provincia_nombre = nombre
            session.add(entity)
            session.commit()
        return True

    def replace_provincia(self, original_id: str, payload: dict) -> bool:
        self.validate_provincia(payload)
        with Session(engine) as session:
            entity = session.get(Provincia, original_id)
            if not entity:
                return False
            new_id = str(payload["provincia_id"]).strip()
            nombre = str(payload["provincia_nombre"]).strip()
            codigo = str(payload["provincia_codigo"]).strip()
            if new_id != entity.provincia_id:
                session.delete(entity)
                session.flush()
                session.add(Provincia(provincia_id=new_id, provincia_nombre=nombre, provincia_codigo=codigo))
            else:
                entity.provincia_nombre = nombre
                entity.provincia_codigo = codigo
                session.add(entity)
            session.commit()
        return True

    def delete_provincia(self, provincia_id: str) -> None:
        with Session(engine) as session:
            entity = session.get(Provincia, provincia_id)
            if entity:
                session.delete(entity)
                session.commit()

    def import_provincias(self, file_path: Path, schema: list[dict], aliases: dict[str, list[str]]) -> tuple[int, list[str]]:
        def _create(payload: dict) -> None:
            self.validate_provincia(payload)
            with Session(engine) as session:
                session.add(Provincia(**payload))
                session.commit()

        return self.import_service.import_with_schema(
            file_path=file_path,
            schema=schema,
            create_fn=_create,
            required_fields=["provincia_id", "provincia_nombre", "provincia_codigo"],
            aliases=aliases,
        )

    def validate_provincia(self, payload: dict) -> None:
        for field in ("provincia_id", "provincia_nombre", "provincia_codigo"):
            if not str(payload.get(field, "") or "").strip():
                raise ValueError(f"Campo obligatorio vacio: {field}")
        payload["provincia_id"] = str(payload["provincia_id"]).strip()
        payload["provincia_nombre"] = str(payload["provincia_nombre"]).strip()
        payload["provincia_codigo"] = str(payload["provincia_codigo"]).strip()

    def list_islas(self, term: str = "") -> tuple[list[Isla], list[Provincia]]:
        with Session(engine) as session:
            stmt = select(Isla)
            if term:
                like_term = f"%{term}%"
                stmt = stmt.where(
                    or_(
                        _col(Isla.isla_codigo).like(like_term),
                        _col(Isla.isla_nombre).like(like_term),
                        _col(Isla.isla_iniciales).like(like_term),
                        _col(Isla.provincia_id).like(like_term),
                        _col(Isla.isla_id).like(like_term),
                    )
                )
            stmt = stmt.order_by(_col(Isla.isla_codigo), _col(Isla.isla_nombre))
            return list(session.exec(stmt)), list(session.exec(select(Provincia)))

    def create_isla(self, payload: dict) -> None:
        self.validate_isla(payload)
        with Session(engine) as session:
            session.add(Isla(**payload))
            session.commit()

    def update_isla_cells(
        self,
        isla_id: str,
        *,
        codigo: str,
        nombre: str,
        iniciales: str,
        provincia_id: str,
    ) -> bool:
        if not isla_id or not codigo or not nombre or not iniciales or not provincia_id:
            return False
        with Session(engine) as session:
            entity = session.get(Isla, isla_id)
            if not entity:
                return False
            entity.isla_codigo = codigo
            entity.isla_nombre = nombre
            entity.isla_iniciales = iniciales
            entity.provincia_id = provincia_id
            session.add(entity)
            session.commit()
        return True

    def replace_isla(self, original_id: str, payload: dict) -> bool:
        self.validate_isla(payload)
        with Session(engine) as session:
            entity = session.get(Isla, original_id)
            if not entity:
                return False
            new_id = str(payload["isla_id"]).strip()
            data = {
                "provincia_id": str(payload["provincia_id"]).strip(),
                "isla_nombre": str(payload["isla_nombre"]).strip(),
                "isla_codigo": str(payload["isla_codigo"]).strip(),
                "isla_iniciales": str(payload["isla_iniciales"]).strip(),
            }
            if new_id != entity.isla_id:
                session.delete(entity)
                session.flush()
                session.add(Isla(isla_id=new_id, **data))
            else:
                entity.provincia_id = data["provincia_id"]
                entity.isla_nombre = data["isla_nombre"]
                entity.isla_codigo = data["isla_codigo"]
                entity.isla_iniciales = data["isla_iniciales"]
                session.add(entity)
            session.commit()
        return True

    def delete_isla(self, isla_id: str) -> None:
        with Session(engine) as session:
            entity = session.get(Isla, isla_id)
            if entity:
                session.delete(entity)
                session.commit()

    def import_islas(self, file_path: Path, schema: list[dict], aliases: dict[str, list[str]]) -> tuple[int, list[str]]:
        def _create(payload: dict) -> None:
            self.validate_isla(payload)
            with Session(engine) as session:
                session.add(Isla(**payload))
                session.commit()

        return self.import_service.import_with_schema(
            file_path=file_path,
            schema=schema,
            create_fn=_create,
            required_fields=["isla_id", "provincia_id", "isla_nombre", "isla_codigo", "isla_iniciales"],
            aliases=aliases,
        )

    def validate_isla(self, payload: dict) -> None:
        for field in ("isla_id", "provincia_id", "isla_nombre", "isla_codigo", "isla_iniciales"):
            if not str(payload.get(field, "") or "").strip():
                raise ValueError(f"Campo obligatorio vacio: {field}")
        payload["isla_id"] = str(payload["isla_id"]).strip()
        payload["provincia_id"] = str(payload["provincia_id"]).strip()
        payload["isla_nombre"] = str(payload["isla_nombre"]).strip()
        payload["isla_codigo"] = str(payload["isla_codigo"]).strip()
        payload["isla_iniciales"] = str(payload["isla_iniciales"]).strip()

    def list_municipios(self, term: str = "") -> tuple[list[Municipio], list[Isla], list[Provincia]]:
        with Session(engine) as session:
            stmt = select(Municipio)
            if term:
                like_term = f"%{term}%"
                stmt = stmt.where(
                    or_(
                        _col(Municipio.municipio_codigo).like(like_term),
                        _col(Municipio.municipio_nombre).like(like_term),
                        _col(Municipio.isla_id).like(like_term),
                        _col(Municipio.provincia_id).like(like_term),
                        _col(Municipio.municipio_id).like(like_term),
                    )
                )
            stmt = stmt.order_by(_col(Municipio.municipio_codigo), _col(Municipio.municipio_nombre))
            return list(session.exec(stmt)), list(session.exec(select(Isla))), list(session.exec(select(Provincia)))

    def create_municipio(self, payload: dict) -> None:
        self.validate_municipio(payload)
        with Session(engine) as session:
            session.add(Municipio(**payload))
            session.commit()

    def update_municipio_cells(
        self,
        municipio_id: str,
        *,
        codigo: str,
        nombre: str,
        isla_id: str,
        provincia_id: str,
    ) -> bool:
        if not municipio_id or not codigo or not nombre or not isla_id or not provincia_id:
            return False
        with Session(engine) as session:
            entity = session.get(Municipio, municipio_id)
            if not entity:
                return False
            entity.municipio_codigo = codigo
            entity.municipio_nombre = nombre
            entity.isla_id = isla_id
            entity.provincia_id = provincia_id
            session.add(entity)
            session.commit()
        return True

    def replace_municipio(self, original_id: str, payload: dict) -> bool:
        self.validate_municipio(payload)
        with Session(engine) as session:
            entity = session.get(Municipio, original_id)
            if not entity:
                return False
            new_id = str(payload["municipio_id"]).strip()
            data = {
                "isla_id": str(payload["isla_id"]).strip(),
                "provincia_id": str(payload["provincia_id"]).strip(),
                "municipio_nombre": str(payload["municipio_nombre"]).strip(),
                "municipio_codigo": str(payload["municipio_codigo"]).strip(),
            }
            if new_id != entity.municipio_id:
                session.delete(entity)
                session.flush()
                session.add(Municipio(municipio_id=new_id, **data))
            else:
                entity.isla_id = data["isla_id"]
                entity.provincia_id = data["provincia_id"]
                entity.municipio_nombre = data["municipio_nombre"]
                entity.municipio_codigo = data["municipio_codigo"]
                session.add(entity)
            session.commit()
        return True

    def delete_municipio(self, municipio_id: str) -> None:
        with Session(engine) as session:
            entity = session.get(Municipio, municipio_id)
            if entity:
                session.delete(entity)
                session.commit()

    def import_municipios(self, file_path: Path, schema: list[dict], aliases: dict[str, list[str]]) -> tuple[int, list[str]]:
        def _create(payload: dict) -> None:
            self.validate_municipio(payload)
            with Session(engine) as session:
                session.add(Municipio(**payload))
                session.commit()

        return self.import_service.import_with_schema(
            file_path=file_path,
            schema=schema,
            create_fn=_create,
            required_fields=["municipio_id", "isla_id", "provincia_id", "municipio_nombre", "municipio_codigo"],
            aliases=aliases,
        )

    def validate_municipio(self, payload: dict) -> None:
        for field in ("municipio_id", "isla_id", "provincia_id", "municipio_nombre", "municipio_codigo"):
            if not str(payload.get(field, "") or "").strip():
                raise ValueError(f"Campo obligatorio vacio: {field}")
        payload["municipio_id"] = str(payload["municipio_id"]).strip()
        payload["isla_id"] = str(payload["isla_id"]).strip()
        payload["provincia_id"] = str(payload["provincia_id"]).strip()
        payload["municipio_nombre"] = str(payload["municipio_nombre"]).strip()
        payload["municipio_codigo"] = str(payload["municipio_codigo"]).strip()

    def list_codigos_postales(
        self, term: str = ""
    ) -> tuple[list[CodigoPostal], list[Municipio], list[Isla], list[Provincia]]:
        with Session(engine) as session:
            stmt = select(CodigoPostal)
            if term:
                like_term = f"%{term}%"
                stmt = stmt.where(
                    or_(
                        _col(CodigoPostal.codigo_postal).like(like_term),
                        _col(CodigoPostal.municipio_id).like(like_term),
                    )
                )
            stmt = stmt.order_by(_col(CodigoPostal.codigo_postal), _col(CodigoPostal.municipio_id))
            return (
                list(session.exec(stmt)),
                list(session.exec(select(Municipio))),
                list(session.exec(select(Isla))),
                list(session.exec(select(Provincia))),
            )

    def create_codigo_postal(self, payload: dict) -> None:
        self.validate_codigo_postal(payload)
        with Session(engine) as session:
            session.add(CodigoPostal(**payload))
            session.commit()

    def replace_codigo_postal(
        self,
        *,
        old_municipio_id: str,
        old_codigo_postal: str,
        new_municipio_id: str,
        new_codigo_postal: str,
    ) -> str:
        old_municipio_id = str(old_municipio_id or "").strip()
        old_codigo_postal = str(old_codigo_postal or "").strip()
        new_municipio_id = str(new_municipio_id or "").strip()
        new_codigo_postal = str(new_codigo_postal or "").strip()
        if not old_municipio_id or not old_codigo_postal or not new_municipio_id or not new_codigo_postal:
            return "invalid"
        if old_municipio_id == new_municipio_id and old_codigo_postal == new_codigo_postal:
            return "unchanged"
        with Session(engine) as session:
            current = session.exec(
                select(CodigoPostal).where(
                    CodigoPostal.municipio_id == old_municipio_id,
                    CodigoPostal.codigo_postal == old_codigo_postal,
                )
            ).first()
            if not current:
                return "missing"
            exists = session.exec(
                select(CodigoPostal).where(
                    CodigoPostal.municipio_id == new_municipio_id,
                    CodigoPostal.codigo_postal == new_codigo_postal,
                )
            ).first()
            if exists:
                return "exists"
            session.delete(current)
            session.flush()
            session.add(CodigoPostal(municipio_id=new_municipio_id, codigo_postal=new_codigo_postal))
            session.commit()
        return "updated"

    def delete_codigo_postal(self, municipio_id: str, codigo_postal: str) -> None:
        with Session(engine) as session:
            entity = session.exec(
                select(CodigoPostal).where(
                    CodigoPostal.municipio_id == municipio_id,
                    CodigoPostal.codigo_postal == codigo_postal,
                )
            ).first()
            if entity:
                session.delete(entity)
                session.commit()

    def import_codigos_postales(
        self, file_path: Path, schema: list[dict], aliases: dict[str, list[str]]
    ) -> tuple[int, list[str]]:
        def _create(payload: dict) -> None:
            self.validate_codigo_postal(payload)
            municipio_id = str(payload["municipio_id"]).strip()
            codigo_postal = str(payload["codigo_postal"]).strip()
            with Session(engine) as session:
                existing = session.exec(
                    select(CodigoPostal).where(
                        CodigoPostal.municipio_id == municipio_id,
                        CodigoPostal.codigo_postal == codigo_postal,
                    )
                ).first()
                if not existing:
                    session.add(CodigoPostal(municipio_id=municipio_id, codigo_postal=codigo_postal))
                session.commit()

        return self.import_service.import_with_schema(
            file_path=file_path,
            schema=schema,
            create_fn=_create,
            required_fields=["municipio_id", "codigo_postal"],
            aliases=aliases,
        )

    def validate_codigo_postal(self, payload: dict) -> None:
        for field in ("municipio_id", "codigo_postal"):
            if not str(payload.get(field, "") or "").strip():
                raise ValueError(f"Campo obligatorio vacio: {field}")
        payload["municipio_id"] = str(payload["municipio_id"]).strip()
        payload["codigo_postal"] = str(payload["codigo_postal"]).strip()

    def list_localidades(self, term: str = "") -> tuple[list[Localidad], int, list[Municipio]]:
        with Session(engine) as session:
            total = len(list(session.exec(select(Localidad))))
            stmt = select(Localidad)
            if term:
                like_term = f"%{term}%"
                stmt = stmt.where(
                    or_(
                        _col(Localidad.localidad_nombre).like(like_term),
                        _col(Localidad.codigo_postal).like(like_term),
                        _col(Localidad.municipio_id).like(like_term),
                        _col(Localidad.localidad_id).like(like_term),
                    )
                )
            stmt = stmt.order_by(_col(Localidad.localidad_nombre), _col(Localidad.codigo_postal))
            return list(session.exec(stmt)), total, list(session.exec(select(Municipio)))

    def create_localidad(self, payload: dict) -> None:
        payload.setdefault("localidad_id", str(uuid4()))
        self.validate_localidad(payload)
        with Session(engine) as session:
            self.ensure_codigo_postal_link(
                session,
                str(payload.get("municipio_id") or "").strip(),
                payload.get("codigo_postal"),
            )
            session.add(
                Localidad(
                    localidad_id=str(payload.get("localidad_id") or "").strip(),
                    municipio_id=str(payload.get("municipio_id") or "").strip(),
                    localidad_nombre=str(payload.get("localidad_nombre") or "").strip(),
                    codigo_postal=(str(payload.get("codigo_postal") or "").strip() or None),
                )
            )
            session.commit()

    def update_localidad_cells(
        self,
        localidad_id: str,
        *,
        localidad_nombre: str,
        municipio_id: str,
        codigo_postal: str | None,
    ) -> bool:
        if not localidad_id or not localidad_nombre or not municipio_id:
            return False
        with Session(engine) as session:
            entity = session.get(Localidad, localidad_id)
            if not entity:
                return False
            self.ensure_codigo_postal_link(session, municipio_id, codigo_postal)
            entity.localidad_nombre = localidad_nombre
            entity.municipio_id = municipio_id
            entity.codigo_postal = (str(codigo_postal or "").strip() or None)
            session.add(entity)
            session.commit()
        return True

    def replace_localidad(self, original_id: str, payload: dict) -> bool:
        self.validate_localidad(payload)
        with Session(engine) as session:
            entity = session.get(Localidad, original_id)
            if not entity:
                return False
            new_id = str(payload["localidad_id"]).strip()
            new_municipio_id = str(payload["municipio_id"]).strip()
            new_codigo_postal = payload.get("codigo_postal")
            self.ensure_codigo_postal_link(session, new_municipio_id, new_codigo_postal)
            data = {
                "municipio_id": new_municipio_id,
                "localidad_nombre": str(payload["localidad_nombre"]).strip(),
                "codigo_postal": (str(new_codigo_postal or "").strip() or None),
            }
            if new_id != entity.localidad_id:
                session.delete(entity)
                session.flush()
                session.add(Localidad(localidad_id=new_id, **data))
            else:
                entity.municipio_id = data["municipio_id"]
                entity.localidad_nombre = data["localidad_nombre"]
                entity.codigo_postal = data["codigo_postal"]
                session.add(entity)
            session.commit()
        return True

    def delete_localidad(self, localidad_id: str) -> None:
        with Session(engine) as session:
            entity = session.get(Localidad, localidad_id)
            if entity:
                session.delete(entity)
                session.commit()

    def import_localidades(self, file_path: Path, schema: list[dict], aliases: dict[str, list[str]]) -> tuple[int, list[str]]:
        def _create(payload: dict) -> None:
            self.validate_localidad(payload)
            localidad_id = str(payload["localidad_id"]).strip()
            municipio_id = str(payload.get("municipio_id") or "").strip()
            codigo_postal = payload.get("codigo_postal")
            with Session(engine) as session:
                self.ensure_codigo_postal_link(session, municipio_id, codigo_postal)
                existing = session.get(Localidad, localidad_id)
                if existing:
                    existing.municipio_id = municipio_id
                    existing.localidad_nombre = str(payload.get("localidad_nombre") or "").strip()
                    existing.codigo_postal = (str(codigo_postal or "").strip() or None)
                    session.add(existing)
                else:
                    session.add(
                        Localidad(
                            localidad_id=localidad_id,
                            municipio_id=municipio_id,
                            localidad_nombre=str(payload.get("localidad_nombre") or "").strip(),
                            codigo_postal=(str(codigo_postal or "").strip() or None),
                        )
                    )
                session.commit()

        return self.import_service.import_with_schema(
            file_path=file_path,
            schema=schema,
            create_fn=_create,
            required_fields=["localidad_id", "municipio_id", "localidad_nombre"],
            aliases=aliases,
        )

    def validate_localidad(self, payload: dict) -> None:
        for field in ("localidad_id", "municipio_id", "localidad_nombre"):
            if not str(payload.get(field, "") or "").strip():
                raise ValueError(f"Campo obligatorio vacio: {field}")
        payload["localidad_id"] = str(payload["localidad_id"]).strip()
        payload["municipio_id"] = str(payload["municipio_id"]).strip()
        payload["localidad_nombre"] = str(payload["localidad_nombre"]).strip()
        codigo_postal = str(payload.get("codigo_postal", "") or "").strip()
        payload["codigo_postal"] = codigo_postal or None

    def ensure_codigo_postal_link(self, session: Session, municipio_id: str, codigo_postal: str | None) -> None:
        cp = (codigo_postal or "").strip()
        if not cp:
            return
        existing = session.exec(
            select(CodigoPostal).where(
                CodigoPostal.municipio_id == municipio_id,
                CodigoPostal.codigo_postal == cp,
            )
        ).first()
        if existing:
            return
        session.add(CodigoPostal(municipio_id=municipio_id, codigo_postal=cp))
        session.flush()

    def list_related_provincias(self) -> list[Provincia]:
        with Session(engine) as session:
            return list(session.exec(select(Provincia)))

    def list_related_islas(self) -> list[Isla]:
        with Session(engine) as session:
            return list(session.exec(select(Isla)))

    def list_related_municipios(self) -> list[Municipio]:
        with Session(engine) as session:
            return list(session.exec(select(Municipio)))

    def list_related_codigos_postales(self) -> list[CodigoPostal]:
        with Session(engine) as session:
            return list(session.exec(select(CodigoPostal)))

    def list_related_localidades(self) -> list[Localidad]:
        with Session(engine) as session:
            return list(session.exec(select(Localidad)))

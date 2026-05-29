from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc
from sqlmodel import Session, col, delete, or_, select

from app.models import Receta, RecetaLinea, RecetaVersion


@dataclass
class RecipeAggregate:
    receta: Receta
    lineas: list[RecetaLinea]


class RecipeRepository:
    def list(
        self,
        session: Session,
        term: str = "",
        cliente_id: str | None = None,
        es_base: bool | None = None,
    ) -> list[Receta]:
        stmt = select(Receta).distinct()
        if term.strip():
            like_term = f"%{term.strip()}%"
            stmt = stmt.outerjoin(RecetaLinea, col(RecetaLinea.receta_id) == col(Receta.id)).where(
                or_(
                    col(Receta.nombre).like(like_term),
                    col(Receta.codigo_receta).like(like_term),
                    col(RecetaLinea.codigo_ingrediente).like(like_term),
                    col(RecetaLinea.nombre_mostrado).like(like_term),
                    col(RecetaLinea.familia).like(like_term),
                    col(RecetaLinea.subfamilia).like(like_term),
                )
            )
        if cliente_id:
            stmt = stmt.where(col(Receta.cliente_id) == cliente_id)
        if es_base is not None:
            stmt = stmt.where(col(Receta.es_base) == es_base)
        stmt = stmt.order_by(desc(col(Receta.updated_at)))
        return list(session.exec(stmt))

    def get(self, session: Session, receta_id: int) -> RecipeAggregate | None:
        receta = session.get(Receta, receta_id)
        if not receta:
            return None
        lineas = list(
            session.exec(
                select(RecetaLinea).where(col(RecetaLinea.receta_id) == receta_id).order_by(col(RecetaLinea.orden))
            )
        )
        return RecipeAggregate(receta=receta, lineas=lineas)

    def save(self, session: Session, receta: Receta, lineas: list[RecetaLinea]) -> RecipeAggregate:
        now = datetime.utcnow()
        payload = receta.model_dump(exclude={"id", "created_at", "updated_at"})

        target: Receta
        if receta.id is not None:
            existing = session.get(Receta, receta.id)
            if existing is not None:
                for key, value in payload.items():
                    setattr(existing, key, value)
                existing.updated_at = now
                target = existing
            else:
                # Si llega un id no existente, crear nueva receta sin forzar PK.
                target = Receta(**payload)
                target.created_at = now
                target.updated_at = now
                session.add(target)
        else:
            target = Receta(**payload)
            target.created_at = now
            target.updated_at = now
            session.add(target)

        session.commit()
        session.refresh(target)

        session.execute(delete(RecetaLinea).where(col(RecetaLinea.receta_id) == (target.id or 0)))
        session.flush()
        for idx, linea in enumerate(lineas, start=1):
            line_payload = linea.model_dump(exclude={"id", "receta_id", "orden"})
            new_line = RecetaLinea(
                receta_id=target.id or 0,
                orden=idx,
                **line_payload,
            )
            session.add(new_line)
        session.commit()
        return self.get(session, target.id)  # type: ignore[arg-type]

    def delete(self, session: Session, receta_id: int) -> bool:
        receta = session.get(Receta, receta_id)
        if not receta:
            return False
        session.execute(delete(RecetaLinea).where(col(RecetaLinea.receta_id) == receta_id))
        session.delete(receta)
        session.commit()
        return True

    def save_version(
        self,
        session: Session,
        receta: Receta,
        lineas: list[RecetaLinea],
        comentario: str = "",
    ) -> RecetaVersion:
        payload = {
            "receta": {k: v for k, v in receta.model_dump().items() if k not in {"id", "created_at", "updated_at"}},
            "lineas": [linea.model_dump() for linea in lineas],
        }
        version = RecetaVersion(
            receta_id=receta.id or 0,
            version=receta.version,
            snapshot_json=json.dumps(payload, ensure_ascii=False),
            comentario=comentario,
        )
        session.add(version)
        session.commit()
        session.refresh(version)
        return version

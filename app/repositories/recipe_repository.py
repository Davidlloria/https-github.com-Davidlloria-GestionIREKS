from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, delete, or_, select

from app.models import Receta, RecetaLinea, RecetaVersion


@dataclass
class RecipeAggregate:
    receta: Receta
    lineas: list[RecetaLinea]


class RecipeRepository:
    def list(self, session: Session, term: str = "", cliente_id: int | None = None) -> list[Receta]:
        stmt = select(Receta)
        if term.strip():
            like_term = f"%{term.strip()}%"
            stmt = stmt.where(or_(Receta.nombre.like(like_term), Receta.codigo_receta.like(like_term)))
        if cliente_id:
            stmt = stmt.where(Receta.cliente_id == cliente_id)
        stmt = stmt.order_by(Receta.updated_at.desc())
        return list(session.exec(stmt))

    def get(self, session: Session, receta_id: int) -> RecipeAggregate | None:
        receta = session.get(Receta, receta_id)
        if not receta:
            return None
        lineas = list(session.exec(select(RecetaLinea).where(RecetaLinea.receta_id == receta_id).order_by(RecetaLinea.orden)))
        return RecipeAggregate(receta=receta, lineas=lineas)

    def save(self, session: Session, receta: Receta, lineas: list[RecetaLinea]) -> RecipeAggregate:
        receta.updated_at = datetime.utcnow()
        if receta.id is None:
            receta.created_at = datetime.utcnow()
        session.add(receta)
        session.commit()
        session.refresh(receta)

        session.exec(delete(RecetaLinea).where(RecetaLinea.receta_id == receta.id))
        for idx, linea in enumerate(lineas, start=1):
            linea.id = None
            linea.receta_id = receta.id
            linea.orden = idx
            session.add(linea)
        session.commit()
        return self.get(session, receta.id)  # type: ignore[arg-type]

    def delete(self, session: Session, receta_id: int) -> bool:
        receta = session.get(Receta, receta_id)
        if not receta:
            return False
        session.exec(delete(RecetaLinea).where(RecetaLinea.receta_id == receta_id))
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

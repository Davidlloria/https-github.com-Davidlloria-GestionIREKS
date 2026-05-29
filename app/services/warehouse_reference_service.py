from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.database import engine
from app.models import Distribuidor, IngredienteIreks, ReferenciaDistribuidor
from app.services.import_service import ImportService


@dataclass
class OtrasRefRow:
    articulo_id: str
    distribuidor_id: str
    articulo_referencia_fabricante: str
    articulo_descripcion_fabricante: str
    articulo_referencia_distribuidor: str
    articulo_descripcion_distribuidor: str


class WarehouseReferenceService:
    def __init__(self) -> None:
        self.import_service = ImportService()

    def list_distributors(self) -> list[Distribuidor]:
        with Session(engine) as session:
            return list(session.exec(select(Distribuidor).order_by(Distribuidor.distribuidor_nombre_comercial)))

    def list_references(self, *, term: str = "", distributor_id: str = "") -> list[OtrasRefRow]:
        clean_term = term.strip().lower()
        clean_distributor = distributor_id.strip()
        with Session(engine) as session:
            ref_rows = list(session.exec(select(ReferenciaDistribuidor)))
            product_rows = list(
                session.exec(
                    select(
                        IngredienteIreks.articulo_id,
                        IngredienteIreks.articulo_referencia,
                        IngredienteIreks.articulo_descripcion,
                    )
                )
            )
        product_map = {
            str(articulo_id or ""): (str(ref or ""), str(desc or ""))
            for articulo_id, ref, desc in product_rows
        }
        result: list[OtrasRefRow] = []
        for row in ref_rows:
            articulo_id = str(row.articulo_id or "").strip()
            row_distributor_id = str(row.distribuidor_id or "").strip()
            if clean_distributor and row_distributor_id != clean_distributor:
                continue
            ref_fab, desc_fab = product_map.get(articulo_id, ("", ""))
            ref_dist = str(row.articulo_referencia_distribuidor or "")
            desc_dist = str(row.articulo_descripcion_distribuidor or "")
            if clean_term:
                blob = " ".join([articulo_id, row_distributor_id, ref_fab, desc_fab, ref_dist, desc_dist]).lower()
                if clean_term not in blob:
                    continue
            result.append(
                OtrasRefRow(
                    articulo_id=articulo_id,
                    distribuidor_id=row_distributor_id,
                    articulo_referencia_fabricante=ref_fab,
                    articulo_descripcion_fabricante=desc_fab,
                    articulo_referencia_distribuidor=ref_dist,
                    articulo_descripcion_distribuidor=desc_dist,
                )
            )
        return result

    def upsert_reference(self, payload: dict[str, Any], old_key: tuple[str, str] | None = None) -> None:
        articulo_id = str(payload.get("articulo_id") or "").strip()
        distribuidor_id = str(payload.get("distribuidor_id") or "").strip()
        if not articulo_id:
            raise ValueError("Campo obligatorio vacio: articulo_id")
        if not distribuidor_id:
            raise ValueError("Campo obligatorio vacio: distribuidor_id")
        clean = {
            "articulo_id": articulo_id,
            "distribuidor_id": distribuidor_id,
            "articulo_referencia_distribuidor": str(payload.get("articulo_referencia_distribuidor") or "").strip(),
            "articulo_descripcion_distribuidor": str(payload.get("articulo_descripcion_distribuidor") or "").strip(),
        }
        with Session(engine) as session:
            if old_key and old_key != (articulo_id, distribuidor_id):
                old = session.get(ReferenciaDistribuidor, old_key)
                if old:
                    session.delete(old)
                    session.commit()
            existing = session.get(ReferenciaDistribuidor, (articulo_id, distribuidor_id))
            if existing:
                existing.articulo_referencia_distribuidor = clean["articulo_referencia_distribuidor"]
                existing.articulo_descripcion_distribuidor = clean["articulo_descripcion_distribuidor"]
                session.add(existing)
            else:
                session.add(ReferenciaDistribuidor(**clean))
            session.commit()

    def delete_reference(self, articulo_id: str, distribuidor_id: str) -> None:
        with Session(engine) as session:
            entity = session.get(ReferenciaDistribuidor, (articulo_id, distribuidor_id))
            if entity:
                session.delete(entity)
                session.commit()

    def import_references(self, file_path: str, schema: list[dict[str, Any]]) -> tuple[int, list[str]]:
        aliases = {
            "articulo_id": ["id_articulo", "articuloid"],
            "distribuidor_id": ["id_distribuidor", "distribuidor"],
            "articulo_referencia_distribuidor": ["referencia", "ref_distribuidor", "ref_dist"],
            "articulo_descripcion_distribuidor": ["descripcion", "desc_distribuidor", "desc_dist"],
        }
        return self.import_service.import_with_schema(
            file_path=Path(file_path),
            schema=schema,
            create_fn=lambda payload: self.upsert_reference(payload),
            required_fields=["articulo_id", "distribuidor_id"],
            aliases=aliases,
        )

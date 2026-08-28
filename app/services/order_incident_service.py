from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import mimetypes
from pathlib import Path
import shutil
from uuid import uuid4

from sqlmodel import Session, select

from app.core.config import DATA_DIR, PEDIDO_INCIDENCIAS_DIR
from app.core.database import engine
from app.models import AlbaranItem, IngredienteIreks, PedidoIncidencia, PedidoIncidenciaImagen


ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class ReceivedArticleOption:
    item_id: str
    codigo: str
    descripcion: str
    lote: str
    caducidad: date | None
    unidades: float
    albaran_numero: str
    recepcion: date

    @property
    def label(self) -> str:
        parts = [f"{self.codigo} — {self.descripcion}".strip(" —")]
        if self.lote:
            parts.append(f"Lote {self.lote}")
        if self.albaran_numero:
            parts.append(f"Albarán {self.albaran_numero}")
        parts.append(self.recepcion.strftime("%d/%m/%Y"))
        return " | ".join(parts)


@dataclass(frozen=True)
class OrderIncidentRow:
    incidencia: PedidoIncidencia
    articulo: ReceivedArticleOption
    image_count: int


class OrderIncidentService:
    def __init__(self, *, data_dir: Path | None = None) -> None:
        self.data_dir = (data_dir or DATA_DIR).resolve()
        self.images_dir = (
            PEDIDO_INCIDENCIAS_DIR if data_dir is None else self.data_dir / "incidencias_pedidos"
        ).resolve()

    def list_received_articles(self, pedido_id: str) -> list[ReceivedArticleOption]:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return []
        with Session(engine) as session:
            rows = list(
                session.exec(
                    select(AlbaranItem, IngredienteIreks)
                    .join(IngredienteIreks, IngredienteIreks.articulo_id == AlbaranItem.articulo_id, isouter=True)
                    .where(AlbaranItem.pedido_id == clean_pedido_id)
                    .order_by(AlbaranItem.albaran_fecha.desc(), AlbaranItem.albaran_numero, AlbaranItem.item_id)
                )
            )
        return [self._received_option(item, article) for item, article in rows]

    def list_incidents(self, pedido_id: str, albaran_item_id: str = "") -> list[OrderIncidentRow]:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return []
        statement = (
            select(PedidoIncidencia, AlbaranItem, IngredienteIreks)
            .join(AlbaranItem, AlbaranItem.item_id == PedidoIncidencia.albaran_item_id)
            .join(IngredienteIreks, IngredienteIreks.articulo_id == AlbaranItem.articulo_id, isouter=True)
            .where(PedidoIncidencia.pedido_id == clean_pedido_id)
            .order_by(PedidoIncidencia.fecha_incidencia.desc(), PedidoIncidencia.creado_en.desc())
        )
        clean_item_id = str(albaran_item_id or "").strip()
        if clean_item_id:
            statement = statement.where(PedidoIncidencia.albaran_item_id == clean_item_id)
        with Session(engine) as session:
            rows = list(session.exec(statement))
            incident_ids = [incidencia.incidencia_id for incidencia, _item, _article in rows]
            counts: dict[str, int] = {incident_id: 0 for incident_id in incident_ids}
            if incident_ids:
                images = list(
                    session.exec(
                        select(PedidoIncidenciaImagen).where(PedidoIncidenciaImagen.incidencia_id.in_(incident_ids))
                    )
                )
                for image in images:
                    counts[image.incidencia_id] = counts.get(image.incidencia_id, 0) + 1
        return [
            OrderIncidentRow(incidencia, self._received_option(item, article), counts.get(incidencia.incidencia_id, 0))
            for incidencia, item, article in rows
        ]

    def create_incident(
        self,
        *,
        pedido_id: str,
        albaran_item_id: str,
        observaciones: str,
        fecha_incidencia: date | None = None,
    ) -> PedidoIncidencia:
        clean_pedido_id = str(pedido_id or "").strip()
        clean_item_id = str(albaran_item_id or "").strip()
        if not clean_pedido_id or not clean_item_id:
            raise ValueError("Selecciona un artículo recibido.")
        with Session(engine) as session:
            item = session.get(AlbaranItem, clean_item_id)
            if item is None or str(item.pedido_id or "").strip() != clean_pedido_id:
                raise ValueError("El artículo recibido no pertenece al pedido seleccionado.")
            row = PedidoIncidencia(
                pedido_id=clean_pedido_id,
                albaran_item_id=clean_item_id,
                observaciones=str(observaciones or "").strip(),
                fecha_incidencia=fecha_incidencia or date.today(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def update_incident(self, incidencia_id: str, *, observaciones: str, fecha_incidencia: date) -> None:
        with Session(engine) as session:
            row = self._get_incident(session, incidencia_id)
            row.observaciones = str(observaciones or "").strip()
            row.fecha_incidencia = fecha_incidencia
            row.actualizado_en = datetime.utcnow()
            session.add(row)
            session.commit()

    def delete_incident(self, incidencia_id: str) -> None:
        clean_id = str(incidencia_id or "").strip()
        with Session(engine) as session:
            row = self._get_incident(session, clean_id)
            images = list(
                session.exec(select(PedidoIncidenciaImagen).where(PedidoIncidenciaImagen.incidencia_id == clean_id))
            )
            paths = [self.resolve_image_path(image.ruta_relativa) for image in images]
            for image in images:
                session.delete(image)
            session.delete(row)
            session.commit()
        for path in paths:
            path.unlink(missing_ok=True)
        incident_dir = self.images_dir / clean_id
        if incident_dir.exists() and not any(incident_dir.iterdir()):
            incident_dir.rmdir()

    def list_images(self, incidencia_id: str) -> list[PedidoIncidenciaImagen]:
        clean_id = str(incidencia_id or "").strip()
        if not clean_id:
            return []
        with Session(engine) as session:
            return list(
                session.exec(
                    select(PedidoIncidenciaImagen)
                    .where(PedidoIncidenciaImagen.incidencia_id == clean_id)
                    .order_by(PedidoIncidenciaImagen.creado_en, PedidoIncidenciaImagen.imagen_id)
                )
            )

    def add_image(self, incidencia_id: str, source_path: Path) -> PedidoIncidenciaImagen:
        source = Path(source_path).resolve()
        if not source.is_file():
            raise ValueError("La imagen seleccionada no existe.")
        suffix = source.suffix.lower()
        if suffix not in ALLOWED_IMAGE_SUFFIXES:
            raise ValueError("Formato no admitido. Usa JPG, PNG o WEBP.")
        size = source.stat().st_size
        if size > MAX_IMAGE_BYTES:
            raise ValueError("La imagen supera el límite de 10 MB.")
        clean_id = str(incidencia_id or "").strip()
        with Session(engine) as session:
            self._get_incident(session, clean_id)
        target_dir = self.images_dir / clean_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{uuid4()}{suffix}"
        shutil.copy2(source, target)
        relative = target.resolve().relative_to(self.data_dir).as_posix()
        row = PedidoIncidenciaImagen(
            incidencia_id=clean_id,
            ruta_relativa=relative,
            nombre_original=source.name,
            tipo_mime=mimetypes.guess_type(source.name)[0] or "application/octet-stream",
            tamano_bytes=size,
        )
        try:
            with Session(engine) as session:
                session.add(row)
                session.commit()
                session.refresh(row)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return row

    def delete_image(self, imagen_id: str) -> None:
        clean_id = str(imagen_id or "").strip()
        with Session(engine) as session:
            row = session.get(PedidoIncidenciaImagen, clean_id)
            if row is None:
                raise ValueError("Imagen no encontrada.")
            path = self.resolve_image_path(row.ruta_relativa)
            session.delete(row)
            session.commit()
        path.unlink(missing_ok=True)

    def resolve_image_path(self, relative_path: str) -> Path:
        candidate = (self.data_dir / str(relative_path or "")).resolve()
        try:
            candidate.relative_to(self.images_dir)
        except ValueError as exc:
            raise ValueError("Ruta de imagen no válida.") from exc
        return candidate

    @staticmethod
    def _get_incident(session: Session, incidencia_id: str) -> PedidoIncidencia:
        row = session.get(PedidoIncidencia, str(incidencia_id or "").strip())
        if row is None:
            raise ValueError("Incidencia no encontrada.")
        return row

    @staticmethod
    def _received_option(item: AlbaranItem, article: IngredienteIreks | None) -> ReceivedArticleOption:
        codigo = str(getattr(article, "articulo_referencia_corta", "") or "").strip()
        codigo = codigo or str(item.articulo_codigo or "").strip() or str(item.articulo_id or "").strip()
        descripcion = str(getattr(article, "articulo_descripcion", "") or "").strip() or codigo
        return ReceivedArticleOption(
            item_id=str(item.item_id or "").strip(),
            codigo=codigo,
            descripcion=descripcion,
            lote=str(item.articulo_lote or "").strip(),
            caducidad=item.articulo_caducidad,
            unidades=float(item.articulo_cantidad or 0.0),
            albaran_numero=str(item.albaran_numero or "").strip(),
            recepcion=item.albaran_fecha,
        )

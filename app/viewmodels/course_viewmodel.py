from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Asistente, Cliente, Contacto, Curso, CursoDocumento, CursoTecnico, Tecnico


def _col(expr: object) -> Any:
    return cast(Any, expr)


@dataclass
class ContactPickerItem:
    contacto_id: str
    cliente_id: str
    nombre_completo: str
    nif: str
    empresa: str


@dataclass
class AsistenteListadoItem:
    curso_id: str
    contacto_id: str
    cliente_id: str
    observaciones: str
    asistente: str
    nif: str
    empresa: str
    status_confirmacion: bool


@dataclass
class TechnicianPickerItem:
    tecnico_id: str
    nombre_completo: str
    movil: str
    interno: str
    email: str


@dataclass
class CursoTecnicoListadoItem:
    curso_id: str
    tecnico_id: str
    nombre_completo: str
    movil: str
    interno: str
    email: str


class CourseViewModel:
    def list_courses(
        self,
        session: Session,
        term: str = "",
        year: int | None = None,
        month_start: int | None = None,
        month_end: int | None = None,
    ) -> list[Curso]:
        stmt = select(Curso)
        clean_term = (term or "").strip()
        if clean_term:
            like_term = f"%{clean_term}%"
            stmt = stmt.where(_col(Curso.curso_nombre).like(like_term))
        if year:
            stmt = stmt.where(func.strftime("%Y", Curso.curso_fecha) == f"{year:04d}")
        if month_start:
            stmt = stmt.where(func.strftime("%m", Curso.curso_fecha) >= f"{month_start:02d}")
        if month_end:
            stmt = stmt.where(func.strftime("%m", Curso.curso_fecha) <= f"{month_end:02d}")
        stmt = stmt.order_by(_col(Curso.curso_fecha).desc(), _col(Curso.curso_nombre).asc())
        return list(session.exec(stmt))

    def create_course(self, session: Session, payload: dict) -> Curso:
        data = self._normalize_course_payload(payload, force=True)
        course = Curso(**data)
        session.add(course)
        session.commit()
        session.refresh(course)
        self._upsert_documents(
            session,
            course.curso_id,
            {
                "portada": course.portada,
                "invitacion": course.invitacion,
                "recetario": course.recetario,
            },
        )
        return course

    def update_course(self, session: Session, curso_id: str, payload: dict) -> Curso:
        course = session.get(Curso, curso_id)
        if not course:
            raise ValueError("Curso no encontrado")
        data = self._normalize_course_payload(payload, force=False)
        for key, value in data.items():
            setattr(course, key, value)
        session.add(course)
        session.commit()
        session.refresh(course)
        self._upsert_documents(
            session,
            course.curso_id,
            {
                "portada": course.portada,
                "invitacion": course.invitacion,
                "recetario": course.recetario,
            },
        )
        return course

    def delete_course(self, session: Session, curso_id: str) -> bool:
        course = session.get(Curso, curso_id)
        if not course:
            return False
        attendees = session.exec(select(Asistente).where(Asistente.curso_id == curso_id)).all()
        for row in attendees:
            session.delete(row)
        tech_rows = session.exec(select(CursoTecnico).where(CursoTecnico.curso_id == curso_id)).all()
        for row in tech_rows:
            session.delete(row)
        session.commit()

        docs = session.get(CursoDocumento, curso_id)
        if docs:
            session.delete(docs)
            session.commit()

        course = session.get(Curso, curso_id)
        if not course:
            return True
        session.delete(course)
        session.commit()
        return True

    def get_documents(self, session: Session, curso_id: str) -> CursoDocumento:
        docs = session.get(CursoDocumento, curso_id)
        if docs:
            return docs
        docs = CursoDocumento(curso_id=curso_id, portada="", invitacion="", recetario="")
        session.add(docs)
        session.commit()
        session.refresh(docs)
        return docs

    def save_documents(self, session: Session, curso_id: str, payload: dict) -> CursoDocumento:
        docs = self._upsert_documents(session, curso_id, payload)
        course = session.get(Curso, curso_id)
        if course:
            course.portada = str(payload.get("portada") or "")
            course.invitacion = str(payload.get("invitacion") or "")
            course.recetario = str(payload.get("recetario") or "")
            session.add(course)
            session.commit()
        return docs

    def list_contacts_for_picker(self, session: Session, term: str = "") -> list[ContactPickerItem]:
        stmt = (
            select(Contacto, Cliente)
            .join(Cliente, _col(Cliente.cliente_id) == _col(Contacto.cliente_id))
            .order_by(_col(Contacto.apellidos), _col(Contacto.nombre))
        )
        clean_term = (term or "").strip()
        if clean_term:
            like_term = f"%{clean_term}%"
            stmt = stmt.where(
                _col(Contacto.nombre).like(like_term)
                | _col(Contacto.apellidos).like(like_term)
                | _col(Contacto.nif).like(like_term)
                | _col(Cliente.cliente_nombre_comercial).like(like_term)
            )

        rows = session.exec(stmt).all()
        items: list[ContactPickerItem] = []
        for contacto, cliente in rows:
            nombre_completo = f"{(contacto.nombre or '').strip()} {(contacto.apellidos or '').strip()}".strip()
            items.append(
                ContactPickerItem(
                    contacto_id=str(contacto.contacto_id),
                    cliente_id=str(contacto.cliente_id),
                    nombre_completo=nombre_completo,
                    nif=str(contacto.nif or ""),
                    empresa=str(cliente.cliente_nombre_comercial or cliente.cliente_nombre_fiscal or ""),
                )
            )
        return items

    def add_attendee(
        self,
        session: Session,
        curso_id: str,
        contacto_id: str,
        cliente_id: str,
        observaciones: str = "",
        status_confirmacion: bool = False,
    ) -> Asistente:
        curso = session.get(Curso, curso_id)
        if not curso:
            raise ValueError("Curso no encontrado")
        contacto = session.get(Contacto, contacto_id)
        if not contacto:
            raise ValueError("Contacto no encontrado")
        cliente = session.get(Cliente, cliente_id)
        if not cliente:
            raise ValueError("Cliente no encontrado")
        existing = session.get(Asistente, (curso_id, contacto_id))
        if existing:
            existing.cliente_id = cliente_id
            existing.observaciones = observaciones.strip()
            existing.status_confirmacion = bool(status_confirmacion)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        row = Asistente(
            curso_id=curso_id,
            contacto_id=contacto_id,
            cliente_id=cliente_id,
            observaciones=observaciones.strip(),
            status_confirmacion=bool(status_confirmacion),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    def set_attendee_confirmation(
        self,
        session: Session,
        curso_id: str,
        contacto_id: str,
        status_confirmacion: bool,
    ) -> Asistente:
        row = session.get(Asistente, (curso_id, contacto_id))
        if not row:
            raise ValueError("Asistente no encontrado")
        row.status_confirmacion = bool(status_confirmacion)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    def update_attendee_observaciones(
        self,
        session: Session,
        curso_id: str,
        contacto_id: str,
        observaciones: str,
    ) -> Asistente:
        row = session.get(Asistente, (curso_id, contacto_id))
        if not row:
            raise ValueError("Asistente no encontrado")
        row.observaciones = str(observaciones or "").strip()
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    def remove_attendee(self, session: Session, curso_id: str, contacto_id: str) -> bool:
        row = session.get(Asistente, (curso_id, contacto_id))
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True

    def list_attendees(self, session: Session, curso_id: str) -> list[AsistenteListadoItem]:
        stmt = (
            select(Asistente, Contacto, Cliente)
            .join(Contacto, _col(Contacto.contacto_id) == _col(Asistente.contacto_id))
            .join(Cliente, _col(Cliente.cliente_id) == _col(Asistente.cliente_id))
            .where(Asistente.curso_id == curso_id)
            .order_by(_col(Contacto.apellidos), _col(Contacto.nombre))
        )
        rows = session.exec(stmt).all()
        items: list[AsistenteListadoItem] = []
        for asistente, contacto, cliente in rows:
            nombre_completo = f"{(contacto.nombre or '').strip()} {(contacto.apellidos or '').strip()}".strip()
            items.append(
                AsistenteListadoItem(
                    curso_id=str(asistente.curso_id),
                    contacto_id=str(asistente.contacto_id),
                    cliente_id=str(asistente.cliente_id),
                    observaciones=str(asistente.observaciones or ""),
                    asistente=nombre_completo,
                    nif=str(contacto.nif or ""),
                    empresa=str(cliente.cliente_nombre_comercial or cliente.cliente_nombre_fiscal or ""),
                    status_confirmacion=bool(getattr(asistente, "status_confirmacion", False)),
                )
            )
        return items

    def list_technicians_for_picker(self, session: Session, term: str = "") -> list[TechnicianPickerItem]:
        stmt = select(Tecnico).order_by(_col(Tecnico.apellidos), _col(Tecnico.nombre))
        clean_term = (term or "").strip()
        if clean_term:
            like_term = f"%{clean_term}%"
            stmt = stmt.where(
                _col(Tecnico.nombre).like(like_term)
                | _col(Tecnico.apellidos).like(like_term)
                | _col(Tecnico.movil).like(like_term)
                | _col(Tecnico.interno).like(like_term)
                | _col(Tecnico.email).like(like_term)
            )
        rows = session.exec(stmt).all()
        return [
            TechnicianPickerItem(
                tecnico_id=str(item.tecnico_id),
                nombre_completo=f"{(item.nombre or '').strip()} {(item.apellidos or '').strip()}".strip(),
                movil=str(item.movil or ""),
                interno=str(item.interno or ""),
                email=str(item.email or ""),
            )
            for item in rows
        ]

    def add_course_technician(self, session: Session, curso_id: str, tecnico_id: str) -> CursoTecnico:
        curso = session.get(Curso, curso_id)
        if not curso:
            raise ValueError("Curso no encontrado")
        tecnico = session.get(Tecnico, tecnico_id)
        if not tecnico:
            raise ValueError("Tecnico no encontrado")
        existing = session.get(CursoTecnico, (curso_id, tecnico_id))
        if existing:
            return existing
        row = CursoTecnico(curso_id=curso_id, tecnico_id=tecnico_id)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    def remove_course_technician(self, session: Session, curso_id: str, tecnico_id: str) -> bool:
        row = session.get(CursoTecnico, (curso_id, tecnico_id))
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True

    def list_course_technicians(self, session: Session, curso_id: str) -> list[CursoTecnicoListadoItem]:
        stmt = (
            select(CursoTecnico, Tecnico)
            .join(Tecnico, _col(Tecnico.tecnico_id) == _col(CursoTecnico.tecnico_id))
            .where(CursoTecnico.curso_id == curso_id)
            .order_by(_col(Tecnico.apellidos), _col(Tecnico.nombre))
        )
        rows = session.exec(stmt).all()
        return [
            CursoTecnicoListadoItem(
                curso_id=str(link.curso_id),
                tecnico_id=str(link.tecnico_id),
                nombre_completo=f"{(tech.nombre or '').strip()} {(tech.apellidos or '').strip()}".strip(),
                movil=str(tech.movil or ""),
                interno=str(tech.interno or ""),
                email=str(tech.email or ""),
            )
            for link, tech in rows
        ]

    def _upsert_documents(self, session: Session, curso_id: str, payload: dict) -> CursoDocumento:
        docs = session.get(CursoDocumento, curso_id)
        if not docs:
            docs = CursoDocumento(curso_id=curso_id, portada="", invitacion="", recetario="")
        docs.portada = str(payload.get("portada") or "")
        docs.invitacion = str(payload.get("invitacion") or "")
        docs.recetario = str(payload.get("recetario") or "")
        session.add(docs)
        session.commit()
        session.refresh(docs)
        return docs

    def _normalize_course_payload(self, payload: dict, force: bool) -> dict:
        data: dict[str, object] = {}

        if force or "curso_id" in payload:
            curso_id = str(payload.get("curso_id") or "").strip()
            data["curso_id"] = curso_id or str(uuid4())

        if force or "curso_nombre" in payload:
            nombre = str(payload.get("curso_nombre") or "").strip()
            if not nombre:
                raise ValueError("Curso_Nombre es obligatorio")
            data["curso_nombre"] = nombre

        if force or "curso_fecha" in payload:
            parsed_date = self._parse_date(payload.get("curso_fecha"))
            if not parsed_date:
                raise ValueError("Curso_Fecha es obligatorio")
            data["curso_fecha"] = parsed_date

        if force or "invitacion" in payload:
            data["invitacion"] = str(payload.get("invitacion") or "").strip()
        if force or "portada" in payload:
            data["portada"] = str(payload.get("portada") or "").strip()
        if force or "recetario" in payload:
            data["recetario"] = str(payload.get("recetario") or "").strip()
        return data

    def _parse_date(self, raw: object) -> date | None:
        if raw is None:
            return None
        if isinstance(raw, date) and not isinstance(raw, datetime):
            return raw
        if isinstance(raw, datetime):
            return raw.date()
        text = str(raw).strip()
        if not text:
            return None
        for fmt in (
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%d/%m/%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d-%m-%Y",
            "%d-%m-%Y %H:%M:%S",
            "%Y/%m/%d",
            "%Y/%m/%d %H:%M:%S",
        ):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            return None

from sqlmodel import Session

from app.models import Tecnico
from app.repositories.technician_repository import TechnicianRepository


class TechnicianViewModel:
    def __init__(self, repository: TechnicianRepository | None = None) -> None:
        self.repository = repository or TechnicianRepository()

    def list(self, session: Session, term: str = "") -> list[Tecnico]:
        return self.repository.search(session, term)

    def create(self, session: Session, payload: dict) -> Tecnico:
        data = dict(payload)
        data.pop("tecnico_id", None)
        data.pop("tecnico_codigo", None)
        if not str(data.get("nombre") or "").strip():
            raise ValueError("Nombre es obligatorio")
        tecnico = Tecnico(**data)
        return self.repository.create(session, tecnico)

    def update(self, session: Session, tecnico_id: str, payload: dict) -> Tecnico:
        tecnico = self.repository.get_by_id(session, tecnico_id)
        if not tecnico:
            raise ValueError("Tecnico no encontrado")
        for key, value in payload.items():
            if key in {"tecnico_id", "tecnico_codigo"}:
                continue
            setattr(tecnico, key, value)
        if not str(tecnico.nombre or "").strip():
            raise ValueError("Nombre es obligatorio")
        return self.repository.update(session, tecnico)

    def delete(self, session: Session, tecnico_id: str) -> bool:
        return self.repository.delete(session, tecnico_id)

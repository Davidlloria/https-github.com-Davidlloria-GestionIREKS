from sqlmodel import Session

from app.models import Contacto
from app.repositories.contact_repository import ContactRepository


class ContactViewModel:
    def __init__(self, repository: ContactRepository | None = None) -> None:
        self.repository = repository or ContactRepository()

    def list(self, session: Session, term: str = "") -> list[Contacto]:
        return self.repository.search(session, term)

    def create(self, session: Session, payload: dict) -> Contacto:
        contacto = Contacto(**payload)
        return self.repository.create(session, contacto)

    def update(self, session: Session, contacto_id: str, payload: dict) -> Contacto:
        contacto = self.repository.get_by_id(session, contacto_id)
        if not contacto:
            raise ValueError("Contacto no encontrado")
        for key, value in payload.items():
            setattr(contacto, key, value)
        return self.repository.update(session, contacto)

    def delete(self, session: Session, contacto_id: str) -> bool:
        return self.repository.delete(session, contacto_id)

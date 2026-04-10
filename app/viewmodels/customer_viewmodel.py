from sqlmodel import Session

from app.models import Cliente
from app.repositories import CustomerRepository


class CustomerViewModel:
    def __init__(self, repository: CustomerRepository | None = None) -> None:
        self.repository = repository or CustomerRepository()

    def list(self, session: Session, term: str = "") -> list[Cliente]:
        return self.repository.search(session, term)

    def create(self, session: Session, payload: dict) -> Cliente:
        customer = Cliente(**payload)
        return self.repository.create(session, customer)

    def update(self, session: Session, customer_id: int, payload: dict) -> Cliente:
        customer = self.repository.get_by_id(session, customer_id)
        if not customer:
            raise ValueError("Cliente no encontrado")
        for key, value in payload.items():
            setattr(customer, key, value)
        return self.repository.update(session, customer)

    def delete(self, session: Session, customer_id: int) -> bool:
        return self.repository.delete(session, customer_id)


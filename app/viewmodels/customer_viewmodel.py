from uuid import uuid4

from sqlalchemy import text
from sqlmodel import Session

from app.models import Cliente
from app.repositories import CustomerRepository


class CustomerViewModel:
    def __init__(self, repository: CustomerRepository | None = None) -> None:
        self.repository = repository or CustomerRepository()

    def list(self, session: Session, term: str = "") -> list[Cliente]:
        return self.repository.search(session, term)

    def create(self, session: Session, payload: dict) -> Cliente:
        self._normalize_ids(payload, force=True)
        self._ensure_cliente_codigo(session, payload, force=True)
        payload.setdefault("cliente_tipo", "indirecto")
        payload.setdefault("cliente_prospeccion", False)
        customer = Cliente(**payload)
        return self.repository.create(session, customer)

    def update(self, session: Session, customer_id: str, payload: dict) -> Cliente:
        self._normalize_ids(payload, force=False)
        self._ensure_cliente_codigo(session, payload, force=False)
        customer = self.repository.get_by_id(session, customer_id)
        if not customer:
            raise ValueError("Cliente no encontrado")
        for key, value in payload.items():
            setattr(customer, key, value)
        return self.repository.update(session, customer)

    def delete(self, session: Session, customer_id: str) -> bool:
        return self.repository.delete(session, customer_id)

    def _normalize_ids(self, payload: dict, force: bool) -> None:
        if not force and "cliente_id" not in payload:
            return
        cliente_id = (payload.get("cliente_id") or "").strip()
        chosen = cliente_id or str(uuid4())
        payload["cliente_id"] = chosen

    def _ensure_cliente_codigo(self, session: Session, payload: dict, force: bool) -> None:
        if not force and "cliente_codigo" not in payload:
            return
        raw = payload.get("cliente_codigo")
        if raw not in (None, ""):
            try:
                value = int(str(raw).strip())
                if value > 0:
                    payload["cliente_codigo"] = value
                    return
            except ValueError:
                pass
        next_code = int(
            session.execute(text("SELECT COALESCE(MAX(cliente_codigo), 0) + 1 FROM clientes")).one()[0]
        )
        payload["cliente_codigo"] = next_code


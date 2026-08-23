from __future__ import annotations

from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine

from app.models import Cliente
from app.repositories.customer_repository import CustomerRepository


def test_customer_search_matches_distributor_assigned_code(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'customers.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Cliente(
                cliente_id="customer-1",
                cliente_codigo=1,
                cliente_codigo_distribuidor="DIST-2048",
                cliente_nombre_comercial="Panadería Uno",
            )
        )
        session.add(
            Cliente(
                cliente_id="customer-2",
                cliente_codigo=2,
                cliente_codigo_distribuidor="DIST-9999",
                cliente_nombre_comercial="Panadería Dos",
            )
        )
        session.commit()

        rows = CustomerRepository().search(session, "2048")

    assert [row.cliente_id for row in rows] == ["customer-1"]

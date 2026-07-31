from __future__ import annotations

from sqlmodel import SQLModel, Session, create_engine

import app.services.customer_service as customer_service_module
from app.models import Cliente, Receta
from app.services.customer_service import CustomerService


def test_related_recipes_only_returns_non_base_recipes_for_selected_customer(
    tmp_path, monkeypatch
) -> None:
    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'customer-recipes.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(db_engine)
    monkeypatch.setattr(customer_service_module, "engine", db_engine)

    with Session(db_engine) as session:
        session.add_all(
            [
                Cliente(
                    cliente_id="customer-1",
                    cliente_codigo=1,
                    cliente_nombre_comercial="Cliente Uno",
                ),
                Cliente(
                    cliente_id="customer-2",
                    cliente_codigo=2,
                    cliente_nombre_comercial="Cliente Dos",
                ),
                Receta(
                    id=1,
                    cliente_id="customer-1",
                    nombre="Receta del cliente",
                    codigo_receta="CLI-1",
                    es_base=False,
                ),
                Receta(
                    id=2,
                    cliente_id="customer-1",
                    nombre="Receta base IREKS",
                    codigo_receta="BASE-1",
                    es_base=True,
                ),
                Receta(
                    id=3,
                    cliente_id="customer-2",
                    nombre="Receta de otro cliente",
                    codigo_receta="CLI-2",
                    es_base=False,
                ),
            ]
        )
        session.commit()

    rows = CustomerService().related_recipes("customer-1")

    assert [row.id for row in rows] == [1]
    assert all(row.cliente_id == "customer-1" for row in rows)
    assert all(row.es_base is False for row in rows)

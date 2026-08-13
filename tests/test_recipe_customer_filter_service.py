from __future__ import annotations

from sqlmodel import SQLModel, Session, create_engine

import app.services.recipe_service as recipe_service_module
from app.models import Cliente, Receta
from app.services.recipe_service import RecipeService


def test_recipe_customer_filter_matches_code_and_name_case_insensitively(tmp_path, monkeypatch) -> None:
    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'recipe-customer-filter.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(db_engine)
    monkeypatch.setattr(recipe_service_module, "engine", db_engine)

    with Session(db_engine) as session:
        session.add_all(
            [
                Cliente(
                    cliente_id="customer-1",
                    cliente_codigo=123,
                    cliente_nombre_comercial="Panadería Pan A Mar",
                ),
                Cliente(
                    cliente_id="customer-2",
                    cliente_codigo=456,
                    cliente_nombre_comercial="Pastelería Norte",
                ),
            ]
        )
        session.commit()

    service = RecipeService()

    assert [row.cliente_id for row in service.search_customers("PANADERÍA")] == ["customer-1"]
    assert [row.cliente_id for row in service.search_customers("123")] == ["customer-1"]


def test_recipe_customer_can_be_changed_without_replacing_recipe_data(tmp_path, monkeypatch) -> None:
    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'recipe-customer-change.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(db_engine)
    monkeypatch.setattr(recipe_service_module, "engine", db_engine)

    with Session(db_engine) as session:
        session.add_all(
            [
                Cliente(cliente_id="customer-1", cliente_codigo=101, cliente_nombre_comercial="Pan A Mar"),
                Cliente(cliente_id="customer-2", cliente_codigo=202, cliente_nombre_comercial="PastelerÃ­a Norte"),
            ]
        )
        recipe = Receta(cliente_id="customer-1", nombre="Pan base", codigo_receta="PAN-01")
        session.add(recipe)
        session.commit()
        session.refresh(recipe)
        recipe_id = int(recipe.id or 0)

    service = RecipeService()

    assert service.update_recipe_customer(recipe_id, "customer-2") is True
    aggregate = service.get_recipe(recipe_id)
    assert aggregate is not None
    assert aggregate.receta.cliente_id == "customer-2"
    assert aggregate.receta.nombre == "Pan base"
    assert service.update_recipe_customer(999999, "customer-1") is False

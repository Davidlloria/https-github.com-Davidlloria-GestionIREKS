from datetime import date

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import Cliente, IngredienteIreks, Receta, RecetaLinea
from app.services.customer_product_promotion_service import CustomerProductPromotionService
from app.services.recipe_calculation_service import RecipeCalculationService


@pytest.fixture
def promotion_context():
    db_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(db_engine)
    with Session(db_engine) as session:
        customer = Cliente(cliente_id="customer-1", cliente_codigo=1, cliente_nombre_comercial="Panadería Uno")
        product = IngredienteIreks(
            articulo_id="article-1",
            articulo_referencia="IREKS-1",
            articulo_descripcion="Mejorante IREKS",
        )
        session.add(customer)
        session.add(product)
        session.commit()
        session.refresh(product)
        product_id = int(product.id or 0)
    return CustomerProductPromotionService(db_engine=db_engine), product_id


def test_applies_prorated_ten_plus_one_promotion(promotion_context) -> None:
    service, product_id = promotion_context
    promotion = service.save(
        cliente_id="customer-1",
        producto_ireks_id=product_id,
        unidades_compra=10,
        unidades_sin_cargo=1,
    )
    line = RecetaLinea(
        receta_id=1,
        tipo_origen="ireks",
        ingrediente_id=product_id,
        nombre_mostrado="Mejorante IREKS",
        cantidad_base_g=1000,
        precio_kg_snapshot=3.0,
    )

    service.apply_to_lines("customer-1", [line], on_date=date(2026, 8, 27))

    assert line.promocion_id_snapshot == promotion.id
    assert line.promocion_compra_snapshot == 10
    assert line.promocion_sin_cargo_snapshot == 1
    assert line.precio_kg_efectivo_snapshot == pytest.approx(3.0 * 10 / 11)


def test_recipe_calculation_exposes_standard_cost_saving_and_promotional_cost(promotion_context) -> None:
    service, product_id = promotion_context
    service.save(
        cliente_id="customer-1",
        producto_ireks_id=product_id,
        unidades_compra=10,
        unidades_sin_cargo=2,
    )
    recipe = Receta(
        cliente_id="customer-1",
        nombre="Pan",
        codigo_receta="PAN-1",
        numero_piezas=1,
        masa_final_deseada_g=1000,
    )
    line = RecetaLinea(
        receta_id=1,
        tipo_origen="ireks",
        ingrediente_id=product_id,
        nombre_mostrado="Harina IREKS",
        es_harina=True,
        cantidad_base_g=1000,
        precio_kg_snapshot=3.0,
    )

    service.apply_to_lines(recipe.cliente_id, [line])
    result = RecipeCalculationService().calculate(recipe, [line])

    assert result.lineas[0].coste_sin_promocion == pytest.approx(3.0)
    assert result.lineas[0].coste_linea == pytest.approx(2.5)
    assert result.lineas[0].ahorro_promocion == pytest.approx(0.5)
    assert result.receta.coste_total == pytest.approx(2.5)


def test_does_not_apply_inactive_or_out_of_range_promotion(promotion_context) -> None:
    service, product_id = promotion_context
    service.save(
        cliente_id="customer-1",
        producto_ireks_id=product_id,
        unidades_compra=10,
        unidades_sin_cargo=1,
        fecha_desde=date(2027, 1, 1),
    )
    line = RecetaLinea(
        receta_id=1,
        tipo_origen="ireks",
        ingrediente_id=product_id,
        precio_kg_snapshot=3.0,
    )

    service.apply_to_lines("customer-1", [line], on_date=date(2026, 8, 27))

    assert line.promocion_id_snapshot is None
    assert line.precio_kg_efectivo_snapshot == pytest.approx(3.0)


def test_rejects_overlapping_active_promotions(promotion_context) -> None:
    service, product_id = promotion_context
    service.save(
        cliente_id="customer-1",
        producto_ireks_id=product_id,
        unidades_compra=10,
        unidades_sin_cargo=1,
        fecha_desde=date(2026, 1, 1),
        fecha_hasta=date(2026, 12, 31),
    )

    with pytest.raises(ValueError, match="solapada"):
        service.save(
            cliente_id="customer-1",
            producto_ireks_id=product_id,
            unidades_compra=10,
            unidades_sin_cargo=2,
            fecha_desde=date(2026, 6, 1),
            fecha_hasta=date(2027, 5, 31),
        )


def test_allows_non_overlapping_promotion_history(promotion_context) -> None:
    service, product_id = promotion_context
    service.save(
        cliente_id="customer-1",
        producto_ireks_id=product_id,
        unidades_compra=10,
        unidades_sin_cargo=1,
        fecha_hasta=date(2025, 12, 31),
    )
    service.save(
        cliente_id="customer-1",
        producto_ireks_id=product_id,
        unidades_compra=10,
        unidades_sin_cargo=2,
        fecha_desde=date(2026, 1, 1),
    )

    assert len(service.list_for_customer("customer-1")) == 2


def test_recipe_line_migration_adds_promotion_snapshots(monkeypatch) -> None:
    from app.core import database

    migration_engine = create_engine("sqlite://", poolclass=StaticPool)
    with migration_engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE receta_lineas (
                id INTEGER PRIMARY KEY,
                receta_id INTEGER NOT NULL,
                proceso_nombre TEXT NOT NULL DEFAULT 'Masa final',
                tipo_linea TEXT NOT NULL DEFAULT 'ingrediente',
                proceso_origen_nombre TEXT NOT NULL DEFAULT '',
                cantidad_origen_g FLOAT NOT NULL DEFAULT 0
            )
            """
        )
    monkeypatch.setattr(database, "engine", migration_engine)

    database._migrate_receta_lineas_process_fields()

    with migration_engine.begin() as connection:
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(receta_lineas)")}
    assert {
        "promocion_id_snapshot",
        "promocion_compra_snapshot",
        "promocion_sin_cargo_snapshot",
        "precio_kg_efectivo_snapshot",
        "coste_sin_promocion",
        "ahorro_promocion",
    } <= columns

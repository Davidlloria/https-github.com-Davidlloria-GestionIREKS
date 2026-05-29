from datetime import date
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

from fastapi.testclient import TestClient

import app.services.ingredient_ireks_service as ingredient_ireks_service_module
import app.services.ingredient_std_service as ingredient_std_service_module
import app.services.order_query_service as order_query_service_module
import app.services.warehouse_inventory_service as warehouse_inventory_service_module
from app.api.main import create_app
from app.models import (
    AlmacenMovimiento,
    AlmacenStock,
    Cliente,
    Distribuidor,
    Envase,
    Fabricante,
    Familia,
    IngredienteIreks,
    IngredienteStd,
    InventarioCabecera,
    InventarioDetalle,
    MateriaPrimaPrecio,
    MateriaPrimaValorNutricional,
    Pedido,
    PedidoItem,
    PedidoPendiente,
    Proveedor,
    Subfamilia,
    TarifaPrecioIreks,
)


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'readonly-api.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(ingredient_ireks_service_module, "engine", engine)
    monkeypatch.setattr(ingredient_std_service_module, "engine", engine)
    monkeypatch.setattr(order_query_service_module, "engine", engine)
    monkeypatch.setattr(warehouse_inventory_service_module, "engine", engine)
    return TestClient(create_app())


def test_ingredients_readonly_endpoints(api_client: TestClient) -> None:
    with Session(ingredient_ireks_service_module.engine) as session:
        session.add(Distribuidor(distribuidor_id="dist-1", distribuidor_codigo=1, distribuidor_nombre_comercial="IGSA"))
        session.add(Proveedor(proveedor_id="prov-1", proveedor_codigo=1, proveedor_nombre_comercial="Proveedor Demo"))
        session.add(Fabricante(fabricante_id="fab-1", fabricante_codigo=1, fabricante_nombre="IREKS"))
        session.add(
            Familia(
                articulo_familia_id="fam-1",
                fabricante_id="fab-1",
                articulo_familia_nombre="Panificacion",
                articulo_familia_codigo="PAN",
            )
        )
        session.add(
            Subfamilia(
                articulo_familia_id="fam-1",
                articulo_subfamilia_id="sub-1",
                articulo_subfamilia_nombre="Mejorantes",
                articulo_subfamilia_codigo="MEJ",
            )
        )
        session.add(Envase(envase_id="env-1", envase_codigo=1, envase_nombre="Saco"))
        session.add(
            IngredienteIreks(
                id=1,
                almacen_id="alm-1",
                fabricante_id="fab-1",
                distribuidor_id="dist-1",
                articulo_id="ireks-article-1",
                articulo_referencia="IR-001",
                articulo_referencia_corta="IR1",
                articulo_descripcion="Mejorante IREKS",
                articulo_envase_id="env-1",
                articulo_envase_cantidad=2,
                articulo_envase_peso=5,
                articulo_envase_peso_total=10,
                articulo_familia_id="fam-1",
                articulo_subfamilia_id="sub-1",
                articulo_status_activo=True,
                articulo_status_en_lista=True,
            )
        )
        session.add(
            IngredienteStd(
                articulo_id="std-article-1",
                articulo_referencia_distribuidor="STD-001",
                proveedor_id="prov-1",
                distribuidor_id="prov-1",
                articulo_descripcion="Harina fuerza",
                formato="SACO",
                formato_cantidad=25,
                formato_unidad="kg",
                activo=True,
            )
        )
        session.add(MateriaPrimaPrecio(articulo_id="std-article-1", fecha_precio=date(2026, 5, 1), costo_neto=30.0))
        session.add(MateriaPrimaValorNutricional(articulo_id="ireks-article-1", energia_kcal=300.0))
        session.add(TarifaPrecioIreks(articulo_id="ireks-article-1", tarifa_ano=2026, precio_distribuidor=12.5))
        session.commit()

    ireks_list = api_client.get("/ingredients/ireks", params={"q": "Mejorante"})
    assert ireks_list.status_code == 200
    assert ireks_list.json()["rows"][0]["articulo_id"] == "ireks-article-1"
    assert ireks_list.json()["catalogs"]["fabricantes"][0]["name"] == "IREKS"

    ireks_detail = api_client.get("/ingredients/ireks/1")
    assert ireks_detail.status_code == 200
    assert ireks_detail.json()["articulo_referencia"] == "IR-001"

    nutrition = api_client.get("/ingredients/ireks/ireks-article-1/nutrition")
    assert nutrition.status_code == 200
    assert nutrition.json()["energia_kcal"] == 300.0

    tarifas = api_client.get("/ingredients/ireks/ireks-article-1/tarifas")
    assert tarifas.status_code == 200
    assert tarifas.json()[0]["tarifa_ano"] == 2026

    std_list = api_client.get("/ingredients/std", params={"q": "Harina"})
    assert std_list.status_code == 200
    assert std_list.json()[0]["articulo_id"] == "std-article-1"
    assert std_list.json()[0]["distribuidor_nombre"] == "Proveedor Demo"

    std_prices = api_client.get("/ingredients/std/std-article-1/prices")
    assert std_prices.status_code == 200
    assert std_prices.json()[0]["costo_neto"] == 30.0


def test_warehouse_readonly_endpoints(api_client: TestClient) -> None:
    with Session(warehouse_inventory_service_module.engine) as session:
        session.add(AlmacenStock(almacen_id="alm-1", articulo_id="article-1", cantidad_total=7.5))
        session.add(
            AlmacenMovimiento(
                almacen_id="alm-1",
                articulo_id="article-1",
                pedido_numero="P-1",
                cantidad=7.5,
                fecha_pedido=date(2026, 5, 20),
            )
        )
        session.add(
            InventarioCabecera(
                inventario_id="inv-1",
                almacen_id="alm-1",
                fecha=date(2026, 5, 21),
                contador="Ana",
                aprobador="Luis",
                lineas=1,
                ajustes=0,
            )
        )
        session.add(
            InventarioDetalle(
                inventario_id="inv-1",
                almacen_id="alm-1",
                articulo_id="article-1",
                teorico_uds=7.5,
                conteo_uds=7.5,
            )
        )
        session.commit()

    stock = api_client.get("/warehouse/stock", params={"almacen_id": "alm-1"})
    assert stock.status_code == 200
    assert stock.json() == [{"almacen_id": "alm-1", "articulo_id": "article-1", "cantidad_total": 7.5}]

    movements = api_client.get("/warehouse/movements", params={"almacen_id": "alm-1"})
    assert movements.status_code == 200
    assert movements.json()[0]["pedido_numero"] == "P-1"

    history = api_client.get("/warehouse/inventory/history", params={"almacen_id": "alm-1"})
    assert history.status_code == 200
    assert history.json()[0]["inventario_id"] == "inv-1"

    detail = api_client.get("/warehouse/inventory/inv-1")
    assert detail.status_code == 200
    assert detail.json()[0]["articulo_id"] == "article-1"


def test_orders_readonly_endpoints(api_client: TestClient) -> None:
    with Session(order_query_service_module.engine) as session:
        session.add(Cliente(cliente_id="alm-1", cliente_codigo=1, cliente_nombre_comercial="Almacen Demo"))
        session.add(
            IngredienteIreks(
                id=1,
                almacen_id="alm-1",
                articulo_id="article-1",
                articulo_referencia="IR-001",
                articulo_descripcion="Producto pedido",
                articulo_envase_peso_total=10.0,
            )
        )
        session.add(
            Pedido(
                pedido_id="order-1",
                almacen_id="alm-1",
                pedido_fecha=date(2026, 5, 20),
                pedido_numero="PED-1",
                pedido_estado="P",
            )
        )
        session.add(
            PedidoItem(
                item_id="item-1",
                pedido_id="order-1",
                pedido_numero="PED-1",
                pedido_item_fecha=date(2026, 5, 20),
                articulo_id="article-1",
                articulo_cantidad=2.0,
            )
        )
        session.add(
            PedidoPendiente(
                pendiente_id="pending-1",
                pedido_id="order-1",
                articulo_id="article-1",
                cantidad_pedida=2.0,
                cantidad_recibida=1.0,
                cantidad_pendiente=1.0,
                estado="pendiente",
            )
        )
        session.commit()

    orders = api_client.get("/orders", params={"year": "2026", "almacen_id": "alm-1"})
    assert orders.status_code == 200
    assert orders.json()[0]["pedido_id"] == "order-1"
    assert orders.json()[0]["almacen_nombre"] == "Almacen Demo"
    assert orders.json()[0]["total_kg"] == 20.0

    detail = api_client.get("/orders/order-1")
    assert detail.status_code == 200
    assert detail.json()["pedido_numero"] == "PED-1"

    items = api_client.get("/orders/order-1/items")
    assert items.status_code == 200
    assert items.json()[0]["item_id"] == "item-1"

    pending = api_client.get("/orders/order-1/pending")
    assert pending.status_code == 200
    assert pending.json()[0]["cantidad_pendiente"] == 1.0

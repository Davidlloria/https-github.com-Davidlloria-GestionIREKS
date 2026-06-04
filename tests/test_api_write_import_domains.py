import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Session, create_engine, select

import app.services.ingredient_ireks_service as ingredient_ireks_service_module
import app.services.ingredient_std_service as ingredient_std_service_module
import app.services.order_document_import_service as order_document_import_service_module
import app.services.order_query_service as order_query_service_module
import app.services.order_service as order_service_module
import app.services.warehouse_inventory_service as warehouse_inventory_service_module
import app.services.warehouse_movement_service as warehouse_movement_service_module
from app.api.main import create_app
from app.models import (
    AlbaranItem,
    AlmacenMovimiento,
    Cliente,
    FacturaItem,
    IngredienteIreks,
    IngredienteStd,
    InventarioCabecera,
    InventarioDetalle,
    MateriaPrimaPrecio,
    Pedido,
    PedidoItem,
    Proveedor,
)


def _write_pdf(path: Path, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path))
    y = 800
    for line in lines:
        pdf.drawString(40, y, line)
        y -= 14
    pdf.save()


def _write_factura_layout_pdf(path: Path) -> None:
    pdf = canvas.Canvas(str(path))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(40, 700, "Numero: 60027")
    pdf.drawString(40, 684, "Fecha: 12/05/26")
    pdf.drawString(360, 700, "Referencia: DEP.14/05 +1")
    pdf.drawString(360, 684, "Albaran: 2026090075")
    pdf.drawString(25, 570, "Codigo")
    pdf.drawString(73, 570, "Descripcion")
    pdf.drawString(258, 570, "UM")
    pdf.drawString(303, 570, "Uds.")
    pdf.drawString(338, 570, "Env.")
    pdf.drawString(382, 570, "Kg/Lit.")
    pdf.drawString(434, 570, "Precio")
    pdf.drawString(468, 570, "Dto.")
    pdf.drawString(506, 570, "Total")
    pdf.drawString(552, 570, "IVA")
    pdf.drawString(25, 545, "D1749044")
    pdf.drawString(90, 545, "AROMA VAINILLA PRIMA")
    pdf.drawString(258, 545, "KG")
    pdf.drawString(303, 545, "24")
    pdf.drawString(338, 545, "1,00")
    pdf.drawString(382, 545, "24,00")
    pdf.drawString(434, 545, "10,83")
    pdf.drawString(468, 545, "20,0")
    pdf.drawString(506, 545, "207,94")
    pdf.drawString(552, 545, "0,0")
    pdf.drawString(73, 530, "Lote:")
    pdf.drawString(115, 530, "60182876")
    pdf.drawString(73, 515, "Caducidad:")
    pdf.drawString(121, 515, "29/07/28")
    pdf.drawString(73, 250, "TOTAL KILOS:")
    pdf.drawString(148, 250, "24,00")
    pdf.drawString(73, 230, "IMPORTE NETO:")
    pdf.drawString(148, 230, "207,94")
    pdf.drawString(73, 210, "TOTAL:")
    pdf.drawString(148, 210, "207,94")
    pdf.save()


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'write-api.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(ingredient_ireks_service_module, "engine", engine)
    monkeypatch.setattr(ingredient_std_service_module, "engine", engine)
    monkeypatch.setattr(order_document_import_service_module, "engine", engine)
    monkeypatch.setattr(order_query_service_module, "engine", engine)
    monkeypatch.setattr(order_service_module, "engine", engine)
    monkeypatch.setattr(warehouse_inventory_service_module, "engine", engine)
    monkeypatch.setattr(warehouse_movement_service_module, "engine", engine)
    return TestClient(create_app())


def test_ireks_tarifa_write_endpoints(api_client: TestClient) -> None:
    created = api_client.post(
        "/ingredients/ireks/tarifas",
        json={
            "articulo_id": "article-1",
            "tarifa_ano": 2026,
            "precio_fabricante": 10.0,
            "precio_distribuidor": 12.0,
            "descuento_pct": 5.0,
        },
    )
    assert created.status_code == 201
    tarifa_id = created.json()["id"]
    assert created.json()["precio_distribuidor"] == 12.0

    updated = api_client.patch(
        f"/ingredients/ireks/tarifas/{tarifa_id}",
        json={
            "tarifa_ano": 2026,
            "precio_fabricante": 11.0,
            "precio_distribuidor": 13.0,
            "descuento_pct": 6.0,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["precio_fabricante"] == 11.0
    assert updated.json()["descuento_pct"] == 6.0

    listed = api_client.get("/ingredients/ireks/article-1/tarifas")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == tarifa_id

    deleted = api_client.delete(f"/ingredients/ireks/tarifas/{tarifa_id}")
    assert deleted.status_code == 204
    assert api_client.delete(f"/ingredients/ireks/tarifas/{tarifa_id}").status_code == 404


def test_std_active_write_endpoint(api_client: TestClient) -> None:
    with Session(ingredient_std_service_module.engine) as session:
        session.add(Proveedor(proveedor_id="prov-1", proveedor_codigo=1, proveedor_nombre_comercial="Proveedor"))
        session.add(
            IngredienteStd(
                articulo_id="std-1",
                articulo_referencia_distribuidor="STD-1",
                proveedor_id="prov-1",
                distribuidor_id="prov-1",
                articulo_descripcion="Materia prima",
                activo=True,
            )
        )
        session.commit()

    updated = api_client.patch("/ingredients/std/std-1/active", json={"activo": False})
    assert updated.status_code == 200
    assert updated.json()["articulo_id"] == "std-1"
    assert updated.json()["activo"] is False

    assert api_client.patch("/ingredients/std/missing/active", json={"activo": True}).status_code == 404


def test_ireks_product_crud_endpoints(api_client: TestClient) -> None:
    created = api_client.post(
        "/ingredients/ireks",
        json={
            "almacen_id": "alm-1",
            "fabricante_id": "fab-1",
            "distribuidor_id": "dist-1",
            "articulo_referencia": "IR-API-1",
            "articulo_referencia_corta": "IRAPI1",
            "articulo_descripcion": "Producto IREKS API",
            "articulo_envase_cantidad": 3,
            "articulo_envase_peso": 4,
            "transporte_cajas_por_capa": 2,
            "transporte_capas_por_pallet": 5,
            "categoria": "Harina",
            "articulo_status_activo": True,
            "articulo_status_en_lista": True,
        },
    )
    assert created.status_code == 201
    body = created.json()
    row_id = body["id"]
    assert body["articulo_id"]
    assert body["articulo_envase_peso_total"] == 12.0
    assert body["transporte_cajas_por_pallet"] == 10.0
    assert body["transporte_unidades_por_pallet"] == 30.0
    assert body["transporte_kg_por_pallet"] == 120.0
    assert body["categoria"] == "harina"

    updated = api_client.patch(
        f"/ingredients/ireks/{row_id}",
        json={
            "articulo_descripcion": "Producto IREKS API actualizado",
            "articulo_envase_cantidad": 2,
            "articulo_envase_peso": 6,
            "articulo_status_en_lista": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["articulo_descripcion"] == "Producto IREKS API actualizado"
    assert updated.json()["articulo_envase_peso_total"] == 12.0
    assert updated.json()["articulo_status_en_lista"] is False

    deleted = api_client.delete(f"/ingredients/ireks/{row_id}")
    assert deleted.status_code == 204
    assert api_client.get(f"/ingredients/ireks/{row_id}").status_code == 404


def test_ireks_product_delete_with_dependencies_returns_conflict(api_client: TestClient) -> None:
    created = api_client.post(
        "/ingredients/ireks",
        json={
            "almacen_id": "alm-1",
            "fabricante_id": "fab-1",
            "distribuidor_id": "dist-1",
            "articulo_referencia": "IR-API-DEP-1",
            "articulo_descripcion": "Producto IREKS con dependencias",
            "articulo_status_activo": True,
            "articulo_status_en_lista": True,
        },
    )
    assert created.status_code == 201
    row_id = created.json()["id"]
    articulo_id = created.json()["articulo_id"]

    with Session(order_service_module.engine) as session:
        session.add(Pedido(pedido_id="order-ireks-del", almacen_id="alm-1", pedido_fecha=date(2026, 5, 30)))
        session.add(
            PedidoItem(
                pedido_id="order-ireks-del",
                pedido_item_fecha=date(2026, 5, 30),
                articulo_id=articulo_id,
                articulo_cantidad=1.0,
            )
        )
        session.commit()

    deleted = api_client.delete(f"/ingredients/ireks/{row_id}")
    assert deleted.status_code == 409
    assert "dependencias" in deleted.json()["detail"].lower()


def test_std_product_crud_endpoints(api_client: TestClient) -> None:
    with Session(ingredient_std_service_module.engine) as session:
        session.add(Proveedor(proveedor_id="prov-api", proveedor_codigo=10, proveedor_nombre_comercial="Proveedor API"))
        session.commit()

    created = api_client.post(
        "/ingredients/std",
        json={
            "articulo_referencia_distribuidor": "STD-API-1",
            "proveedor_id": "prov-api",
            "articulo_descripcion": "Materia API SACO 25 KG",
            "categoria": "Harina",
            "formato": "SACO",
            "formato_cantidad": 25,
            "formato_unidad": "kg",
            "pvp_formato": 50.0,
            "activo": True,
        },
    )
    assert created.status_code == 201
    body = created.json()
    articulo_id = body["articulo_id"]
    assert articulo_id
    assert body["proveedor_id"] == "prov-api"
    assert body["distribuidor_id"] == "prov-api"
    assert body["distribuidor_nombre"] == "Proveedor API"
    assert body["categoria"] == "harina"

    updated = api_client.patch(
        f"/ingredients/std/{articulo_id}",
        json={
            "articulo_descripcion": "Materia API actualizada",
            "pvp_formato": 60.0,
            "activo": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["articulo_descripcion"] == "Materia API actualizada"
    assert updated.json()["activo"] is False

    with Session(ingredient_std_service_module.engine) as session:
        prices = list(session.exec(select(MateriaPrimaPrecio).where(MateriaPrimaPrecio.articulo_id == articulo_id)))
    assert len(prices) == 1
    assert prices[0].costo_neto == 60.0

    deleted = api_client.delete(f"/ingredients/std/{articulo_id}")
    assert deleted.status_code == 204
    assert api_client.get(f"/ingredients/std/{articulo_id}").status_code == 404


def test_std_product_delete_with_dependencies_returns_conflict(api_client: TestClient) -> None:
    with Session(ingredient_std_service_module.engine) as session:
        session.add(Proveedor(proveedor_id="prov-del", proveedor_codigo=11, proveedor_nombre_comercial="Proveedor DEL"))
        session.commit()

    created = api_client.post(
        "/ingredients/std",
        json={
            "articulo_referencia_distribuidor": "STD-DEL-1",
            "proveedor_id": "prov-del",
            "articulo_descripcion": "Materia prima con dependencias",
            "formato": "SACO",
            "formato_cantidad": 25,
            "formato_unidad": "kg",
            "pvp_formato": 50.0,
            "activo": True,
        },
    )
    assert created.status_code == 201
    articulo_id = created.json()["articulo_id"]

    with Session(order_service_module.engine) as session:
        session.add(Pedido(pedido_id="order-std-del", almacen_id="alm-1", pedido_fecha=date(2026, 5, 30)))
        session.add(
            PedidoItem(
                pedido_id="order-std-del",
                pedido_item_fecha=date(2026, 5, 30),
                articulo_id=articulo_id,
                articulo_cantidad=1.0,
            )
        )
        session.commit()

    deleted = api_client.delete(f"/ingredients/std/{articulo_id}")
    assert deleted.status_code == 409
    assert "dependencias" in deleted.json()["detail"].lower()


def test_manual_warehouse_movement_write_endpoint(api_client: TestClient) -> None:
    created = api_client.post(
        "/warehouse/movements",
        json={
            "almacen_id": "alm-1",
            "articulo_id": "article-1",
            "cantidad": 4.5,
            "mode": "in",
            "fecha_pedido": "2026-05-29",
            "articulo_lote": "L-1",
            "pedido_albaran_numero": "MANUAL-API",
        },
    )
    assert created.status_code == 201
    assert created.json()["cantidad"] == 4.5
    assert created.json()["pedido_albaran_numero"] == "MANUAL-API"
    assert created.json()["fecha_pedido"] == "2026-05-29"

    movements = api_client.get("/warehouse/movements", params={"almacen_id": "alm-1"})
    assert movements.status_code == 200
    assert movements.json()["items"][0]["articulo_lote"] == "L-1"


def test_manual_warehouse_movement_negative_stock_returns_conflict(api_client: TestClient) -> None:
    seed = api_client.post(
        "/warehouse/movements",
        json={
            "almacen_id": "alm-1",
            "articulo_id": "article-1",
            "cantidad": 1.0,
            "mode": "in",
            "fecha_pedido": "2026-05-29",
            "articulo_lote": "L-NEG",
            "pedido_albaran_numero": "MANUAL-SEED",
        },
    )
    assert seed.status_code == 201

    conflict_move = api_client.post(
        "/warehouse/movements",
        json={
            "almacen_id": "alm-1",
            "articulo_id": "article-1",
            "cantidad": 2.0,
            "mode": "out",
            "fecha_pedido": "2026-05-29",
            "articulo_lote": "L-NEG",
            "pedido_albaran_numero": "MANUAL-OUT",
        },
    )
    assert conflict_move.status_code == 409
    assert "stock negativo" in conflict_move.json()["detail"].lower()


def test_inventory_adjustment_write_endpoint(api_client: TestClient) -> None:
    applied = api_client.post(
        "/warehouse/inventory/adjustments",
        json={
            "almacen_id": "alm-1",
            "contador": "Ana",
            "aprobador": "Luis",
            "adjustments": [
                {
                    "articulo_id": "article-1",
                    "articulo_lote": "L-1",
                    "articulo_caducidad": "2026-12-31",
                    "teorico_uds": 10.0,
                    "conteo_uds": 7.0,
                    "diferencia_uds": -3.0,
                    "kg_ajuste": -30.0,
                },
                {
                    "articulo_id": "article-2",
                    "teorico_uds": 5.0,
                    "conteo_uds": 5.0,
                    "diferencia_uds": 0.0,
                    "kg_ajuste": 0.0,
                },
            ],
        },
    )
    assert applied.status_code == 201
    body = applied.json()
    assert body["almacen_id"] == "alm-1"
    assert body["contador"] == "Ana"
    assert body["aprobador"] == "Luis"
    assert body["estado"] == "aprobado"
    assert body["lineas"] == 1
    assert body["ajustes"] == 1

    with Session(warehouse_inventory_service_module.engine) as session:
        headers = list(session.exec(select(InventarioCabecera)))
        details = list(session.exec(select(InventarioDetalle)))
        movements = list(session.exec(select(AlmacenMovimiento)))

    assert len(headers) == 1
    assert headers[0].inventario_id == body["inventario_id"]
    assert len(details) == 1
    assert details[0].inventario_id == body["inventario_id"]
    assert details[0].diferencia_uds == -3.0
    assert details[0].kg_ajuste == -30.0
    assert len(movements) == 1
    assert movements[0].pedido_numero == body["inventario_id"]
    assert movements[0].cantidad == -3.0
    assert movements[0].pedido_albaran_numero == "INV-AJUSTE|CONT:Ana|APROB:Luis"


def test_order_json_import_endpoint(api_client: TestClient, tmp_path: Path) -> None:
    with Session(order_service_module.engine) as session:
        session.add(
            IngredienteIreks(
                id=1,
                almacen_id="alm-1",
                articulo_id="article-1",
                articulo_referencia="IR-001",
                articulo_referencia_corta="IR1",
                articulo_descripcion="Producto importado",
            )
        )
        session.commit()

    source = tmp_path / "pedido.json"
    source.write_text(
        json.dumps(
            {
                "Fecha": "29/05/26",
                "Albaran": "ALB-1",
                "Lineas": [
                    {"Codigo": "IR-001", "Cantidad": "3"},
                    {"Codigo": "UNKNOWN", "Cantidad": "2"},
                    {"Codigo": "IR-001", "Cantidad": "0"},
                ],
            }
        ),
        encoding="utf-8",
    )

    imported = api_client.post(
        "/orders/import/json",
        json={"almacen_id": "alm-1", "source_path": str(source)},
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["pedido_id"]
    assert body["imported_items"] == 1
    assert body["skipped_unknown"] == ["UNKNOWN"]
    assert body["skipped_invalid"] == 1

    with Session(order_service_module.engine) as session:
        rows = list(session.exec(select(PedidoItem)))
    assert len(rows) == 1
    assert rows[0].articulo_id == "article-1"
    assert rows[0].articulo_cantidad == 3.0

    uploaded = api_client.post(
        "/orders/import/json/upload",
        data={"almacen_id": "alm-1"},
        files={
            "file": (
                "pedido_upload.json",
                json.dumps(
                    {
                        "Fecha": "30/05/26",
                        "Albaran": "ALB-2",
                        "Lineas": [{"Codigo": "IR-001", "Cantidad": "1"}],
                    }
                ).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["imported_items"] == 1

    with Session(order_service_module.engine) as session:
        rows = list(session.exec(select(PedidoItem).order_by(PedidoItem.item_id)))
    assert len(rows) == 2


def test_order_albaran_pdf_import_endpoint(api_client: TestClient, tmp_path: Path) -> None:
    with Session(order_document_import_service_module.engine) as session:
        session.add(Pedido(pedido_id="order-albaran", almacen_id="alm-1", pedido_fecha=date(2026, 5, 4)))
        session.add(
            IngredienteIreks(
                id=20,
                almacen_id="alm-1",
                articulo_id="article-albaran",
                articulo_referencia="D1749044",
                articulo_referencia_corta="D1749044",
                articulo_descripcion="AROMA VAINILLA PRIMA",
                articulo_envase_peso_total=1.0,
                articulo_status_en_lista=True,
            )
        )
        session.add(
            PedidoItem(
                pedido_id="order-albaran",
                pedido_item_fecha=date(2026, 5, 4),
                articulo_id="article-albaran",
                articulo_cantidad=24.0,
            )
        )
        session.commit()

    source = tmp_path / "albaran.pdf"
    _write_pdf(
        source,
        [
            "PACKING LIST",
            "Numero:",
            "2026090075",
            "Fecha:",
            "12/05/26",
            "Fecha pedido:",
            "04/05/26",
            "N Pedido:",
            "1244",
            "Cod.Art.",
            "Descripcion",
            "Kilos",
            "Envases",
            "Fecha entrega:",
            "14/05/26",
            "D1749044",
            "AROMA VAINILLA PRIMA",
            "24,00",
            "24",
            "Lote:",
            "60182876",
            "Cons.Pref:",
            "29/07/28",
            "Carga:",
            "Datos transporte",
        ],
    )

    imported = api_client.post(
        "/orders/order-albaran/import/albaran-pdf",
        json={"source_path": str(source)},
    )
    assert imported.status_code == 200
    assert imported.json()["imported"] == 1
    assert imported.json()["errors"] == []

    with Session(order_document_import_service_module.engine) as session:
        items = list(session.exec(select(AlbaranItem)))
        movements = list(session.exec(select(AlmacenMovimiento)))
        pedido = session.get(Pedido, "order-albaran")

    assert len(items) == 1
    assert items[0].albaran_numero == "2026090075"
    assert items[0].articulo_id == "article-albaran"
    assert items[0].articulo_cantidad == 24.0
    assert len(movements) == 1
    assert movements[0].albaran_item_id == items[0].item_id
    assert pedido is not None
    assert pedido.pedido_albaran_numero == "2026090075"

    uploaded = api_client.post(
        "/orders/order-albaran/import/albaran-pdf/upload",
        files={"file": ("albaran_upload.pdf", source.read_bytes(), "application/pdf")},
    )
    assert uploaded.status_code == 200


def test_order_albaran_pdf_import_missing_order_returns_not_found(api_client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "albaran-missing-order.pdf"
    _write_pdf(
        source,
        [
            "PACKING LIST",
            "Numero:",
            "2026090075",
            "Fecha:",
            "12/05/26",
            "Cod.Art.",
            "Descripcion",
            "Kilos",
            "Envases",
            "D1749044",
            "AROMA VAINILLA PRIMA",
            "24,00",
            "24",
        ],
    )

    imported = api_client.post(
        "/orders/order-missing/import/albaran-pdf",
        json={"source_path": str(source)},
    )
    assert imported.status_code == 404
    assert "no existe" in imported.json()["detail"].lower()


def test_order_factura_pdf_import_endpoint(api_client: TestClient, tmp_path: Path) -> None:
    with Session(order_document_import_service_module.engine) as session:
        session.add(Pedido(pedido_id="order-factura", almacen_id="alm-1", pedido_fecha=date(2026, 5, 4)))
        session.add(
            IngredienteIreks(
                id=30,
                almacen_id="alm-1",
                articulo_id="article-factura",
                articulo_referencia="D1749044",
                articulo_referencia_corta="D1749044",
                articulo_descripcion="AROMA VAINILLA PRIMA",
                articulo_envase_peso_total=1.0,
                articulo_status_en_lista=True,
            )
        )
        session.commit()

    source = tmp_path / "factura.pdf"
    _write_factura_layout_pdf(source)

    imported = api_client.post(
        "/orders/order-factura/import/factura-pdf",
        json={"source_path": str(source)},
    )
    assert imported.status_code == 200
    assert imported.json()["imported"] == 1
    assert imported.json()["errors"] == []

    with Session(order_document_import_service_module.engine) as session:
        items = list(session.exec(select(FacturaItem)))
        pedido = session.get(Pedido, "order-factura")

    assert len(items) == 1
    assert items[0].factura_numero == "60027"
    assert items[0].albaran_numero == "2026090075"
    assert items[0].articulo_id == "article-factura"
    assert items[0].precio_unitario == 10.83
    assert pedido is not None
    assert pedido.pedido_factura_numero == "60027"

    uploaded = api_client.post(
        "/orders/order-factura/import/factura-pdf/upload",
        files={"file": ("factura_upload.pdf", source.read_bytes(), "application/pdf")},
    )
    assert uploaded.status_code == 200


def test_order_factura_pdf_import_missing_order_returns_not_found(api_client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "factura-missing-order.pdf"
    _write_factura_layout_pdf(source)

    imported = api_client.post(
        "/orders/order-missing/import/factura-pdf",
        json={"source_path": str(source)},
    )
    assert imported.status_code == 404
    assert "no existe" in imported.json()["detail"].lower()


def test_order_crud_and_line_write_endpoints(api_client: TestClient) -> None:
    with Session(order_service_module.engine) as session:
        session.add(Cliente(cliente_id="alm-1", cliente_codigo=1, cliente_nombre_comercial="Almacen Demo"))
        session.add(
            IngredienteIreks(
                id=1,
                almacen_id="alm-1",
                articulo_id="article-1",
                articulo_referencia="IR-001",
                articulo_descripcion="Producto pedido",
                articulo_envase_peso_total=10.0,
                articulo_status_en_lista=True,
            )
        )
        session.add(
            IngredienteIreks(
                id=2,
                almacen_id="alm-1",
                articulo_id="article-2",
                articulo_referencia="IR-002",
                articulo_descripcion="Producto extra",
                articulo_envase_peso_total=5.0,
                articulo_status_en_lista=True,
            )
        )
        session.commit()

    created = api_client.post(
        "/orders",
        json={
            "almacen_id": "alm-1",
            "pedido_fecha": "2026-05-29",
            "pedido_numero": "PED-API-1",
            "is_pending": True,
            "lines": [{"articulo_id": "article-1", "uds": 2.0}],
        },
    )
    assert created.status_code == 201
    order_id = created.json()["pedido_id"]
    assert created.json()["pedido_estado"] == "P"

    listed = api_client.get("/orders", params={"year": "2026", "almacen_id": "alm-1"})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["pedido_id"] == order_id
    assert listed.json()["items"][0]["total_kg"] == 20.0

    items = api_client.get(f"/orders/{order_id}/items")
    assert items.status_code == 200
    assert len(items.json()["items"]) == 1
    first_item_id = items.json()["items"][0]["item_id"]

    updated = api_client.patch(
        f"/orders/{order_id}",
        json={
            "pedido_fecha": "2026-05-30",
            "pedido_numero": "PED-API-2",
            "submit_mode": "",
            "lines": [{"articulo_id": "article-1", "uds": 3.5}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["pedido_numero"] == "PED-API-2"
    assert updated.json()["pedido_estado"] == ""

    replaced_items = api_client.get(f"/orders/{order_id}/items")
    assert replaced_items.status_code == 200
    assert len(replaced_items.json()["items"]) == 1
    assert replaced_items.json()["items"][0]["item_id"] != first_item_id
    assert replaced_items.json()["items"][0]["articulo_cantidad"] == 3.5

    added_line = api_client.post(
        f"/orders/{order_id}/items",
        json={"articulo_id": "article-2", "articulo_cantidad": 4.0},
    )
    assert added_line.status_code == 201
    added_item_id = added_line.json()["item_id"]
    assert added_line.json()["articulo_id"] == "article-2"

    patched_line = api_client.patch(
        f"/orders/items/{added_item_id}",
        json={"articulo_id": "article-1", "articulo_cantidad": 1.5},
    )
    assert patched_line.status_code == 200
    assert patched_line.json()["articulo_id"] == "article-1"
    assert patched_line.json()["articulo_cantidad"] == 1.5

    deleted_line = api_client.delete(f"/orders/items/{added_item_id}")
    assert deleted_line.status_code == 204
    assert api_client.delete(f"/orders/items/{added_item_id}").status_code == 404

    deleted_order = api_client.delete(f"/orders/{order_id}")
    assert deleted_order.status_code == 204
    assert api_client.get(f"/orders/{order_id}").status_code == 404


def test_order_delete_maps_integrity_error_to_conflict(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(order_service_module.engine) as session:
        session.add(Pedido(pedido_id="order-conflict", almacen_id="alm-1", pedido_fecha=date(2026, 5, 30)))
        session.commit()

    def _raise_integrity_error(self: object, pedido_id: str) -> bool:
        raise IntegrityError("DELETE FROM pedidos", {}, Exception("fk"))

    monkeypatch.setattr(order_service_module.OrderService, "delete_order_if_exists", _raise_integrity_error)

    deleted = api_client.delete("/orders/order-conflict")
    assert deleted.status_code == 409
    assert "dependencias" in deleted.json()["detail"].lower()

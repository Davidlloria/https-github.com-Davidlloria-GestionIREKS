from fastapi.testclient import TestClient

from app.api.main import create_app


def test_ingredient_activity_filters_are_validated() -> None:
    client = TestClient(create_app())

    assert client.get("/ingredients/ireks", params={"activity_filter": "archived"}).status_code == 422
    assert client.get("/ingredients/std", params={"activity_filter": "archived"}).status_code == 422


def test_order_month_filters_are_bounded() -> None:
    client = TestClient(create_app())

    assert client.get("/orders", params={"month_from": 13}).status_code == 422
    assert client.get("/orders", params={"month_to": -1}).status_code == 422


def test_warehouse_history_limit_is_bounded() -> None:
    client = TestClient(create_app())

    assert client.get("/warehouse/inventory/history", params={"limit": 0}).status_code == 422
    assert client.get("/warehouse/inventory/history", params={"limit": 201}).status_code == 422

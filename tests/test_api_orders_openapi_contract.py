from __future__ import annotations

from app.api.main import create_app


EXPECTED_PATHS = {
    "/orders",
    "/orders/{order_id}",
    "/orders/{order_id}/items",
    "/orders/{order_id}/pending",
}


def _operation(spec: dict, path: str) -> dict:
    path_item = spec["paths"][path]
    assert "get" in path_item
    return path_item["get"]


def _parameter_names(operation: dict) -> list[str]:
    return [param["name"] for param in operation.get("parameters", [])]


def test_orders_openapi_contract_freezes_readonly_surface() -> None:
    spec = create_app().openapi()

    order_get_paths = {path for path, item in spec["paths"].items() if path.startswith("/orders") and "get" in item}
    assert order_get_paths == EXPECTED_PATHS

    orders = _operation(spec, "/orders")
    order_detail = _operation(spec, "/orders/{order_id}")
    order_items = _operation(spec, "/orders/{order_id}/items")
    order_pending = _operation(spec, "/orders/{order_id}/pending")

    assert _parameter_names(orders) == ["year", "month_from", "month_to", "almacen_id", "limit", "offset"]
    assert _parameter_names(order_detail) == ["order_id"]
    assert _parameter_names(order_items) == ["order_id", "limit", "offset"]
    assert _parameter_names(order_pending) == ["order_id", "limit", "offset"]

    assert orders["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OrderListResponse"
    }
    assert order_detail["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OrderRead"
    }
    assert order_items["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OrderItemListResponse"
    }
    assert order_pending["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OrderPendingListResponse"
    }

    order_id_param = order_detail["parameters"][0]
    assert order_id_param["in"] == "path"
    assert order_id_param["required"] is True

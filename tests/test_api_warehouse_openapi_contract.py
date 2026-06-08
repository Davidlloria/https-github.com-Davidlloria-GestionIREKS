from __future__ import annotations

from app.api.main import create_app


EXPECTED_PATHS = {
    "/warehouse/stock",
    "/warehouse/movements",
    "/warehouse/inventory/history",
    "/warehouse/inventory/{inventory_id}",
    "/warehouse/inventory/export",
}


def _operation(spec: dict, path: str) -> dict:
    path_item = spec["paths"][path]
    assert "get" in path_item
    return path_item["get"]


def _parameter_names(operation: dict) -> list[str]:
    return [param["name"] for param in operation.get("parameters", [])]


def test_warehouse_openapi_contract_freezes_readonly_surface() -> None:
    spec = create_app().openapi()

    warehouse_get_paths = {
        path
        for path, path_item in spec["paths"].items()
        if path.startswith("/warehouse") and "get" in path_item
    }
    assert warehouse_get_paths == EXPECTED_PATHS

    stock = _operation(spec, "/warehouse/stock")
    movements = _operation(spec, "/warehouse/movements")
    history = _operation(spec, "/warehouse/inventory/history")
    inventory_detail = _operation(spec, "/warehouse/inventory/{inventory_id}")
    inventory_export = _operation(spec, "/warehouse/inventory/export")

    assert _parameter_names(stock) == ["almacen_id", "limit", "offset"]
    assert _parameter_names(movements) == ["almacen_id", "limit", "offset"]
    assert _parameter_names(history) == ["almacen_id", "limit", "offset"]
    assert _parameter_names(inventory_detail) == ["inventory_id"]
    assert _parameter_names(inventory_export) == ["almacen_id", "selected_id"]

    assert stock["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/WarehouseStockListResponse"
    }
    assert movements["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/WarehouseMovementListResponse"
    }
    assert history["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/InventoryHistoryListResponse"
    }
    assert inventory_detail["responses"]["200"]["content"]["application/json"]["schema"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/InventoryDetailRead"},
        "title": "Response List Inventory Detail Warehouse Inventory  Inventory Id  Get",
    }
    assert inventory_export["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/InventoryExportPayload"
    }

    assert _parameter_names(stock) == ["almacen_id", "limit", "offset"]
    assert _parameter_names(movements) == ["almacen_id", "limit", "offset"]
    assert _parameter_names(history) == ["almacen_id", "limit", "offset"]
    assert _parameter_names(inventory_export) == ["almacen_id", "selected_id"]

    assert _parameter_names(inventory_detail) == ["inventory_id"]
    inventory_detail_param = inventory_detail["parameters"][0]
    assert inventory_detail_param["in"] == "path"
    assert inventory_detail_param["required"] is True

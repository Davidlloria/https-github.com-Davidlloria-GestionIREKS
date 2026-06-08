from __future__ import annotations

from app.api.main import create_app


EXPECTED_PATHS = {
    "/ingredients",
    "/ingredients/{ingredient_id}",
}


def _operation(spec: dict, path: str) -> dict:
    path_item = spec["paths"][path]
    assert "get" in path_item
    return path_item["get"]


def _parameter_names(operation: dict) -> list[str]:
    return [param["name"] for param in operation.get("parameters", [])]


def test_ingredients_openapi_contract_freezes_readonly_surface() -> None:
    spec = create_app().openapi()

    ingredient_paths = {path for path in spec["paths"] if path.startswith("/ingredients")}
    assert EXPECTED_PATHS.issubset(ingredient_paths)

    ingredients = _operation(spec, "/ingredients")
    ingredient_detail = _operation(spec, "/ingredients/{ingredient_id}")

    assert _parameter_names(ingredients) == [
        "q",
        "familia_id",
        "subfamilia_id",
        "fabricante_id",
        "activity_filter",
        "distributor_filter_id",
        "limit",
        "offset",
    ]
    assert _parameter_names(ingredient_detail) == ["ingredient_id"]

    assert ingredients["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/IngredientListResponse"
    }
    assert ingredient_detail["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/IngredientDetail"
    }

    ingredient_id_param = ingredient_detail["parameters"][0]
    assert ingredient_id_param["in"] == "path"
    assert ingredient_id_param["required"] is True


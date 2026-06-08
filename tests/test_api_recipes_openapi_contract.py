from __future__ import annotations

from app.api.main import create_app


EXPECTED_PATHS = {
    "/recipes",
    "/recipes/{recipe_id}",
    "/recipes/{recipe_id}/items",
}


def _operation(spec: dict, path: str) -> dict:
    path_item = spec["paths"][path]
    assert "get" in path_item
    return path_item["get"]


def _parameter_names(operation: dict) -> list[str]:
    return [param["name"] for param in operation.get("parameters", [])]


def test_recipes_openapi_contract_freezes_readonly_surface() -> None:
    spec = create_app().openapi()

    recipe_paths = {path for path in spec["paths"] if path.startswith("/recipes")}
    assert recipe_paths == EXPECTED_PATHS

    recipes = _operation(spec, "/recipes")
    recipe_detail = _operation(spec, "/recipes/{recipe_id}")
    recipe_items = _operation(spec, "/recipes/{recipe_id}/items")

    assert _parameter_names(recipes) == ["q", "cliente_id", "es_base", "limit", "offset"]
    assert _parameter_names(recipe_detail) == ["recipe_id"]
    assert _parameter_names(recipe_items) == ["recipe_id"]

    assert recipes["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RecipeListResponse"
    }
    assert recipe_detail["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RecipeDetail"
    }
    assert recipe_items["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RecipeItemListResponse"
    }

    recipe_id_param = recipe_detail["parameters"][0]
    assert recipe_id_param["in"] == "path"
    assert recipe_id_param["required"] is True

    item_recipe_id_param = recipe_items["parameters"][0]
    assert item_recipe_id_param["in"] == "path"
    assert item_recipe_id_param["required"] is True

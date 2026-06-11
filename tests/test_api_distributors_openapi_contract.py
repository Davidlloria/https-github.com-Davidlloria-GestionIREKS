from __future__ import annotations

from app.api.main import create_app


EXPECTED_PATHS = {
    "/distributors",
    "/distributors/{distributor_id}",
}


def _operation(spec: dict, path: str) -> dict:
    path_item = spec["paths"][path]
    assert set(path_item) == {"get"}
    return path_item["get"]


def _parameter_names(operation: dict) -> list[str]:
    return [param["name"] for param in operation.get("parameters", [])]


def test_distributors_openapi_contract_freezes_readonly_surface() -> None:
    spec = create_app().openapi()

    distributor_paths = {path for path in spec["paths"] if path.startswith("/distributors")}
    assert distributor_paths == EXPECTED_PATHS

    list_distributors = _operation(spec, "/distributors")
    detail_distributor = _operation(spec, "/distributors/{distributor_id}")

    assert _parameter_names(list_distributors) == ["q", "limit", "offset"]
    assert _parameter_names(detail_distributor) == ["distributor_id"]

    assert list_distributors["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DistributorListResponse"
    }
    assert detail_distributor["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DistributorDetail"
    }

    distributor_id_param = detail_distributor["parameters"][0]
    assert distributor_id_param["in"] == "path"
    assert distributor_id_param["required"] is True

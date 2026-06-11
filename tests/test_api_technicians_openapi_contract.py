from __future__ import annotations

from app.api.main import create_app


EXPECTED_PATHS = {
    "/technicians",
    "/technicians/{technician_id}",
}


def _operation(spec: dict, path: str) -> dict:
    path_item = spec["paths"][path]
    assert set(path_item) == {"get"}
    return path_item["get"]


def _parameter_names(operation: dict) -> list[str]:
    return [param["name"] for param in operation.get("parameters", [])]


def test_technicians_openapi_contract_freezes_readonly_surface() -> None:
    spec = create_app().openapi()

    technician_paths = {path for path in spec["paths"] if path.startswith("/technicians")}
    assert technician_paths == EXPECTED_PATHS

    list_technicians = _operation(spec, "/technicians")
    detail_technician = _operation(spec, "/technicians/{technician_id}")

    assert _parameter_names(list_technicians) == ["q", "limit", "offset"]
    assert _parameter_names(detail_technician) == ["technician_id"]

    assert list_technicians["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/TechnicianListResponse"
    }
    assert detail_technician["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/TechnicianDetail"
    }

    technician_id_param = detail_technician["parameters"][0]
    assert technician_id_param["in"] == "path"
    assert technician_id_param["required"] is True

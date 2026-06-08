from __future__ import annotations

from app.api.main import create_app


EXPECTED_SALES_PATHS = {
    "/sales/annual-summary",
    "/sales/annual-summary/igsa",
    "/sales/annual-summary/years",
    "/sales/annual-summary/igsa/years",
    "/sales/annual-summary/filters/clients",
    "/sales/annual-summary/filters/products",
    "/sales/annual-summary/filters/manufacturers",
    "/sales/annual-summary/igsa/filters/manufacturers",
    "/sales/annual-summary/filters/families",
    "/sales/annual-summary/igsa/filters/families",
    "/sales/annual-summary/filters/subfamilies",
    "/sales/annual-summary/igsa/filters/subfamilies",
}


def _get_operation(spec: dict, path: str) -> dict:
    path_item = spec["paths"][path]
    assert set(path_item) == {"get"}
    return path_item["get"]


def _get_param_names(operation: dict) -> list[str]:
    return [param["name"] for param in operation.get("parameters", [])]


def test_sales_openapi_contract_freezes_sales_paths_and_models() -> None:
    spec = create_app().openapi()
    sales_paths = {path for path in spec["paths"] if path.startswith("/sales/annual-summary")}
    assert sales_paths == EXPECTED_SALES_PATHS

    summary = _get_operation(spec, "/sales/annual-summary")
    igsa_summary = _get_operation(spec, "/sales/annual-summary/igsa")

    expected_summary_params = [
        "year",
        "month",
        "acumulado",
        "cliente_id",
        "articulo_id",
        "producto_texto",
        "fabricante_id",
        "familia_id",
        "subfamilia_id",
    ]
    expected_igsa_params = [
        "year",
        "month",
        "acumulado",
        "producto_texto",
        "fabricante_id",
        "familia_id",
        "subfamilia_id",
    ]

    assert _get_param_names(summary) == expected_summary_params
    assert _get_param_names(igsa_summary) == expected_igsa_params

    assert summary["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SalesAnnualSummaryResponse"
    }
    assert igsa_summary["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SalesAnnualSummaryResponse"
    }

    years = _get_operation(spec, "/sales/annual-summary/years")
    igsa_years = _get_operation(spec, "/sales/annual-summary/igsa/years")
    assert _get_param_names(years) == []
    assert _get_param_names(igsa_years) == []
    assert years["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SalesYearOptionsResponse"
    }
    assert igsa_years["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SalesYearOptionsResponse"
    }

    filter_paths = {
        "/sales/annual-summary/filters/clients": [],
        "/sales/annual-summary/filters/products": [],
        "/sales/annual-summary/filters/manufacturers": [],
        "/sales/annual-summary/igsa/filters/manufacturers": [],
        "/sales/annual-summary/filters/families": ["fabricante_id"],
        "/sales/annual-summary/igsa/filters/families": ["fabricante_id"],
        "/sales/annual-summary/filters/subfamilies": ["familia_id"],
        "/sales/annual-summary/igsa/filters/subfamilies": ["familia_id"],
    }
    for path, expected_params in filter_paths.items():
        operation = _get_operation(spec, path)
        assert _get_param_names(operation) == expected_params
        assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/SalesFilterOptionsResponse"
        }

    summary_schema = spec["components"]["schemas"]["SalesAnnualSummaryResponse"]
    assert summary_schema["properties"]["source"]["enum"] == ["ireks", "igsa"]
    assert summary_schema["properties"]["source"]["default"] == "ireks"


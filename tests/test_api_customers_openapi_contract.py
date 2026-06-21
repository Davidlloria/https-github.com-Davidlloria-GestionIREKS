from __future__ import annotations

from app.api.main import create_app


EXPECTED_CUSTOMER_PATHS = {
    "/customers",
    "/customers/address-catalogs",
    "/customers/listings",
    "/customers/listings/pdf",
    "/customers/listings/xlsx",
    "/customers/{customer_id}",
}

EXPECTED_CONTACT_PATHS = {
    "/contacts",
    "/contacts/{contact_id}",
    "/contacts/companies",
}


def _operation(spec: dict, path: str) -> dict:
    path_item = spec["paths"][path]
    assert "get" in path_item
    return path_item["get"]


def _parameter_map(operation: dict) -> dict[str, dict]:
    return {param["name"]: param for param in operation.get("parameters", [])}


def _response_schema(operation: dict) -> dict:
    return operation["responses"]["200"]["content"]["application/json"]["schema"]


def test_customers_openapi_contract_freezes_customers_and_contacts_surface() -> None:
    spec = create_app().openapi()

    customer_paths = {path for path in spec["paths"] if path.startswith("/customers")}
    contact_paths = {path for path in spec["paths"] if path.startswith("/contacts")}
    assert customer_paths == EXPECTED_CUSTOMER_PATHS
    assert contact_paths == EXPECTED_CONTACT_PATHS

    customers = _operation(spec, "/customers")
    customer_catalogs = _operation(spec, "/customers/address-catalogs")
    customer_listings = spec["paths"]["/customers/listings"]["post"]
    customer_listings_pdf = spec["paths"]["/customers/listings/pdf"]["post"]
    customer_listings_xlsx = spec["paths"]["/customers/listings/xlsx"]["post"]
    customer_detail = _operation(spec, "/customers/{customer_id}")
    contacts = _operation(spec, "/contacts")
    contact_detail = _operation(spec, "/contacts/{contact_id}")
    contact_companies = _operation(spec, "/contacts/companies")

    assert list(_parameter_map(customers)) == ["q", "limit", "offset"]
    assert list(_parameter_map(customer_catalogs)) == []
    assert list(_parameter_map(customer_detail)) == ["customer_id"]
    assert list(_parameter_map(contacts)) == ["q", "cliente_id", "limit", "offset"]
    assert list(_parameter_map(contact_detail)) == ["contact_id"]
    assert list(_parameter_map(contact_companies)) == []

    assert _response_schema(customers) == {"$ref": "#/components/schemas/CustomerListResponse"}
    assert _response_schema(customer_catalogs) == {"$ref": "#/components/schemas/CustomerAddressCatalogsPayload"}
    assert customer_listings["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CustomerListingResponse"
    }
    assert "application/pdf" in customer_listings_pdf["responses"]["200"]["content"]
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in customer_listings_xlsx["responses"]["200"]["content"]
    assert _response_schema(customer_detail) == {"$ref": "#/components/schemas/CustomerDetail"}
    assert _response_schema(contacts) == {"$ref": "#/components/schemas/ContactListResponse"}
    assert _response_schema(contact_detail) == {"$ref": "#/components/schemas/ContactDetail"}
    assert _response_schema(contact_companies)["type"] == "array"
    assert _response_schema(contact_companies)["items"] == {"$ref": "#/components/schemas/ContactCompanyOption"}

    customers_q = _parameter_map(customers)["q"]["schema"]
    customers_limit = _parameter_map(customers)["limit"]["schema"]
    customers_offset = _parameter_map(customers)["offset"]["schema"]
    assert customers_q["type"] == "string"
    assert customers_q["default"] == ""
    assert customers_q["maxLength"] == 120
    assert customers_limit["type"] == "integer"
    assert customers_limit["default"] == 1000
    assert customers_limit["maximum"] == 1000
    assert customers_limit["minimum"] == 1
    assert customers_offset["type"] == "integer"
    assert customers_offset["default"] == 0
    assert customers_offset["maximum"] == 100000
    assert customers_offset["minimum"] == 0

    contacts_q = _parameter_map(contacts)["q"]["schema"]
    contacts_cliente_id = _parameter_map(contacts)["cliente_id"]["schema"]
    contacts_limit = _parameter_map(contacts)["limit"]["schema"]
    contacts_offset = _parameter_map(contacts)["offset"]["schema"]
    assert contacts_q["type"] == "string"
    assert contacts_q["default"] == ""
    assert contacts_q["maxLength"] == 120
    assert contacts_cliente_id["type"] == "string"
    assert contacts_cliente_id["default"] == ""
    assert contacts_cliente_id["maxLength"] == 64
    assert contacts_limit["type"] == "integer"
    assert contacts_limit["default"] == 1000
    assert contacts_limit["maximum"] == 1000
    assert contacts_limit["minimum"] == 1
    assert contacts_offset["type"] == "integer"
    assert contacts_offset["default"] == 0
    assert contacts_offset["maximum"] == 100000
    assert contacts_offset["minimum"] == 0

    assert _parameter_map(customer_detail)["customer_id"]["in"] == "path"
    assert _parameter_map(customer_detail)["customer_id"]["required"] is True
    assert _parameter_map(contact_detail)["contact_id"]["in"] == "path"
    assert _parameter_map(contact_detail)["contact_id"]["required"] is True

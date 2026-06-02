from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_api_settings_service, get_settings_import_service, get_settings_maintenance_service
from app.api.main import create_app
from app.services.api_settings_service import InvalidSettingsConfigError, UnsupportedSettingsProviderError
from app.services.order_query_service import WarehouseFilterOption


class FakeMaintenanceService:
    def database_status(self) -> dict:
        return {
            "db_path": "data/app.db",
            "legacy_db_path": "data/legacy.db",
            "db_exists": True,
            "legacy_exists": False,
            "db_size_bytes": 128,
            "counts": {"clientes": 2},
            "orphan_contact_links": 1,
        }

    def run_integrity_check(self) -> list[str]:
        return ["ok"]

    def repair_contact_links(self) -> dict[str, int]:
        return {"updated_links": 0, "orphans_before": 1, "orphans_after": 1}

    def create_missing_clients_for_contact_links(self) -> int:
        return 1

    def optimize_database(self) -> None:
        return None

    def backup_database(self, destination: Path) -> Path:
        return destination


class FakeApiSettingsService:
    def __init__(self) -> None:
        self.saved: dict[str, dict] = {}

    def provider_payload(self, provider: str) -> dict:
        if provider != "warehouse":
            raise ValueError("Proveedor de configuracion no soportado.")
        return {
            "provider": "warehouse",
            "enabled": True,
            "config": {"low_stock_threshold_units": 2.0},
        }

    def save_provider(self, provider: str, config: dict) -> dict:
        if provider != "warehouse":
            raise ValueError("Proveedor de configuracion no soportado.")
        self.saved[provider] = dict(config)
        return {
            "provider": provider,
            "enabled": True,
            "config": dict(config),
        }


class FakeImportService:
    def warehouse_filter_options(self) -> list[WarehouseFilterOption]:
        return [WarehouseFilterOption(value="alm-1", label="Almacen API")]

    def import_order_json(self, source: Path, almacen_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            pedido_id="order-api",
            imported_items=2,
            skipped_unknown=[],
            skipped_invalid=0,
        )


class FakeApiSettingsErrorService:
    def provider_payload(self, provider: str) -> dict:
        raise UnsupportedSettingsProviderError("Proveedor de configuracion no soportado.")

    def save_provider(self, provider: str, config: dict) -> dict:
        if provider == "warehouse":
            raise InvalidSettingsConfigError("low_stock_threshold_units debe ser numerico.")
        raise UnsupportedSettingsProviderError("Proveedor de configuracion no soportado.")


def test_settings_maintenance_endpoints_use_service_contracts() -> None:
    app = create_app()
    app.dependency_overrides[get_settings_maintenance_service] = lambda: FakeMaintenanceService()
    client = TestClient(app)

    status = client.get("/settings/maintenance/status")
    assert status.status_code == 200
    assert status.json()["counts"] == {"clientes": 2}
    assert status.json()["orphan_contact_links"] == 1

    integrity = client.post("/settings/maintenance/integrity-check")
    assert integrity.status_code == 200
    assert integrity.json()["ok"] is True
    assert integrity.json()["details"]["messages"] == ["ok"]

    repaired = client.post("/settings/maintenance/repair-contact-links")
    assert repaired.status_code == 200
    assert repaired.json()["details"]["orphans_before"] == 1

    created = client.post("/settings/maintenance/create-missing-contact-clients")
    assert created.status_code == 200
    assert created.json()["details"]["created"] == 1

    optimized = client.post("/settings/maintenance/optimize")
    assert optimized.status_code == 200
    assert optimized.json()["message"] == "Base de datos optimizada."

    backup = client.post("/settings/maintenance/backup", json={"destination_path": "data/backup.db"})
    assert backup.status_code == 200
    assert backup.json()["details"]["path"] == "data\\backup.db" or backup.json()["details"]["path"] == "data/backup.db"


def test_settings_api_and_import_endpoints_use_service_contracts(tmp_path: Path) -> None:
    app = create_app()
    fake_settings = FakeApiSettingsService()
    app.dependency_overrides[get_api_settings_service] = lambda: fake_settings
    app.dependency_overrides[get_settings_import_service] = lambda: FakeImportService()
    client = TestClient(app)

    loaded = client.get("/settings/api/warehouse")
    assert loaded.status_code == 200
    assert loaded.json()["config"]["low_stock_threshold_units"] == 2.0

    saved = client.put(
        "/settings/api/warehouse",
        json={
            "provider": "warehouse",
            "enabled": True,
            "config": {"low_stock_threshold_units": 3.5},
        },
    )
    assert saved.status_code == 200
    assert saved.json()["config"]["low_stock_threshold_units"] == 3.5
    assert fake_settings.saved["warehouse"] == {"low_stock_threshold_units": 3.5}

    assert client.get("/settings/api/unknown").status_code == 404

    warehouses = client.get("/settings/imports/warehouses")
    assert warehouses.status_code == 200
    assert warehouses.json() == [{"almacen_id": "alm-1", "almacen_nombre": "Almacen API"}]

    source = tmp_path / "pedido.json"
    source.write_text("{}", encoding="utf-8")

    imported = client.post(
        "/settings/imports/orders-json",
        json={"file_path": str(source), "almacen_id": "alm-1", "document_type": "order_json"},
    )
    assert imported.status_code == 200
    assert imported.json()["pedido_id"] == "order-api"
    assert imported.json()["imported_items"] == 2

    imported_upload = client.post(
        "/settings/imports/orders-json/upload",
        data={"almacen_id": "alm-1"},
        files={"file": ("pedido.json", b"{}", "application/json")},
    )
    assert imported_upload.status_code == 200
    assert imported_upload.json()["pedido_id"] == "order-api"
    assert imported_upload.json()["imported_items"] == 2


def test_settings_save_api_settings_maps_invalid_config_and_unknown_provider() -> None:
    app = create_app()
    app.dependency_overrides[get_api_settings_service] = lambda: FakeApiSettingsErrorService()
    client = TestClient(app)

    invalid = client.put(
        "/settings/api/warehouse",
        json={
            "provider": "warehouse",
            "enabled": True,
            "config": {"low_stock_threshold_units": "x"},
        },
    )
    assert invalid.status_code == 400
    assert "numerico" in invalid.json()["detail"].lower()

    unknown = client.put(
        "/settings/api/unknown",
        json={
            "provider": "unknown",
            "enabled": True,
            "config": {},
        },
    )
    assert unknown.status_code == 404

from __future__ import annotations

from pathlib import Path

from app.services.settings_maintenance_ui_service import SettingsMaintenanceUiService


class _FakeSettingsMaintenanceService:
    def __init__(self) -> None:
        self.backup_calls: list[Path] = []

    def database_status(self) -> dict[str, object]:
        return {
            "db_path": "data/gestion_ireks.db",
            "db_size_bytes": 2 * 1024 * 1024,
            "counts": {
                "clientes": 2,
                "contactos": 3,
                "provincias": 4,
                "islas": 5,
                "municipios": 6,
                "codigos_postales": 7,
                "localidades": 8,
            },
            "orphan_contact_links": 1,
            "legacy_exists": False,
            "legacy_db_path": "data/legacy.db",
        }

    def run_integrity_check(self) -> list[str]:
        return ["ok"]

    def repair_contact_links(self) -> dict[str, int]:
        return {"updated_links": 3, "orphans_before": 2, "orphans_after": 0}

    def optimize_database(self) -> None:
        return None

    def create_missing_clients_for_contact_links(self) -> int:
        return 4

    def backup_database(self, destination: Path) -> Path:
        self.backup_calls.append(destination)
        return destination


def test_build_status_view_and_outcomes(tmp_path: Path) -> None:
    fake = _FakeSettingsMaintenanceService()
    service = SettingsMaintenanceUiService(settings_maintenance_service=fake)  # type: ignore[arg-type]

    status = service.build_status_view()
    assert "DB activa: data/gestion_ireks.db" == status.db_path_label
    assert "Tamano: 2.00 MB" == status.db_size_label
    assert "clientes=2" in status.db_rows_label
    assert "Contactos sin cliente vinculado: 1" == status.orphans_label
    assert "DB legacy detectada: no" in status.legacy_label
    assert "actualizado" in status.log_message.lower()

    integrity = service.run_integrity_check()
    assert integrity.ok is True
    assert "OK" in integrity.message
    assert "Chequeo de integridad" in integrity.log_message

    repair = service.repair_contact_links()
    assert repair.ok is True
    assert "Enlaces actualizados: 3" in repair.message
    assert "huerfanos_despues=0" in repair.log_message

    optimize = service.optimize_database()
    assert optimize.ok is True
    assert "Optimizacion completada" in optimize.message

    create = service.create_missing_clients()
    assert create.ok is True
    assert "Clientes creados: 4" in create.message

    destination = tmp_path / "backup.db"
    backup = service.backup_database(destination)
    assert backup.ok is True
    assert str(destination) in backup.message
    assert fake.backup_calls == [destination]


def test_integrity_outcome_with_incidencias() -> None:
    class _BadIntegrityService(_FakeSettingsMaintenanceService):
        def run_integrity_check(self) -> list[str]:
            return ["malformed", "error"]

    service = SettingsMaintenanceUiService(settings_maintenance_service=_BadIntegrityService())  # type: ignore[arg-type]
    outcome = service.run_integrity_check()
    assert outcome.ok is False
    assert "malformed" in outcome.message
    assert "INCIDENCIAS" in outcome.log_message

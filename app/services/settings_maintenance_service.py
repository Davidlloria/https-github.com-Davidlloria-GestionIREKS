from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.database import (
    backup_database,
    create_missing_clients_for_contact_links,
    get_database_status,
    optimize_database,
    repair_cliente_contacto_links,
    run_integrity_check,
)


class SettingsMaintenanceService:
    def database_status(self) -> dict[str, Any]:
        return get_database_status()

    def run_integrity_check(self) -> list[str]:
        return run_integrity_check()

    def repair_contact_links(self) -> dict[str, int]:
        return repair_cliente_contacto_links()

    def optimize_database(self) -> None:
        optimize_database()

    def create_missing_clients_for_contact_links(self) -> int:
        return create_missing_clients_for_contact_links()

    def backup_database(self, destination: Path) -> Path:
        return backup_database(destination)

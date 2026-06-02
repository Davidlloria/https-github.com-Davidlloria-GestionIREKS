from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.core.config import DATA_DIR
from app.services.settings_maintenance_service import SettingsMaintenanceService


@dataclass
class SettingsMaintenanceStatusView:
    db_path_label: str
    db_size_label: str
    db_rows_label: str
    orphans_label: str
    legacy_label: str
    log_message: str


@dataclass
class SettingsMaintenanceOutcome:
    ok: bool
    title: str
    message: str
    log_message: str


@dataclass(frozen=True)
class SettingsMaintenanceView:
    refresh_button_label: str = "Actualizar estado"
    integrity_button_label: str = "Comprobar integridad"
    repair_links_button_label: str = "Reparar enlaces Cliente/Contacto"
    create_missing_clients_button_label: str = "Crear clientes faltantes"
    optimize_button_label: str = "Optimizar DB (VACUUM)"
    backup_button_label: str = "Crear backup"
    log_placeholder: str = "Registro de acciones de mantenimiento..."


class SettingsMaintenanceUiService:
    def __init__(self, settings_maintenance_service: SettingsMaintenanceService | None = None) -> None:
        self.settings_maintenance_service = settings_maintenance_service or SettingsMaintenanceService()

    def build_view(self) -> SettingsMaintenanceView:
        return SettingsMaintenanceView()

    def build_backup_default_path(self, timestamp: datetime | None = None) -> Path:
        stamp = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
        return DATA_DIR / f"gestion_ireks_backup_{stamp}.db"

    def build_status_view(self) -> SettingsMaintenanceStatusView:
        status = self.settings_maintenance_service.database_status()
        db_path = status["db_path"]
        size_mb = float(status["db_size_bytes"]) / (1024 * 1024)
        counts = status["counts"]
        return SettingsMaintenanceStatusView(
            db_path_label=f"DB activa: {db_path}",
            db_size_label=f"Tamano: {size_mb:.2f} MB",
            db_rows_label=(
                "Registros: "
                f"clientes={counts.get('clientes', 0)} | "
                f"contactos={counts.get('contactos', 0)} | "
                f"provincias={counts.get('provincias', 0)} | "
                f"islas={counts.get('islas', 0)} | "
                f"municipios={counts.get('municipios', 0)} | "
                f"codigos_postales={counts.get('codigos_postales', 0)} | "
                f"localidades={counts.get('localidades', 0)}"
            ),
            orphans_label=f"Contactos sin cliente vinculado: {status.get('orphan_contact_links', 0)}",
            legacy_label=f"DB legacy detectada: {'si' if status['legacy_exists'] else 'no'} ({status['legacy_db_path']})",
            log_message="Estado de base de datos actualizado.",
        )

    def run_integrity_check(self) -> SettingsMaintenanceOutcome:
        result = self.settings_maintenance_service.run_integrity_check()
        ok = all(str(line or "").lower() == "ok" for line in result)
        if ok:
            return SettingsMaintenanceOutcome(
                ok=True,
                title="Integridad DB",
                message="PRAGMA integrity_check: OK",
                log_message=f"Chequeo de integridad: OK -> {', '.join(result)}",
            )
        return SettingsMaintenanceOutcome(
            ok=False,
            title="Integridad DB",
            message="\n".join(result),
            log_message=f"Chequeo de integridad: INCIDENCIAS -> {', '.join(result)}",
        )

    def repair_contact_links(self) -> SettingsMaintenanceOutcome:
        result = self.settings_maintenance_service.repair_contact_links()
        updated = int(result["updated_links"])
        before = int(result["orphans_before"])
        after = int(result["orphans_after"])
        return SettingsMaintenanceOutcome(
            ok=True,
            title="Reparacion completada",
            message=(
                "Enlaces actualizados: "
                f"{updated}\n"
                f"Huerfanos antes: {before}\n"
                f"Huerfanos despues: {after}"
            ),
            log_message=(
                "Reparacion de enlaces completada: "
                f"actualizados={updated}, "
                f"huerfanos_antes={before}, "
                f"huerfanos_despues={after}"
            ),
        )

    def optimize_database(self) -> SettingsMaintenanceOutcome:
        self.settings_maintenance_service.optimize_database()
        return SettingsMaintenanceOutcome(
            ok=True,
            title="Optimizar DB",
            message="Optimizacion completada.",
            log_message="Optimizacion completada (PRAGMA optimize + ANALYZE + VACUUM).",
        )

    def create_missing_clients(self) -> SettingsMaintenanceOutcome:
        created = int(self.settings_maintenance_service.create_missing_clients_for_contact_links())
        return SettingsMaintenanceOutcome(
            ok=True,
            title="Clientes faltantes",
            message=f"Clientes creados: {created}",
            log_message=f"Clientes tecnicos creados: {created}",
        )

    def backup_database(self, destination: Path) -> SettingsMaintenanceOutcome:
        saved_path = self.settings_maintenance_service.backup_database(destination)
        return SettingsMaintenanceOutcome(
            ok=True,
            title="Backup DB",
            message=f"Backup creado en:\n{saved_path}",
            log_message=f"Backup generado: {saved_path}",
        )

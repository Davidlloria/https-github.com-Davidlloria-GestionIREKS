from __future__ import annotations

from sqlmodel import Field

from .base import AppSchema


class ImportRequest(AppSchema):
    file_path: str
    schema_name: str = ""


class ImportResult(AppSchema):
    imported: int = 0
    errors: list[str] = Field(default_factory=list)


class DocumentImportRequest(AppSchema):
    file_path: str
    almacen_id: str = ""
    document_type: str = ""


class MaintenanceStatus(AppSchema):
    db_path: str = ""
    legacy_db_path: str = ""
    db_exists: bool = False
    legacy_exists: bool = False
    db_size_bytes: int = 0
    counts: dict[str, int] = Field(default_factory=dict)
    orphan_contact_links: int = 0


class MaintenanceResult(AppSchema):
    ok: bool = True
    message: str = ""
    details: dict[str, object] = Field(default_factory=dict)


class MaintenanceBackupRequest(AppSchema):
    destination_path: str


class ApiSettingsPayload(AppSchema):
    provider: str = ""
    enabled: bool = False
    config: dict[str, object] = Field(default_factory=dict)


__all__ = [
    "ApiSettingsPayload",
    "DocumentImportRequest",
    "ImportRequest",
    "ImportResult",
    "MaintenanceBackupRequest",
    "MaintenanceResult",
    "MaintenanceStatus",
]

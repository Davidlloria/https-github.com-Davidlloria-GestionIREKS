from __future__ import annotations

from pathlib import Path

from app.services.api_settings_service import ApiSettingsService


class FatSecretSettingsService:
    DEFAULT_SCOPE = "basic"

    def load(self) -> dict:
        data = ApiSettingsService().get_fatsecret()
        return {
            "client_id": str(data.get("client_id") or "").strip(),
            "client_secret": str(data.get("client_secret") or "").strip(),
            "scope": str(data.get("scope") or self.DEFAULT_SCOPE).strip() or self.DEFAULT_SCOPE,
        }

    def save(self, client_id: str, client_secret: str, scope: str | None = None) -> Path:
        return ApiSettingsService().save_fatsecret(
            client_id=str(client_id or "").strip(),
            client_secret=str(client_secret or "").strip(),
            scope=str(scope or self.DEFAULT_SCOPE).strip() or self.DEFAULT_SCOPE,
        )

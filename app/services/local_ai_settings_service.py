from __future__ import annotations

from pathlib import Path

from app.services.api_settings_service import ApiSettingsService


class LocalAISettingsService:
    DEFAULT_BASE_URL = "http://127.0.0.1:11434"
    DEFAULT_MODEL = "qwen3.5:4b"

    def load(self) -> dict:
        data = ApiSettingsService().get_local_ai()
        return {
            "enabled": bool(data.get("enabled", False)),
            "base_url": str(data.get("base_url") or self.DEFAULT_BASE_URL).strip(),
            "model": str(data.get("model") or self.DEFAULT_MODEL).strip(),
        }

    def save(self, *, enabled: bool, base_url: str, model: str) -> Path:
        return ApiSettingsService().save_local_ai(
            enabled=bool(enabled),
            base_url=str(base_url or self.DEFAULT_BASE_URL).strip(),
            model=str(model or self.DEFAULT_MODEL).strip(),
        )

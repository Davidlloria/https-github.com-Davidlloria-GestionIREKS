from __future__ import annotations

from pathlib import Path

from app.services.api_settings_service import ApiSettingsService


class OpenAISettingsService:
    def load(self) -> dict:
        data = ApiSettingsService().get_openai()
        return {
            "api_key": str(data.get("api_key") or "").strip(),
            "use_ai_translation": bool(data.get("use_ai_translation", False)),
        }

    def save(self, api_key: str, use_ai_translation: bool) -> Path:
        return ApiSettingsService().save_openai(
            api_key=str(api_key or "").strip(),
            use_ai_translation=bool(use_ai_translation),
        )


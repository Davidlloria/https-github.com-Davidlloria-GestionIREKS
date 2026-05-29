from __future__ import annotations

from pathlib import Path
from app.services.api_settings_service import ApiSettingsService


class FdcSettingsService:
    DEFAULT_DATA_TYPE = "Foundation"

    def load(self) -> dict:
        api = ApiSettingsService()
        fdc = api.get_fdc()
        openai = api.get_openai()
        data_type = str(fdc.get("data_type") or self.DEFAULT_DATA_TYPE).strip() or self.DEFAULT_DATA_TYPE
        return {
            "api_key": str(fdc.get("api_key") or "").strip(),
            "data_type": data_type,
            "openai_api_key": str(openai.get("api_key") or "").strip(),
            "use_ai_translation": bool(openai.get("use_ai_translation", False)),
        }

    def save(
        self,
        api_key: str,
        data_type: str | None = None,
        openai_api_key: str | None = None,
        use_ai_translation: bool | None = None,
    ) -> Path:
        api = ApiSettingsService()
        current = api.get_openai()
        path = api.save_fdc(
            api_key=str(api_key or "").strip(),
            data_type=str(data_type or self.DEFAULT_DATA_TYPE).strip() or self.DEFAULT_DATA_TYPE,
        )
        if openai_api_key is not None or use_ai_translation is not None:
            api.save_openai(
                api_key=str(openai_api_key if openai_api_key is not None else current.get("api_key", "")).strip(),
                use_ai_translation=bool(
                    current.get("use_ai_translation", False) if use_ai_translation is None else use_ai_translation
                ),
            )
        return path

from __future__ import annotations

from pathlib import Path

from app.services.api_settings_service import ApiSettingsService


class WarehouseSettingsService:
    def load(self) -> dict:
        raw = ApiSettingsService().get_warehouse()
        return {
            "low_stock_threshold_units": float(raw.get("low_stock_threshold_units") or 1.0),
        }

    def save(self, low_stock_threshold_units: float) -> Path:
        value = max(0.0, float(low_stock_threshold_units or 0.0))
        return ApiSettingsService().save_warehouse(low_stock_threshold_units=value)

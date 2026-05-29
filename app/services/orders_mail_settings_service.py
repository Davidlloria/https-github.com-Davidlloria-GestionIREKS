from __future__ import annotations

from pathlib import Path

from app.core.config import PEDIDOS_EMAIL_DESTINO, PEDIDOS_HISTORICO_DIR
from app.services.api_settings_service import ApiSettingsService


class OrdersMailSettingsService:
    def load(self) -> dict:
        data = ApiSettingsService().get_orders_mail()
        historico = str(data.get("historico_dir") or "").strip() or str(PEDIDOS_HISTORICO_DIR)
        return {
            "destino_email": str(data.get("destino_email") or "").strip() or str(PEDIDOS_EMAIL_DESTINO or "").strip(),
            "historico_dir": historico,
        }

    def save(self, destino_email: str, historico_dir: str) -> Path:
        clean_dir = str(historico_dir or "").strip() or str(PEDIDOS_HISTORICO_DIR)
        return ApiSettingsService().save_orders_mail(
            destino_email=str(destino_email or "").strip(),
            historico_dir=clean_dir,
        )

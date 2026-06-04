from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.fatsecret_client import FatSecretClient
from app.services.fatsecret_settings_service import FatSecretSettingsService
from app.services.fdc_nutrition_service import FdcNutritionService
from app.services.fdc_settings_service import FdcSettingsService
from app.services.openai_settings_service import OpenAISettingsService
from app.services.openai_translation_service import OpenAITranslationService
from app.services.orders_mail_settings_service import OrdersMailSettingsService


@dataclass
class SettingsProviderResult:
    ok: bool
    message: str
    path: Path | None = None


@dataclass(frozen=True)
class OrdersMailSettingsView:
    title: str
    destino_email: str
    historico_dir: str
    destino_placeholder: str = "destino@empresa.com"
    historico_placeholder: str = r"E:\...\pedidos_historico"
    selector_button_label: str = "Examinar"
    save_button_label: str = "Guardar"
    info_label: str = "Estos parametros se guardan en data/api_config.json."


@dataclass(frozen=True)
class SettingsProviderView:
    fdc_title: str = "Configuracion API FoodData Central"
    fatsecret_title: str = "Configuracion API FatSecret"
    openai_title: str = "Configuracion API OpenAI"
    secret_info_label: str = "Las claves se guardan en data/api_config.json (secretos cifrados)"
    save_button_label: str = "Guardar"
    test_button_label: str = "Probar conexion"
    fdc_placeholder: str = "Introduce API key de USDA/Data.gov"
    fdc_api_key_label: str = "API key"
    fdc_data_type_label: str = "Tipo de datos"
    fdc_data_type_options: tuple[str, ...] = ("Foundation", "Branded", "Survey (FNDDS)", "SR Legacy")
    fatsecret_client_id_placeholder: str = "FATSECRET_CLIENT_ID"
    fatsecret_client_secret_placeholder: str = "FATSECRET_CLIENT_SECRET"
    fatsecret_scope_placeholder: str = "basic (o: basic barcode)"
    fatsecret_client_id_label: str = "Client ID"
    fatsecret_client_secret_label: str = "Client Secret"
    fatsecret_scope_label: str = "Scope"
    openai_placeholder: str = "OPENAI_API_KEY"
    openai_api_key_label: str = "API key"
    openai_ai_translation_label: str = "Usar traduccion IA (ES->EN) en busquedas FDC"


class SettingsProviderService:
    def __init__(
        self,
        *,
        fdc_settings: FdcSettingsService | None = None,
        fatsecret_settings: FatSecretSettingsService | None = None,
        openai_settings: OpenAISettingsService | None = None,
        orders_mail_settings: OrdersMailSettingsService | None = None,
        fdc_nutrition_factory: type[FdcNutritionService] = FdcNutritionService,
        fatsecret_client_factory: type[FatSecretClient] = FatSecretClient,
        openai_translation_factory: type[OpenAITranslationService] = OpenAITranslationService,
    ) -> None:
        self.fdc_settings = fdc_settings or FdcSettingsService()
        self.fatsecret_settings = fatsecret_settings or FatSecretSettingsService()
        self.openai_settings = openai_settings or OpenAISettingsService()
        self.orders_mail_settings = orders_mail_settings or OrdersMailSettingsService()
        self.fdc_nutrition_factory = fdc_nutrition_factory
        self.fatsecret_client_factory = fatsecret_client_factory
        self.openai_translation_factory = openai_translation_factory

    def load_fdc(self) -> dict[str, Any]:
        data = self.fdc_settings.load()
        return dict(data) if isinstance(data, dict) else {}

    def load_fatsecret(self) -> dict[str, Any]:
        data = self.fatsecret_settings.load()
        return dict(data) if isinstance(data, dict) else {}

    def load_openai(self) -> dict[str, Any]:
        data = self.openai_settings.load()
        return dict(data) if isinstance(data, dict) else {}

    def load_orders_mail(self) -> dict[str, Any]:
        data = self.orders_mail_settings.load()
        return dict(data) if isinstance(data, dict) else {}

    def load_orders_mail_view(self) -> OrdersMailSettingsView:
        data = self.load_orders_mail()
        return OrdersMailSettingsView(
            title="Configuracion envio pedidos por Outlook",
            destino_email=str(data.get("destino_email") or ""),
            historico_dir=str(data.get("historico_dir") or ""),
        )

    def build_ui_view(self) -> SettingsProviderView:
        return SettingsProviderView()

    def save_fdc(self, api_key: str, data_type: str) -> SettingsProviderResult:
        path = self.fdc_settings.save(api_key, data_type=data_type)
        return SettingsProviderResult(ok=True, message="Configuracion de FoodData Central guardada.", path=path)

    def test_fdc(self, api_key: str, data_type: str) -> SettingsProviderResult:
        self.fdc_settings.save(api_key, data_type=data_type)
        service = self.fdc_nutrition_factory(api_key=api_key)
        result = service.fetch_for_query("olive oil")
        if result.ok:
            return SettingsProviderResult(ok=True, message="Conexion OK y respuesta valida.")
        return SettingsProviderResult(ok=False, message=str(result.message or "No se obtuvo respuesta valida."))

    def save_fatsecret(self, client_id: str, client_secret: str, scope: str) -> SettingsProviderResult:
        path = self.fatsecret_settings.save(client_id, client_secret, scope=scope)
        return SettingsProviderResult(ok=True, message="Configuracion de FatSecret guardada.", path=path)

    def test_fatsecret(self, client_id: str, client_secret: str, scope: str) -> SettingsProviderResult:
        self.fatsecret_settings.save(client_id, client_secret, scope=scope)
        client = self.fatsecret_client_factory(client_id=client_id, client_secret=client_secret, scope=scope)
        rows = client.search_food("olive oil", page=0, max_results=1, region="ES")
        if isinstance(rows, list):
            return SettingsProviderResult(ok=True, message="Conexion OK y respuesta valida.")
        return SettingsProviderResult(ok=True, message="Conexion OK.")

    def save_openai(self, api_key: str, use_ai_translation: bool) -> SettingsProviderResult:
        path = self.openai_settings.save(api_key=api_key, use_ai_translation=use_ai_translation)
        return SettingsProviderResult(ok=True, message="Configuracion de OpenAI guardada.", path=path)

    def test_openai(self, api_key: str, use_ai_translation: bool) -> SettingsProviderResult:
        self.openai_settings.save(api_key=api_key, use_ai_translation=use_ai_translation)
        service = self.openai_translation_factory(api_key=api_key)
        result = service.translate_es_to_en("aceite de oliva")
        if result.ok:
            return SettingsProviderResult(ok=True, message="Conexion OK y respuesta valida.")
        return SettingsProviderResult(ok=False, message=str(result.message or "No se obtuvo respuesta valida."))

    def save_orders_mail(self, destino_email: str, historico_dir: str) -> SettingsProviderResult:
        destino = str(destino_email or "").strip()
        historico = str(historico_dir or "").strip()
        if not destino:
            return SettingsProviderResult(ok=False, message="El email destino fijo es obligatorio.")
        if historico:
            Path(historico).mkdir(parents=True, exist_ok=True)
        path = self.orders_mail_settings.save(destino_email=destino, historico_dir=historico)
        return SettingsProviderResult(ok=True, message="Configuracion de pedidos Outlook guardada.", path=path)

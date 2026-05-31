from __future__ import annotations

from pathlib import Path

from app.services.settings_provider_service import SettingsProviderService


class _FakeFdcSettings:
    def __init__(self) -> None:
        self.saved: tuple[str, str] | None = None

    def save(self, api_key: str, data_type: str | None = None) -> Path:
        self.saved = (api_key, str(data_type or ""))
        return Path("data/api_config.json")


class _FakeFatsecretSettings:
    def __init__(self) -> None:
        self.saved: tuple[str, str, str] | None = None

    def save(self, client_id: str, client_secret: str, scope: str | None = None) -> Path:
        self.saved = (client_id, client_secret, str(scope or ""))
        return Path("data/api_config.json")


class _FakeOpenaiSettings:
    def __init__(self) -> None:
        self.saved: tuple[str, bool] | None = None

    def save(self, api_key: str, use_ai_translation: bool) -> Path:
        self.saved = (api_key, bool(use_ai_translation))
        return Path("data/api_config.json")


class _FakeOrdersMailSettings:
    def __init__(self) -> None:
        self.saved: tuple[str, str] | None = None

    def save(self, destino_email: str, historico_dir: str) -> Path:
        self.saved = (destino_email, historico_dir)
        return Path("data/api_config.json")


class _FakeFdcNutrition:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def fetch_for_query(self, _query: str):  # noqa: ANN001
        return type("R", (), {"ok": True, "message": "ok"})()


class _FakeFatsecretClient:
    def __init__(self, **_kwargs) -> None:  # noqa: ANN003
        pass

    def search_food(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        return [{"id": "1"}]


class _FakeOpenAITranslation:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def translate_es_to_en(self, _text: str):  # noqa: ANN001
        return type("R", (), {"ok": True, "message": "ok"})()


def test_save_operations_delegate_to_underlying_settings_services(tmp_path: Path) -> None:
    fdc = _FakeFdcSettings()
    fat = _FakeFatsecretSettings()
    oa = _FakeOpenaiSettings()
    mail = _FakeOrdersMailSettings()
    service = SettingsProviderService(
        fdc_settings=fdc,
        fatsecret_settings=fat,
        openai_settings=oa,
        orders_mail_settings=mail,
        fdc_nutrition_factory=_FakeFdcNutrition,
        fatsecret_client_factory=_FakeFatsecretClient,
        openai_translation_factory=_FakeOpenAITranslation,
    )

    assert service.save_fdc("k1", "Foundation").ok is True
    assert service.save_fatsecret("id", "sec", "basic").ok is True
    assert service.save_openai("ok", True).ok is True
    assert service.save_orders_mail("destino@empresa.com", str(tmp_path)).ok is True

    assert fdc.saved == ("k1", "Foundation")
    assert fat.saved == ("id", "sec", "basic")
    assert oa.saved == ("ok", True)
    assert mail.saved == ("destino@empresa.com", str(tmp_path))


def test_connection_checks_return_ok_for_happy_path() -> None:
    service = SettingsProviderService(
        fdc_settings=_FakeFdcSettings(),
        fatsecret_settings=_FakeFatsecretSettings(),
        openai_settings=_FakeOpenaiSettings(),
        orders_mail_settings=_FakeOrdersMailSettings(),
        fdc_nutrition_factory=_FakeFdcNutrition,
        fatsecret_client_factory=_FakeFatsecretClient,
        openai_translation_factory=_FakeOpenAITranslation,
    )

    assert service.test_fdc("k1", "Foundation").ok is True
    assert service.test_fatsecret("id", "sec", "basic").ok is True
    assert service.test_openai("ok", False).ok is True


def test_orders_mail_requires_destination_email() -> None:
    service = SettingsProviderService(
        orders_mail_settings=_FakeOrdersMailSettings(),
    )
    result = service.save_orders_mail("", "")
    assert result.ok is False
    assert "obligatorio" in result.message.lower()


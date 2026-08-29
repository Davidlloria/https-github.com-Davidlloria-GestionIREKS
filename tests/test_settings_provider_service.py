from __future__ import annotations

from pathlib import Path

from app.services.settings_provider_service import SettingsProviderService


class _FakeFdcSettings:
    def __init__(self) -> None:
        self.saved: tuple[str, str] | None = None

    def load(self) -> dict:
        return {"api_key": "k1", "data_type": "Foundation"}

    def save(self, api_key: str, data_type: str | None = None) -> Path:
        self.saved = (api_key, str(data_type or ""))
        return Path("data/api_config.json")


class _FakeFatsecretSettings:
    def __init__(self) -> None:
        self.saved: tuple[str, str, str] | None = None

    def load(self) -> dict:
        return {"client_id": "id", "client_secret": "sec", "scope": "basic"}

    def save(self, client_id: str, client_secret: str, scope: str | None = None) -> Path:
        self.saved = (client_id, client_secret, str(scope or ""))
        return Path("data/api_config.json")


class _FakeOpenaiSettings:
    def __init__(self) -> None:
        self.saved: tuple[str, bool] | None = None

    def load(self) -> dict:
        return {"api_key": "ok", "use_ai_translation": True}

    def save(self, api_key: str, use_ai_translation: bool) -> Path:
        self.saved = (api_key, bool(use_ai_translation))
        return Path("data/api_config.json")


class _FakeLocalAISettings:
    def __init__(self, embedding_model: str = "embeddinggemma") -> None:
        self.embedding_model = embedding_model
        self.saved: tuple[bool, str, str, str] | None = None

    def load(self) -> dict:
        return {
            "enabled": True,
            "base_url": "http://127.0.0.1:11434/v1",
            "model": "qwen3.5:4b",
            "embedding_model": self.embedding_model,
        }

    def save(self, *, enabled: bool, base_url: str, model: str, embedding_model: str) -> Path:
        self.embedding_model = embedding_model
        self.saved = (enabled, base_url, model, embedding_model)
        return Path("data/api_config.json")


class _FakeLocalAI:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def test_connection(self):
        return type("R", (), {"ok": True, "text": "OK", "message": "Respuesta generada con IA local."})()


class _FakeLocalEmbedding:
    instances = []
    ok = True
    message = ""

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.calls = []
        type(self).instances.append(self)

    def embed(self, texts):
        self.calls.append(list(texts))
        return type(
            "R",
            (),
            {
                "ok": type(self).ok,
                "model": self.kwargs["model"],
                "dimension": 768,
                "message": type(self).message,
                "vectors": ((1.0,),),
            },
        )()


class _FakeOrdersMailSettings:
    def __init__(self) -> None:
        self.saved: tuple[str, str] | None = None

    def load(self) -> dict:
        return {"destino_email": "destino@empresa.com", "historico_dir": "data/historico"}

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


def test_load_operations_delegate_to_underlying_settings_services() -> None:
    service = SettingsProviderService(
        fdc_settings=_FakeFdcSettings(),
        fatsecret_settings=_FakeFatsecretSettings(),
        openai_settings=_FakeOpenaiSettings(),
        orders_mail_settings=_FakeOrdersMailSettings(),
    )

    assert service.load_fdc().get("api_key") == "k1"
    assert service.load_fatsecret().get("client_id") == "id"
    assert service.load_openai().get("api_key") == "ok"
    assert service.load_orders_mail().get("destino_email") == "destino@empresa.com"
    view = service.load_orders_mail_view()
    assert view.destino_email == "destino@empresa.com"
    assert view.historico_dir == "data/historico"
    assert view.title == "Configuracion envio pedidos por Outlook"
    assert view.destino_placeholder == "destino@empresa.com"
    assert view.historico_placeholder == r"E:\...\pedidos_historico"
    assert view.selector_button_label == "Examinar"
    assert view.save_button_label == "Guardar"
    assert view.info_label == "Estos parametros se guardan en data/api_config.json."

    ui_view = service.build_ui_view()
    assert ui_view.fdc_title == "Configuracion API FoodData Central"
    assert ui_view.fatsecret_title == "Configuracion API FatSecret"
    assert ui_view.openai_title == "Configuracion API OpenAI"
    assert ui_view.save_button_label == "Guardar"
    assert ui_view.test_button_label == "Probar conexion"
    assert ui_view.fdc_api_key_label == "API key"
    assert ui_view.fdc_data_type_label == "Tipo de datos"
    assert ui_view.fdc_data_type_options == ("Foundation", "Branded", "Survey (FNDDS)", "SR Legacy")
    assert ui_view.fatsecret_client_id_label == "Client ID"
    assert ui_view.fatsecret_client_secret_label == "Client Secret"
    assert ui_view.fatsecret_scope_label == "Scope"
    assert ui_view.openai_api_key_label == "API key"
    assert ui_view.local_ai_title == "Configuración IA local"
    assert ui_view.local_ai_base_url_placeholder == "http://127.0.0.1:11434"
    assert ui_view.local_ai_model_placeholder == "qwen3.5:4b"
    assert ui_view.local_ai_model_label == "Modelo conversacional"
    assert ui_view.local_ai_embedding_model_label == "Modelo de embeddings"
    assert ui_view.local_ai_embedding_model_placeholder == "embeddinggemma"
    assert ui_view.local_ai_test_embedding_button_label == "Probar embeddings"
    assert "no los descarga automáticamente" in ui_view.local_ai_info_label


def test_local_ai_settings_can_be_loaded_saved_and_tested() -> None:
    settings = _FakeLocalAISettings()
    service = SettingsProviderService(local_ai_settings=settings, local_ai_factory=_FakeLocalAI)

    loaded = service.load_local_ai()
    saved = service.save_local_ai(
        enabled=True,
        base_url="http://127.0.0.1:11434/v1",
        model="qwen3.5:4b",
        embedding_model="embeddinggemma",
    )
    tested = service.test_local_ai(base_url=loaded["base_url"], model=loaded["model"])

    assert loaded["enabled"] is True
    assert saved.ok is True
    assert settings.saved == (
        True,
        "http://127.0.0.1:11434/v1",
        "qwen3.5:4b",
        "embeddinggemma",
    )
    assert tested.ok is True


def test_changed_embedding_model_adds_warning_and_same_model_does_not() -> None:
    settings = _FakeLocalAISettings("embeddinggemma")
    service = SettingsProviderService(local_ai_settings=settings)

    same = service.save_local_ai(
        enabled=True,
        base_url="http://localhost:11434",
        model="chat",
        embedding_model="embeddinggemma",
    )
    changed = service.save_local_ai(
        enabled=True,
        base_url="http://localhost:11434",
        model="chat",
        embedding_model="new-embed",
    )

    assert "ha cambiado" not in same.message
    assert (
        "El modelo de embeddings ha cambiado. Actualiza el índice semántico documental."
        in changed.message
    )


def test_omitted_embedding_model_preserves_previous_value() -> None:
    settings = _FakeLocalAISettings("stored-embed")
    service = SettingsProviderService(local_ai_settings=settings)

    result = service.save_local_ai(
        enabled=True,
        base_url="http://localhost:11434",
        model="chat",
    )

    assert result.ok
    assert settings.saved[-1] == "stored-embed"
    assert "ha cambiado" not in result.message


def test_local_embedding_test_uses_entered_model_without_saving_or_exposing_vectors() -> None:
    _FakeLocalEmbedding.instances.clear()
    _FakeLocalEmbedding.ok = True
    _FakeLocalEmbedding.message = ""
    settings = _FakeLocalAISettings()
    service = SettingsProviderService(
        local_ai_settings=settings,
        local_embedding_factory=_FakeLocalEmbedding,
    )

    result = service.test_local_embedding(
        base_url="http://localhost:11434",
        embedding_model="embed-screen",
    )

    instance = _FakeLocalEmbedding.instances[-1]
    assert result.ok
    assert "embed-screen" in result.message and "768" in result.message
    assert "vector" not in result.message.casefold()
    assert instance.kwargs == {
        "enabled": True,
        "base_url": "http://localhost:11434",
        "model": "embed-screen",
    }
    assert instance.calls == [["Prueba de búsqueda documental de GestionIREKS."]]
    assert settings.saved is None


def test_local_embedding_failure_returns_safe_service_message() -> None:
    _FakeLocalEmbedding.instances.clear()
    _FakeLocalEmbedding.ok = False
    _FakeLocalEmbedding.message = "El modelo local 'missing' no está instalado en Ollama."
    service = SettingsProviderService(
        local_ai_settings=_FakeLocalAISettings(),
        local_embedding_factory=_FakeLocalEmbedding,
    )

    result = service.test_local_embedding(
        base_url="http://localhost:11434",
        embedding_model="missing",
    )

    assert not result.ok
    assert result.message == "El modelo local 'missing' no está instalado en Ollama."

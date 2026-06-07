from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from typing import Any

from app.models import RecetaLinea
from app.services.recipe_active_flow_service import RecipeActiveFlowService, RecipeActivePayload


@dataclass
class _FakeRecipeService:
    calculate_result: Any | None = None
    save_result: Any | None = None
    error: Exception | None = None

    def __post_init__(self) -> None:
        self.calculate_calls: list[dict[str, Any]] = []
        self.save_calls: list[dict[str, Any]] = []
        self.version_calls: list[dict[str, Any]] = []

    def calculate(self, receta: Any, lineas: list[Any], *, sync_categories: bool = False) -> Any:
        self.calculate_calls.append({"receta": receta, "lineas": list(lineas), "sync_categories": sync_categories})
        if self.error is not None:
            raise self.error
        return self.calculate_result

    def save_recipe(self, receta: Any, lineas: list[Any]) -> Any:
        self.save_calls.append({"receta": receta, "lineas": list(lineas)})
        if self.error is not None:
            raise self.error
        return self.save_result

    def save_version(self, receta: Any, lineas: list[Any], comentario: str = "") -> None:
        self.version_calls.append({"receta": receta, "lineas": list(lineas), "comentario": comentario})
        if self.error is not None:
            raise self.error


def _sample_payload(**overrides: Any) -> RecipeActivePayload:
    base = {
        "recipe_id": 7,
        "cliente_id": "cli-1",
        "nombre": "Pan base",
        "codigo_receta": "",
        "version": "",
        "es_base": True,
        "receta_base_id": None,
        "masa_final_deseada_g": 1500.0,
        "peso_pieza_g": 250.0,
        "numero_piezas": 6,
        "merma_pct": 2.5,
        "observaciones": "Notas",
        "proceso": "Masa final",
        "escandallo_data": {"a": 1},
        "elaboracion_data": {"x": 2},
        "proceso_rich_html": "<p>Hola</p>",
        "images_gallery": [{"path": "/img/a.png", "is_main": True, "order": 0}],
        "estado": "",
    }
    base.update(overrides)
    return RecipeActivePayload(**base)


def test_build_recipe_model_merges_payload_and_defaults() -> None:
    service = RecipeActiveFlowService(recipe_service=_FakeRecipeService())
    payload = _sample_payload()

    receta = service.build_recipe_model(payload)

    assert receta.id == 7
    assert receta.cliente_id == "cli-1"
    assert receta.codigo_receta == "Pan base"
    assert receta.version == "1.0"
    assert receta.estado == "borrador"
    assert receta.parametros_elaboracion_json
    assert receta.escandallo_detalle_json


def test_save_recipe_returns_missing_name_without_calling_services() -> None:
    fake_recipe = _FakeRecipeService()
    service = RecipeActiveFlowService(recipe_service=fake_recipe)
    payload = _sample_payload(nombre="")

    result = service.save_recipe(payload, [], selected_cliente_id="cli-1", recipe_tab_index=0)

    assert result.status == "missing_name"
    assert fake_recipe.calculate_calls == []
    assert fake_recipe.save_calls == []


def test_save_recipe_returns_missing_customer_for_customer_tab() -> None:
    fake_recipe = _FakeRecipeService()
    service = RecipeActiveFlowService(recipe_service=fake_recipe)
    payload = _sample_payload(cliente_id="")

    result = service.save_recipe(payload, [], selected_cliente_id="", recipe_tab_index=1)

    assert result.status == "missing_customer"
    assert fake_recipe.calculate_calls == []
    assert fake_recipe.save_calls == []


def test_save_recipe_calls_calculate_and_save() -> None:
    fake_recipe = _FakeRecipeService(
        calculate_result=SimpleNamespace(
            receta=SimpleNamespace(id=11, nombre="Pan base"),
            lineas=[RecetaLinea(receta_id=11, orden=1, nombre_mostrado="Harina")],
            issues=[SimpleNamespace(level="info", message="ok")],
        ),
        save_result=SimpleNamespace(
            receta=SimpleNamespace(id=11, nombre="Pan base"),
            lineas=[RecetaLinea(receta_id=11, orden=1, nombre_mostrado="Harina")],
        ),
    )
    service = RecipeActiveFlowService(recipe_service=fake_recipe)
    payload = _sample_payload()
    lineas = [RecetaLinea(receta_id=7, orden=1, nombre_mostrado="Harina")]

    result = service.save_recipe(payload, lineas, selected_cliente_id="cli-1", recipe_tab_index=0)

    assert result.status == "saved"
    assert result.saved_recipe_id == 11
    assert len(fake_recipe.calculate_calls) == 1
    assert len(fake_recipe.save_calls) == 1
    assert result.issues and result.issues[0].message == "ok"


def test_save_version_strips_comment_and_calls_service() -> None:
    fake_recipe = _FakeRecipeService()
    service = RecipeActiveFlowService(recipe_service=fake_recipe)
    payload = _sample_payload()

    result = service.save_version(payload, [], "  Version 1  ", selected_cliente_id="cli-1", recipe_tab_index=0)

    assert result.status == "version_saved"
    assert len(fake_recipe.version_calls) == 1
    assert fake_recipe.version_calls[0]["comentario"] == "Version 1"


def test_autosave_skips_when_recipe_name_is_empty() -> None:
    fake_recipe = _FakeRecipeService()
    service = RecipeActiveFlowService(recipe_service=fake_recipe)
    payload = _sample_payload(nombre="")

    result = service.autosave_recipe(payload, [], selected_cliente_id="cli-1", recipe_tab_index=0)

    assert result.status == "skipped"
    assert fake_recipe.calculate_calls == []
    assert fake_recipe.save_calls == []

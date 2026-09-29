import os
os.environ.setdefault("QT_QPA_PLATFORM", "windows")
import json
import pytest
from PySide6.QtWidgets import QApplication, QInputDialog
from app.ui.widgets.recipes_page import RecipesPage
from app.models import RecetaLinea
from app.viewmodels import IngredientChoice


@pytest.fixture
def page(monkeypatch):
    app = QApplication.instance() or QApplication([])
    for name in ("_load_customers", "_reload_recipe_list", "_new_recipe", "_schedule_autosave"):
        monkeypatch.setattr(RecipesPage, name, lambda self: None)
    widget = RecipesPage()
    widget._refresh_process_controls(["Masa final", "Frutas"])
    widget.active_process_combo.setCurrentText("Frutas")
    yield widget
    widget.close()


def test_empty_process_survives_build_and_ingredient_insertion(page):
    page._render_lines([RecetaLinea(receta_id=0, nombre_mostrado="Harina", proceso_nombre="Masa final", cantidad_base_g=100)])
    page._build_lines()
    assert page._current_active_process() == "Frutas"
    ingredient = IngredientChoice(tipo_origen="std", ingrediente_id=1, codigo="PASAS", nombre="Pasas", familia="", subfamilia="", precio_kg=1, es_harina=False, es_liquido=False)
    page._set_ingredient_row(page._first_empty_line_row(), ingredient)
    assert page._current_active_process() == "Frutas"
    assert next(line for line in page._build_lines() if line.nombre_mostrado == "Pasas").proceso_nombre == "Frutas"


def test_rename_updates_references_and_process_settings(page, monkeypatch):
    page._render_lines([
        RecetaLinea(receta_id=0, nombre_mostrado="Pasas", proceso_nombre="Frutas", cantidad_base_g=100),
        RecetaLinea(receta_id=0, nombre_mostrado="Proceso: Frutas", proceso_nombre="Masa final", tipo_linea="proceso", tipo_origen="process", proceso_origen_nombre="Frutas", cantidad_base_g=100, cantidad_origen_g=100),
    ])
    page.recipe_escandallo_data["proceso::Frutas::peso_pieza"] = "100"
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("Fruta macerada", True))
    page._rename_process()
    lines = page._build_lines()
    assert lines[0].proceso_nombre == "Fruta macerada"
    assert lines[1].proceso_origen_nombre == "Fruta macerada"
    assert "Frutas" not in page.recipe_process_names
    assert page.recipe_escandallo_data["proceso::Fruta macerada::peso_pieza"] == "100"


def test_move_ingredient_preserves_quantity_and_order_controls(page):
    page._render_lines([RecetaLinea(receta_id=0, nombre_mostrado="Pasas", proceso_nombre="Frutas", cantidad_base_g=125)])
    page._move_ingredient_to_process(0, "Masa final")
    line = page._build_lines()[0]
    assert line.proceso_nombre == "Masa final" and line.cantidad_base_g == 125
    page.active_process_combo.setCurrentText("Frutas")
    page._reorder_process(-1)
    assert page.recipe_process_names == ["Frutas", "Masa final"]
    page._build_lines()
    assert page.recipe_process_names == ["Frutas", "Masa final"]
    payload = page._build_recipe_payload()
    assert json.loads(payload.elaboracion_data["recipe_process_order"]) == ["Frutas", "Masa final"]


def test_renaming_primary_process_preserves_calculated_mass(page, monkeypatch):
    page._render_lines([RecetaLinea(receta_id=0, nombre_mostrado="Harina", proceso_nombre="Masa final", cantidad_base_g=1000, es_harina=True)])
    page.active_process_combo.setCurrentText("Masa final")
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("Stollen terminado", True))
    page._rename_process()
    from app.services.recipe_calculation_service import RecipeCalculationService
    recipe = page._build_recipe_model()
    recipe.masa_final_deseada_g = 0
    recipe.numero_piezas = 0
    result = RecipeCalculationService().calculate(recipe, page._build_lines())
    assert result.receta.masa_total_g == 1000
    assert "Masa final" not in page.recipe_process_names


def test_saved_process_names_and_order_reload_with_empty_process(page, monkeypatch):
    from types import SimpleNamespace
    from app.models import Receta
    recipe = Receta(id=123, nombre="Prueba", parametros_elaboracion_json=json.dumps({"recipe_process_order": json.dumps(["Frutas", "Masa final", "Cobertura"])}))
    monkeypatch.setattr(page.recipe_service, "get_recipe", lambda *args, **kwargs: SimpleNamespace(receta=recipe, lineas=[]))
    page._load_recipe(123)
    assert page.recipe_process_names == ["Frutas", "Masa final", "Cobertura"]

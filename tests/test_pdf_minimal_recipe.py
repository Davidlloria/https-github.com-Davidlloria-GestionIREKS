from __future__ import annotations

import json

import pytest
from pypdf import PdfReader

from app.models import Cliente, Receta, RecetaLinea
from app.services import pdf_service as pdf_service_module
from app.services.pdf_service import PdfService
from app.services.recipe_calculation_service import RecipeCalculationService


def test_minimal_recipe_pdf_includes_recipe_and_optional_escandallo(tmp_path) -> None:
    recipe = Receta(
        cliente_id="cliente-1",
        nombre="Pan mínimo",
        codigo_receta="PAN-1",
        peso_pieza_g=250,
        proceso="Amasar durante 10 minutos.\nFermentar 30 minutos.",
        escandallo_detalle_json=json.dumps({"costes_fijos": "1,20"}),
    )
    lines = [
        RecetaLinea(
            receta_id=1,
            orden=1,
            nombre_mostrado="Harina",
            cantidad_base_g=1000,
            porcentaje_panadero=100,
            precio_kg_snapshot=0.8,
            proceso_nombre="Masa final",
        ),
        RecetaLinea(
            receta_id=1,
            orden=2,
            nombre_mostrado="Prefermento",
            cantidad_base_g=200,
            porcentaje_panadero=20,
            precio_kg_snapshot=0.5,
            proceso_nombre="Poolish",
        ),
    ]
    output_path = tmp_path / "minimo.pdf"
    customer = Cliente(cliente_id="cliente-1", cliente_nombre_comercial="Panadería Norte")

    PdfService()._export_minimal_recipe_to_pdf(
        recipe,
        customer,
        lines,
        output_path,
        include_escandallo=True,
        include_nutrition=True,
    )

    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(output_path)).pages)
    assert output_path.read_bytes().startswith(b"%PDF")
    assert "Pan mínimo" in text
    assert "Panadería Norte" in text
    assert "RECETA" in text
    assert "MASA FINAL" in text
    assert "POOLISH" in text
    assert "PROCESO" in text
    assert "Amasar durante 10 minutos." in text
    assert "ESCANDALLO" in text
    assert "Harina" in text
    assert "TOTAL MASA" in text
    assert "PESO POR PIEZA" in text
    assert "TOTAL PIEZAS" in text
    assert "COSTE UNITARIO" in text
    assert "TOTAL" in text
    assert "VALORES NUTRICIONALES" in text
    assert "INFORMACIÓN NUTRICIONAL" in text


def test_minimal_recipe_pdf_can_hide_baker_percentage(tmp_path) -> None:
    recipe = Receta(cliente_id="cliente-1", nombre="Pan", codigo_receta="PAN-1")
    lines = [
        RecetaLinea(
            receta_id=1,
            orden=1,
            nombre_mostrado="Harina",
            cantidad_base_g=1000,
            porcentaje_panadero=100,
            proceso_nombre="Masa final",
        )
    ]
    output_path = tmp_path / "minimo-sin-porcentaje.pdf"

    PdfService()._export_minimal_recipe_to_pdf(
        recipe,
        None,
        lines,
        output_path,
        include_escandallo=False,
        include_baker_percentage=False,
    )

    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(output_path)).pages)
    assert "CANTIDAD" in text
    assert "100,00 %" not in text


@pytest.mark.parametrize("layout_mode", ["minimal", "extended"])
def test_recipe_pdf_preserves_base_formula_for_cost_and_unit_price(
    tmp_path,
    monkeypatch,
    layout_mode: str,
) -> None:
    recipe = Receta(
        cliente_id="cliente-1",
        nombre="Receta escalada",
        codigo_receta="ESC-1",
        masa_final_deseada_g=2000,
        peso_pieza_g=300,
        numero_piezas=8,
    )
    lines = [
        RecetaLinea(
            receta_id=1,
            orden=1,
            nombre_mostrado="Harina",
            es_harina=True,
            cantidad_base_g=1000,
            precio_kg_snapshot=1.0,
        ),
        RecetaLinea(
            receta_id=1,
            orden=2,
            nombre_mostrado="Agua",
            es_liquido=True,
            cantidad_base_g=650,
            precio_kg_snapshot=0.2,
        ),
        RecetaLinea(
            receta_id=1,
            orden=3,
            nombre_mostrado="Sal",
            cantidad_base_g=20,
            precio_kg_snapshot=0.9,
        ),
    ]
    customer = Cliente(cliente_id="cliente-1", cliente_nombre_comercial="Cliente prueba")
    service = PdfService()
    monkeypatch.setattr(service, "_load_recipe_data", lambda _recipe_id: (recipe, customer, lines))

    class _RecipeServiceStub:
        def calculate(self, target_recipe, target_lines, *, sync_categories=False):
            return RecipeCalculationService().calculate(target_recipe, target_lines)

    monkeypatch.setattr(pdf_service_module, "RecipeService", _RecipeServiceStub)
    output_path = tmp_path / f"receta-escalada-{layout_mode}.pdf"

    service.export_recipe_to_pdf(
        1,
        output_path,
        layout_mode=layout_mode,
        include_escandallo=True,
    )

    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(output_path)).pages)
    assert "1.670,00 g" in text
    assert "2.000,00 g" not in text
    assert "1,15" in text
    assert "0,14" in text

import pytest

from app.models import Receta, RecetaLinea
from app.services.recipe_calculation_service import RecipeCalculationService
from app.services.recipe_scaling_service import RecipeScalingService


def test_scale_by_flour_updates_totals_and_pieces() -> None:
    receta = Receta(
        cliente_id="cliente-test",
        nombre="Test",
        codigo_receta="T-1",
        peso_pieza_g=250,
        numero_piezas=6,
        masa_final_deseada_g=1670,
    )
    lineas = [
        RecetaLinea(receta_id=1, orden=1, nombre_mostrado="Harina", es_harina=True, cantidad_base_g=1000),
        RecetaLinea(receta_id=1, orden=2, nombre_mostrado="Agua", es_liquido=True, cantidad_base_g=650),
        RecetaLinea(receta_id=1, orden=3, nombre_mostrado="Sal", cantidad_base_g=20),
    ]

    result = RecipeScalingService().scale(receta, lineas, "flour", 1500)

    assert round(result.factor, 4) == 1.5
    assert round(sum(line.cantidad_base_g for line in result.lineas), 2) == 2505.00
    assert round(result.receta.masa_final_deseada_g, 2) == 2505.00
    assert result.receta.numero_piezas == 10


def test_scale_by_total_dough_uses_total_mass() -> None:
    receta = Receta(
        cliente_id="cliente-test",
        nombre="Test",
        codigo_receta="T-2",
        peso_pieza_g=200,
        numero_piezas=8,
        masa_final_deseada_g=1600,
    )
    lineas = [
        RecetaLinea(receta_id=1, orden=1, nombre_mostrado="Harina", es_harina=True, cantidad_base_g=1000),
        RecetaLinea(receta_id=1, orden=2, nombre_mostrado="Agua", es_liquido=True, cantidad_base_g=600),
    ]

    result = RecipeScalingService().scale(receta, lineas, "dough", 2400)

    assert round(result.factor, 4) == 1.5
    assert round(result.lineas[0].cantidad_base_g, 2) == 1500.00
    assert round(result.lineas[1].cantidad_base_g, 2) == 900.00
    assert round(result.receta.masa_final_deseada_g, 2) == 2400.00
    assert result.receta.numero_piezas == 12


def test_scale_by_pieces_keeps_piece_weight_relation() -> None:
    receta = Receta(
        cliente_id="cliente-test",
        nombre="Test",
        codigo_receta="T-3",
        peso_pieza_g=250,
        numero_piezas=8,
        masa_final_deseada_g=2000,
    )
    lineas = [
        RecetaLinea(receta_id=1, orden=1, nombre_mostrado="Harina", es_harina=True, cantidad_base_g=1200),
        RecetaLinea(receta_id=1, orden=2, nombre_mostrado="Agua", es_liquido=True, cantidad_base_g=760),
        RecetaLinea(receta_id=1, orden=3, nombre_mostrado="Sal", cantidad_base_g=40),
    ]

    result = RecipeScalingService().scale(receta, lineas, "pieces", 10)

    assert round(result.factor, 4) == 1.25
    assert result.receta.numero_piezas == 10
    assert round(result.receta.masa_final_deseada_g, 2) == 2500.00


def test_scale_updates_process_source_quantity() -> None:
    receta = Receta(
        cliente_id="cliente-test",
        nombre="Test procesos",
        codigo_receta="T-4",
        numero_piezas=1,
        masa_final_deseada_g=600,
    )
    lineas = [
        RecetaLinea(
            receta_id=1,
            orden=1,
            tipo_linea="proceso",
            nombre_mostrado="Proceso: Primera Masa",
            cantidad_base_g=300,
            cantidad_origen_g=300,
            proceso_nombre="Masa final",
            proceso_origen_nombre="Primera Masa",
        ),
        RecetaLinea(receta_id=1, orden=2, nombre_mostrado="Mantequilla", cantidad_base_g=300),
    ]

    result = RecipeScalingService().scale(receta, lineas, "dough", 1200)

    assert result.lineas[0].cantidad_base_g == 600
    assert result.lineas[0].cantidad_origen_g == 600


@pytest.mark.parametrize("mode,target", [("flour", 151.5), ("dough", 228), ("pieces", 3)])
def test_all_scale_modes_round_to_whole_grams_and_recalculate_total(mode, target):
    receta = Receta(nombre="Redondeo", numero_piezas=2, peso_pieza_g=76)
    lineas = [
        RecetaLinea(receta_id=1, nombre_mostrado="Harina", es_harina=True, cantidad_base_g=101),
        RecetaLinea(receta_id=1, nombre_mostrado="Agua", cantidad_base_g=50.2),
        RecetaLinea(receta_id=1, nombre_mostrado="Sal", cantidad_base_g=0.8),
    ]
    original = [line.model_dump() for line in lineas]
    result = RecipeScalingService().scale(receta, lineas, mode, target)
    assert [line.cantidad_base_g for line in result.lineas] == [152, 75, 1]
    assert result.receta.masa_final_deseada_g == 228
    calculated = RecipeCalculationService().calculate(result.receta, result.lineas)
    assert [line.cantidad_base_g for line in calculated.lineas] == [152, 75, 1]
    assert [line.model_dump() for line in lineas] == original


def test_rounding_updates_total_and_process_reference_consistently():
    receta = Receta(nombre="Redondeo procesos", numero_piezas=2)
    lineas = [
        RecetaLinea(receta_id=1, nombre_mostrado="Proceso: Base", tipo_linea="proceso", cantidad_base_g=101, cantidad_origen_g=101),
        RecetaLinea(receta_id=1, nombre_mostrado="Mantequilla", cantidad_base_g=101),
    ]
    result = RecipeScalingService().scale(receta, lineas, "dough", 303)
    assert [line.cantidad_base_g for line in result.lineas] == [152, 152]
    assert result.lineas[0].cantidad_origen_g == 152
    assert result.receta.masa_final_deseada_g == 304

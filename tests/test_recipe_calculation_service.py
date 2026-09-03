import pytest

from app.models import Receta, RecetaLinea
from app.services import RecipeCalculationService


def test_calculation_service_basic() -> None:
    receta = Receta(cliente_id="cliente-test", nombre="Test", codigo_receta="T-1", numero_piezas=10, masa_final_deseada_g=2000)
    lineas = [
        RecetaLinea(receta_id=1, orden=1, nombre_mostrado="Harina", es_harina=True, cantidad_base_g=1000, precio_kg_snapshot=1.0),
        RecetaLinea(receta_id=1, orden=2, nombre_mostrado="Agua", es_liquido=True, cantidad_base_g=650, precio_kg_snapshot=0.2),
        RecetaLinea(receta_id=1, orden=3, nombre_mostrado="Sal", cantidad_base_g=20, precio_kg_snapshot=0.9),
    ]

    result = RecipeCalculationService().calculate(receta, lineas)

    assert result.receta.total_harinas_g == 1000
    assert result.receta.total_liquidos_g == 650
    assert result.receta.hidratacion_pct == 65
    assert result.receta.total_porcentaje_panadero > 0


def test_calculation_resolves_source_process_even_when_final_mass_is_first() -> None:
    receta = Receta(cliente_id="cliente-test", nombre="Pan", codigo_receta="P-1", numero_piezas=1)
    lineas = [
        RecetaLinea(
            receta_id=1,
            orden=1,
            nombre_mostrado="Proceso: Poolish",
            tipo_linea="proceso",
            proceso_nombre="Masa final",
            proceso_origen_nombre="Poolish",
            cantidad_base_g=300,
            cantidad_origen_g=300,
        ),
        RecetaLinea(
            receta_id=1,
            orden=2,
            nombre_mostrado="Sal",
            proceso_nombre="Masa final",
            cantidad_base_g=10,
            precio_kg_snapshot=1,
        ),
        RecetaLinea(
            receta_id=1,
            orden=3,
            nombre_mostrado="Harina",
            es_harina=True,
            proceso_nombre="Poolish",
            cantidad_base_g=200,
            precio_kg_snapshot=2,
        ),
        RecetaLinea(
            receta_id=1,
            orden=4,
            nombre_mostrado="Agua",
            es_liquido=True,
            proceso_nombre="Poolish",
            cantidad_base_g=200,
            precio_kg_snapshot=0.5,
        ),
    ]

    result = RecipeCalculationService().calculate(receta, lineas)

    assert result.receta.masa_total_g == 310
    assert result.receta.total_harinas_g == 150
    assert result.receta.total_liquidos_g == 150
    assert result.receta.coste_total == 0.385


def test_process_cost_sheet_keeps_source_process_as_valued_line() -> None:
    lineas = [
        RecetaLinea(
            receta_id=1,
            orden=1,
            nombre_mostrado="Proceso: Poolish",
            tipo_linea="proceso",
            proceso_nombre="Masa final",
            proceso_origen_nombre="Poolish",
            cantidad_base_g=300,
        ),
        RecetaLinea(
            receta_id=1,
            orden=2,
            nombre_mostrado="Sal",
            proceso_nombre="Masa final",
            cantidad_base_g=10,
            precio_kg_snapshot=1,
        ),
        RecetaLinea(
            receta_id=1,
            orden=3,
            nombre_mostrado="Harina",
            es_harina=True,
            proceso_nombre="Poolish",
            cantidad_base_g=200,
            precio_kg_snapshot=2,
        ),
        RecetaLinea(
            receta_id=1,
            orden=4,
            nombre_mostrado="Agua",
            es_liquido=True,
            proceso_nombre="Poolish",
            cantidad_base_g=200,
            precio_kg_snapshot=0.5,
        ),
    ]

    cost_sheet = RecipeCalculationService().build_process_cost_sheet(lineas)

    assert [(line.nombre_mostrado, line.cantidad_base_g) for line in cost_sheet] == [
        ("Proceso: Poolish", 300),
        ("Sal", 10),
    ]
    assert cost_sheet[0].precio_kg_efectivo_snapshot == 1.25
    assert cost_sheet[0].coste_linea == 0.375
    assert sum(line.coste_linea for line in cost_sheet) == 0.385


def test_process_cost_sheet_filters_each_process() -> None:
    lineas = [
        RecetaLinea(
            receta_id=1,
            orden=1,
            nombre_mostrado="Harina",
            es_harina=True,
            proceso_nombre="Primera Masa",
            cantidad_base_g=2175,
            precio_kg_snapshot=4.8,
        ),
        RecetaLinea(
            receta_id=1,
            orden=2,
            nombre_mostrado="Yema",
            proceso_nombre="Primera Masa",
            cantidad_base_g=370,
        ),
        RecetaLinea(
            receta_id=1,
            orden=3,
            nombre_mostrado="Levadura",
            proceso_nombre="Primera Masa",
            cantidad_base_g=25,
        ),
        RecetaLinea(
            receta_id=1,
            orden=4,
            nombre_mostrado="Mantequilla",
            proceso_nombre="Primera Masa",
            cantidad_base_g=540,
        ),
        RecetaLinea(
            receta_id=1,
            orden=5,
            nombre_mostrado="Agua",
            es_liquido=True,
            proceso_nombre="Primera Masa",
            cantidad_base_g=1000,
            precio_kg_snapshot=1,
        ),
        RecetaLinea(
            receta_id=1,
            orden=6,
            nombre_mostrado="Proceso: Primera Masa",
            tipo_linea="proceso",
            proceso_nombre="Masa final",
            proceso_origen_nombre="Primera Masa",
            cantidad_base_g=4110,
        ),
    ]
    service = RecipeCalculationService()

    first_mass = service.build_process_cost_sheet(lineas, "Primera Masa")
    final_mass = service.build_process_cost_sheet(lineas, "Masa final")

    assert [line.nombre_mostrado for line in first_mass] == [
        "Harina",
        "Yema",
        "Levadura",
        "Mantequilla",
        "Agua",
    ]
    assert [line.nombre_mostrado for line in final_mass] == ["Proceso: Primera Masa"]
    assert final_mass[0].precio_kg_efectivo_snapshot == pytest.approx(
        sum(line.coste_linea for line in first_mass) * 1000 / 4110
    )
    assert final_mass[0].coste_linea == pytest.approx(sum(line.coste_linea for line in first_mass))


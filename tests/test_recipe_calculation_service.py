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


def test_resolve_process_ingredients_returns_final_mass_cost_sheet() -> None:
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

    resolved = RecipeCalculationService().resolve_process_ingredients(lineas)

    assert [(line.nombre_mostrado, line.cantidad_base_g) for line in resolved] == [
        ("Harina", 150),
        ("Agua", 150),
        ("Sal", 10),
    ]
    assert sum(line.coste_linea for line in resolved) == 0.385


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


from app.models import Receta, RecetaLinea
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

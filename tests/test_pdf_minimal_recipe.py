from __future__ import annotations

import json

from pypdf import PdfReader

from app.models import Receta, RecetaLinea
from app.services.pdf_service import PdfService


def test_minimal_recipe_pdf_includes_recipe_and_optional_escandallo(tmp_path) -> None:
    recipe = Receta(
        cliente_id="cliente-1",
        nombre="Pan mínimo",
        codigo_receta="PAN-1",
        peso_pieza_g=250,
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
        )
    ]
    output_path = tmp_path / "minimo.pdf"

    PdfService()._export_minimal_recipe_to_pdf(recipe, lines, output_path, include_escandallo=True)

    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(output_path)).pages)
    assert output_path.read_bytes().startswith(b"%PDF")
    assert "Pan mínimo" in text
    assert "RECETA" in text
    assert "ESCANDALLO" in text
    assert "Harina" in text
    assert "TOTAL MASA" in text
    assert "PESO POR PIEZA" in text
    assert "TOTAL PIEZAS" in text
    assert "COSTE UNITARIO" in text

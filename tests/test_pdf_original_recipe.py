from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest
from PIL import Image
from pypdf import PdfReader

from app.models import Receta, RecetaLinea
from app.services import pdf_service as pdf_service_module
from app.services import recipe_image_storage_service
from app.services.pdf_service import PdfService


def _line(name, quantity, process="Masa final", **kwargs):
    return RecetaLinea(receta_id=1, nombre_mostrado=name, cantidad_base_g=quantity, proceso_nombre=process, **kwargs)


def _text(reader):
    return "\n".join(page.extract_text() or "" for page in reader.pages)


@pytest.mark.parametrize("dreidoppel", [False, True])
def test_original_export_uses_reference_artwork_base_quantities_and_no_cost_calculation(tmp_path, monkeypatch, dreidoppel):
    recipe = Receta(
        nombre="Baguette con MASA MADRE PIE", codigo_receta="BAG",
        masa_final_deseada_g=20000, proceso="1. Amasar hasta conseguir una masa fina.\n• Cocer a 220 °C.\n1.000 g de harina por masa.",
    )
    lines = [
        _line("Harina", 5000, cantidad_calculada_g=10000),
        _line("MASA MADRE PIE", 100), _line("Sal", 100), _line("Levadura", 100), _line("Agua", 3250),
    ]
    before = [line.model_dump() for line in lines]
    recipe_before = recipe.model_dump()
    service = PdfService()
    monkeypatch.setattr(service, "_load_recipe_data", lambda _id: (recipe, None, lines))

    def forbidden_calculation():
        pytest.fail("Original must not call cost/category services or write recipe data")

    monkeypatch.setattr(pdf_service_module, "RecipeService", forbidden_calculation)
    path = tmp_path / "original.pdf"
    service.export_recipe_to_pdf(
        1, path, layout_mode="original", include_dreidoppel=dreidoppel,
        include_escandallo=True, include_nutrition=True, include_baker_percentage=True,
    )
    reader = PdfReader(path)
    text = _text(reader)
    assert len(reader.pages) == 1
    assert "Baguette\ncon MASA MADRE PIE" in text
    assert "5,000 kg" in text and "8,550 kg" in text
    assert "10,000 kg" not in text
    assert "Amasar hasta conseguir una masa fina." in text
    assert "Cocer a 220 °C." in text
    assert "1. Amasar" not in text
    assert "1.000 g de harina por masa." in text
    assert not any(label in text for label in ["ESCANDALLO", "NUTRICIONALES", "%", "Masa final"])
    artwork = list(reader.pages[0].images)
    assert len(artwork) == 2
    templates = Path(pdf_service_module.__file__).resolve().parents[2] / "assets/templates/recetas"
    expected = Image.open(templates / ("original_cabecera_dreidoppel.png" if dreidoppel else "original_cabecera.png"))
    assert any(item.image.convert("RGB").tobytes() == expected.convert("RGB").tobytes() for item in artwork)
    assert [line.model_dump() for line in lines] == before
    assert recipe.model_dump() == recipe_before


def test_original_groups_preparations_preserves_instructions_and_corrects_totals(tmp_path):
    recipe = Receta(
        nombre="Plancha de chocolate con mousse de chocolate con MELLA CHOCO MUFFIN y DREIDOPPEL",
        codigo_receta="CHOCO", proceso="[Mousse de chocolate]\nMezclar el agua y el fond.\n"
        "[Masa final]\nMezclar la masa.\nRellenar y decorar.\n[Decoración]\nTerminar con virutas.",
    )
    lines = [
        _line("MELLA CHOCO MUFFIN", 1000, "Masa"), _line("Aceite", 360, "Masa"),
        _line("Huevo", 350, "Masa"), _line("Agua", 220, "Masa"),
        _line("Agua", 250, "Mousse de chocolate"), _line("FOND ROYAL CHOCOLATE", 200, "Mousse de chocolate"),
        _line("Nata semimontada", 1000, "Mousse de chocolate", notas="sin azúcar"),
    ]
    path = tmp_path / "preparaciones.pdf"
    PdfService()._export_original_recipe_to_pdf(recipe, lines, path, include_dreidoppel=True)
    text = _text(PdfReader(path))
    assert "con mousse de chocolate con MELLA CHOCO MUFFIN" in text
    assert "1,930 kg" in text and "1,450 kg" in text and "0,725 kg" not in text
    assert "Nata semimontada (sin azúcar)" in text
    assert text.index("Mezclar el agua") < text.index("Mezclar la masa")
    assert "Terminar con virutas." in text


@pytest.mark.parametrize("name", ["Pan sin subtítulo", "Pan CON malta con semillas", "Pan concha"])
def test_original_title_handles_missing_subtitle_case_and_word_boundaries(tmp_path, name):
    recipe = Receta(nombre=name, codigo_receta="PAN")
    path = tmp_path / "titulo.pdf"
    PdfService()._export_original_recipe_to_pdf(recipe, [_line("Harina", 1000)], path)
    text = _text(PdfReader(path))
    if " CON " in name:
        assert "Pan\nCON malta con semillas" in text
    else:
        assert name in text


@pytest.mark.parametrize("legacy_gallery", [False, True])
def test_original_includes_only_selected_recipe_image_with_its_proportions(tmp_path, monkeypatch, legacy_gallery):
    monkeypatch.setattr(recipe_image_storage_service, "DATA_DIR", tmp_path)
    for name, color, size in [("principal.png", "red", (100, 200)), ("elegida.png", "blue", (400, 100))]:
        Image.new("RGB", size, color).save(tmp_path / name)
    gallery = [{"path": "principal.png", "is_main": True}, {"path": "elegida.png"}]
    payload = {"__images_gallery_json": json.dumps(gallery)} if legacy_gallery else {"images_gallery": gallery}
    recipe = Receta(nombre="Pan", codigo_receta="PAN", parametros_elaboracion_json=json.dumps(payload))
    path = tmp_path / "imagen.pdf"
    PdfService()._export_original_recipe_to_pdf(
        recipe, [_line("Harina", 1000)], path, include_images=True, selected_image_path="elegida.png",
    )
    reader = PdfReader(path)
    images = list(reader.pages[0].images)
    assert len(images) == 3
    assert any(image.image.size == (400, 100) for image in images)
    assert not any(image.image.size == (100, 200) for image in images)
    with fitz.open(path) as document:
        page = document[0]
        photo = next(item for item in page.get_images() if item[2:4] == (400, 100))
        rectangle = page.get_image_rects(photo[0])[0]
        assert rectangle.width / rectangle.height == pytest.approx(4)


@pytest.mark.parametrize("selected", ["", "fuera.png", "ausente.png", "corrupta.png"])
def test_original_rejects_missing_invalid_or_unregistered_image(tmp_path, monkeypatch, selected):
    monkeypatch.setattr(recipe_image_storage_service, "DATA_DIR", tmp_path)
    Image.new("RGB", (10, 10), "red").save(tmp_path / "fuera.png")
    (tmp_path / "corrupta.png").write_text("invalid")
    recipe = Receta(nombre="Pan", codigo_receta="PAN", parametros_elaboracion_json=json.dumps({
        "images_gallery": [{"path": "ausente.png"}, {"path": "corrupta.png"}],
    }))
    path = tmp_path / "invalid.pdf"
    with pytest.raises(ValueError, match="imagen"):
        PdfService()._export_original_recipe_to_pdf(
            recipe, [], path, include_images=True, selected_image_path=selected,
        )
    assert not path.exists()


def test_original_long_recipe_paginates_and_repeats_artwork_without_losing_content(tmp_path):
    recipe = Receta(
        nombre="Receta larga con ingredientes de prueba", codigo_receta="LARGA",
        proceso="\n".join(f"Paso {i}: amasar y dejar reposar." for i in range(1, 91)),
    )
    lines = [_line(f"Ingrediente {i:03d}", 1000) for i in range(1, 101)]
    path = tmp_path / "larga.pdf"
    PdfService()._export_original_recipe_to_pdf(recipe, lines, path)
    reader = PdfReader(path)
    text = _text(reader)
    assert len(reader.pages) > 2
    assert all(len(list(page.images)) == 2 for page in reader.pages)
    assert all(text.count(f"Ingrediente {i:03d}") == 1 for i in range(1, 101))
    assert "100,000 kg" in text
    assert "Paso 90:" in text
    # Verify content remains between the repeated header and footer.
    with fitz.open(path) as document:
        for page in document:
            for block in page.get_text("blocks"):
                assert block[1] >= 100
                assert block[3] < page.rect.height - 42

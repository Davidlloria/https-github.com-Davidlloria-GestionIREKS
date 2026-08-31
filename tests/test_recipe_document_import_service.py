from __future__ import annotations

from app.services.document_content_index_service import DocumentContentSearchResult
from app.services.recipe_document_import_service import RecipeDocumentImportService
from app.viewmodels import IngredientChoice


def _ingredient(name: str, *, source: str = "std") -> IngredientChoice:
    return IngredientChoice(
        tipo_origen=source,
        ingrediente_id=7,
        codigo=name.upper().replace(" ", "-"),
        nombre=name,
        familia="",
        subfamilia="",
        precio_kg=0.0,
        es_harina="harina" in name.casefold(),
        es_liquido=name.casefold() == "agua",
    )


def test_search_is_restricted_to_technical_recipe_categories() -> None:
    calls = []

    class Content:
        def search(self, query, **filters):
            calls.append((query, filters))
            return []

    service = RecipeDocumentImportService(content_service=Content())  # type: ignore[arg-type]

    assert service.search("espelta") == []
    assert calls == [
        (
            "espelta",
            {"area": "TECNICO", "category_prefix": "RECETAS", "limit": 50},
        )
    ]


def test_parse_page_builds_processes_quantities_matches_and_provenance() -> None:
    ingredients = {
        "rex espelta miel": [_ingredient("REX ESPELTA MIEL", source="ireks")],
        "agua": [_ingredient("Agua")],
        "crema pastelera": [_ingredient("Crema pastelera")],
    }
    service = RecipeDocumentImportService(
        ingredient_search=lambda term: ingredients.get(term.casefold(), [])
    )
    text = """Pan de espelta
con REX ESPELTA MIEL
Receta para 20 unidades
Masa
REX ESPELTA MIEL
10,000 kg
Agua (aprox.)
5,200 kg
Total
15,200 kg
Relleno
Crema pastelera
0,500 kg
Decoración
Azúcar glas
C/S
Proceso de elaboración
Mezclar los ingredientes.
Fermentar 60 minutos.
"""

    draft = service.parse_page(
        text,
        document_id="doc-1",
        document_name="pan.pdf",
        relative_path="TECNICO/RECETAS/PAN/pan.pdf",
        page_number=3,
    )

    assert draft.recipe_name == "Pan de espelta"
    assert draft.number_of_pieces == 20
    assert draft.process_text == "Mezclar los ingredientes.\nFermentar 60 minutos."
    assert draft.document_id == "doc-1"
    assert [(line.source_name, line.quantity_g, line.process_name) for line in draft.lines] == [
        ("REX ESPELTA MIEL", 10_000.0, "Masa final"),
        ("Agua (aprox.)", 5_200.0, "Masa final"),
        ("Crema pastelera", 500.0, "Relleno"),
        ("Azúcar glas", 0.0, "Decoración"),
    ]
    assert draft.lines[0].matched_ingredient is not None
    assert draft.lines[1].matched_ingredient is not None
    assert draft.lines[-1].matched_ingredient is None
    assert "C/S" in draft.lines[-1].notes
    assert draft.unresolved_count == 1


def test_build_draft_uses_selected_page_text() -> None:
    result = DocumentContentSearchResult(
        document_id="doc-9",
        name="formula.pdf",
        relative_path="TECNICO/RECETAS/formula.pdf",
        area="TECNICO",
        category="RECETAS",
        page_number=2,
        fragment="",
        score=0.0,
    )

    class Content:
        def get_page_text(self, document_id, page_number):
            assert (document_id, page_number) == ("doc-9", 4)
            return "Formula elegida\nHarina\n1,000 kg"

    service = RecipeDocumentImportService(content_service=Content())  # type: ignore[arg-type]

    draft = service.build_draft(result, page_number=4)

    assert draft.recipe_name == "Formula elegida"
    assert draft.page_number == 4
    assert draft.lines[0].quantity_g == 1000.0


def test_process_marker_tolerates_replacement_characters_from_pdf_fonts() -> None:
    service = RecipeDocumentImportService()

    draft = service.parse_page(
        "Formula\nHarina\n1,000 kg\nProceso de elaboraci�n\nAmasar cinco minutos.",
        document_id="doc-font",
        document_name="formula.pdf",
        relative_path="TECNICO/RECETAS/formula.pdf",
        page_number=1,
    )

    assert draft.process_text == "Amasar cinco minutos."

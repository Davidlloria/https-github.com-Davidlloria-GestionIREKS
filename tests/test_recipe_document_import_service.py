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
    assert draft.process_text == "1. Mezclar los ingredientes.\n2. Fermentar 60 minutos."
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
            assert document_id == "doc-9" and page_number in (4, 5)
            return "Formula elegida\nHarina\n1,000 kg" if page_number == 4 else None

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

    assert draft.process_text == "1. Amasar cinco minutos."


def test_process_bullets_join_wrapped_lines_and_number_each_step() -> None:
    service = RecipeDocumentImportService()

    draft = service.parse_page(
        "Formula\nHarina\n1,000 kg\nProceso de elaboración\n•\nAmasar hasta conseguir\nuna masa fina.\n•\nFermentar 60 minutos.",
        document_id="doc-process",
        document_name="formula.pdf",
        relative_path="TECNICO/RECETAS/formula.pdf",
        page_number=1,
    )

    assert draft.process_text == (
        "1. Amasar hasta conseguir una masa fina.\n"
        "2. Fermentar 60 minutos."
    )


def test_raw_material_search_and_manual_match_only_use_standard_ingredients() -> None:
    raw_material = _ingredient("Levadura fresca")
    ireks_product = _ingredient("AROMA LEVADURA", source="ireks")
    service = RecipeDocumentImportService(
        ingredient_search=lambda _term: [ireks_product, raw_material]
    )
    draft = service.parse_page(
        "Formula\nLevadura\n0,300 kg",
        document_id="doc-raw",
        document_name="formula.pdf",
        relative_path="TECNICO/RECETAS/formula.pdf",
        page_number=1,
    )

    assert service.search_raw_materials("levadura") == [raw_material]
    assert draft.unresolved_count == 1

    resolved = service.apply_raw_material_match(draft, 0, raw_material)

    assert resolved.unresolved_count == 0
    assert resolved.lines[0].matched_ingredient == raw_material
    assert "Revisar asociación" not in resolved.lines[0].notes
    assert not any("revisión manual" in warning for warning in resolved.warnings)


def test_browse_documents_limits_paths_to_recipe_pdfs():
    from types import SimpleNamespace
    calls = []
    class Library:
        def list_documents(self, **kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(document_id=str(i), name=path.split("/")[-1], relative_path=path,
                                    area="TECNICO", category="RECETAS")
                    for i, path in enumerate(("TECNICO/RECETAS/Pan/pan.pdf", "TECNICO/RECETARIOS/otro.pdf",
                                              "TECNICO/RECETAS/raiz.pdf"))]
    service = RecipeDocumentImportService(library_service=Library(), content_service=object())
    rows = service.browse_documents()
    assert [row.name for row in rows] == ["pan.pdf", "raiz.pdf"]
    assert all(row.page_number == 1 for row in rows)
    assert calls == [dict(area="TECNICO", extension=".pdf", active=True)]


def test_document_without_indexed_text_has_explanatory_warning():
    class Content:
        def get_page_text(self, *args):
            return None
    service = RecipeDocumentImportService(content_service=Content())
    result = DocumentContentSearchResult("id", "pan.pdf", "TECNICO/RECETAS/pan.pdf", "TECNICO", "RECETAS", 1, "", 0)
    draft = service.build_draft(result)
    assert not draft.lines
    assert any("no tiene texto indexado" in warning for warning in draft.warnings)


def test_refresh_discovers_new_modified_and_removed_recipe_pdfs(tmp_path, monkeypatch):
    import fitz
    import os
    from app.services.document_library_service import DocumentLibraryService
    from app.services.document_content_index_service import DocumentContentIndexService
    root = tmp_path / "documents"
    folder = root / "TECNICO" / "RECETAS" / "Pan"
    folder.mkdir(parents=True)
    library = DocumentLibraryService(root, tmp_path / "catalog.sqlite")
    content = DocumentContentIndexService(library)
    service = RecipeDocumentImportService(library_service=library, content_service=content)
    assert service.refresh_documents() == ""
    def pdf(path, text):
        document = fitz.open()
        document.new_page().insert_text((72, 72), text)
        document.save(path)
        document.close()
    path = folder / "nueva.pdf"
    pdf(path, "Formula centenoespecial")
    outside = root / "TECNICO" / "MANUALES"
    outside.mkdir()
    pdf(outside / "manual.pdf", "manualfuera")
    assert service.refresh_documents() == ""
    assert len(service.search("centenoespecial")) == 1
    assert [row.name for row in service.browse_documents()] == ["nueva.pdf"]
    assert content.search("manualfuera") == []
    original = content._extract_candidate
    monkeypatch.setattr(content, "_extract_candidate", lambda _: (_ for _ in ()).throw(AssertionError("Unchanged file reindexed")))
    service.refresh_documents()
    monkeypatch.setattr(content, "_extract_candidate", original)
    timestamp = path.stat().st_mtime_ns
    path.unlink()
    pdf(path, "Formula espeltanueva")
    os.utime(path, ns=(timestamp + 2000000000, timestamp + 2000000000))
    service.refresh_documents()
    assert service.search("centenoespecial") == []
    assert len(service.search("espeltanueva")) == 1
    path.unlink()
    service.refresh_documents()
    assert service.browse_documents() == []
    assert service.search("espeltanueva") == []


def test_stollen_preparations_and_final_assembly_are_separate():
    service = RecipeDocumentImportService()
    draft = service.parse_page(
        "Stollen\ncon MELLA BRIOCHE y DREIDOPPEL\nMezcla de frutas\nPasas sultanas\n2,000 kg\n"
        "ORANGEAT\n0,500 kg\nTotal\n2,500 kg\nReposo: de un día para otro.\n"
        "Masa\nMELLA BRIOCHE\n4,000 kg\nAgua\n1,500 kg\nTotal\n5,500 kg\n"
        "Amasado: 2 + 10 minutos.\nMasa\n5,500 kg\nMezcla de frutas\n2,500 kg\nTotal\n8,000 kg",
        document_id="stollen", document_name="Stollen.pdf", relative_path="Stollen.pdf", page_number=1,
    )
    assert [line.process_name for line in draft.lines] == ["Mezcla de frutas"] * 2 + ["Masa"] * 2 + ["Masa final"] * 2
    assert [line.source_process for line in draft.lines[-2:]] == ["Masa", "Mezcla de frutas"]
    assert all(line.is_resolved for line in draft.lines[-2:])
    assert draft.unresolved_count == 4


def test_draft_includes_elaboration_from_next_page_without_changing_ingredients():
    class Content:
        def get_page_text(self, document_id, page):
            return {1: "Stollen\nMasa\nHarina\n1,000 kg", 2: "Proceso de elaboración\n•\nAmasar todos los ingredientes.\n•\nHornear a 190 grados."}.get(page)
    service = RecipeDocumentImportService(content_service=Content())
    result = DocumentContentSearchResult("id", "Stollen.pdf", "Stollen.pdf", "TECNICO", "RECETAS", 1, "", 0)
    draft = service.build_draft(result)
    assert len(draft.lines) == 1 and draft.lines[0].quantity_g == 1000
    assert draft.process_text == "1. Amasar todos los ingredientes.\n2. Hornear a 190 grados."
    assert draft.page_number == 1
    assert any("página 2" in warning for warning in draft.warnings)


def test_draft_does_not_take_elaboration_from_a_different_recipe():
    class Content:
        def get_page_text(self, document_id, page):
            return {1: "Stollen\nMasa\nHarina\n1,000 kg", 2: "Otra receta\nProceso de elaboración\nAmasar."}.get(page)
    service = RecipeDocumentImportService(content_service=Content())
    result = DocumentContentSearchResult("id", "Recetario.pdf", "Recetario.pdf", "TECNICO", "RECETAS", 1, "", 0)
    assert service.build_draft(result).process_text == ""

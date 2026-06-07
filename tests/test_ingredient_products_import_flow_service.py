from __future__ import annotations

from pathlib import Path

from app.services.ingredient_products_import_flow_service import (
    IngredientProductsImportFlowService,
)


class _FakeIngredientService:
    def __init__(self, result: tuple[int, list[str]] | None = None, *, exc: Exception | None = None) -> None:
        self.result = result or (0, [])
        self.exc = exc
        self.calls: list[tuple[str, list[dict], dict[str, list[str]]]] = []

    def import_products(self, file_path: str, schema: list[dict], aliases: dict[str, list[str]]) -> tuple[int, list[str]]:
        self.calls.append((file_path, schema, aliases))
        if self.exc is not None:
            raise self.exc
        return self.result


def test_import_products_success_uses_schema_and_aliases(tmp_path: Path) -> None:
    file_path = tmp_path / "productos.xlsx"
    file_path.write_text("", encoding="utf-8")
    fake = _FakeIngredientService(result=(3, []))

    result = IngredientProductsImportFlowService(fake).import_products(file_path)

    assert result.status == "success"
    assert result.imported == 3
    assert result.errors == []
    assert result.preview == ""
    assert len(fake.calls) == 1
    called_path, schema, aliases = fake.calls[0]
    assert called_path == str(file_path)
    assert schema[0]["name"] == "almacen_id"
    assert schema[-1]["name"] == "articulo_status_en_lista"
    assert aliases["articulo_id"] == ["articulo", "articulo_id", "id_articulo"]
    assert aliases["articulo_status_activo"] == ["status_activo", "activo_status", "activo_producto", "estado", "habilitado"]


def test_import_products_warning_builds_truncated_preview(tmp_path: Path) -> None:
    file_path = tmp_path / "productos.csv"
    file_path.write_text("", encoding="utf-8")
    errors = [f"Fila {idx}: error" for idx in range(2, 12)]
    fake = _FakeIngredientService(result=(7, errors))

    result = IngredientProductsImportFlowService(fake).import_products(file_path)

    assert result.status == "warning"
    assert result.imported == 7
    assert result.errors == errors
    assert result.preview.startswith("Fila 2: error")
    assert "... y 2 errores mas." in result.preview
    assert "Fila 11: error" not in result.preview


def test_import_products_returns_error_on_service_exception(tmp_path: Path) -> None:
    file_path = tmp_path / "productos.xlsm"
    file_path.write_text("", encoding="utf-8")
    fake = _FakeIngredientService(exc=RuntimeError("boom"))

    result = IngredientProductsImportFlowService(fake).import_products(file_path)

    assert result.status == "error"
    assert result.imported == 0
    assert result.errors == ["boom"]
    assert result.preview == "boom"
    assert len(fake.calls) == 1


def test_import_products_keeps_single_preview_line_when_one_error(tmp_path: Path) -> None:
    file_path = tmp_path / "productos.csv"
    file_path.write_text("", encoding="utf-8")
    fake = _FakeIngredientService(result=(1, ["Fila 2: campo obligatorio vacio: articulo_id"]))

    result = IngredientProductsImportFlowService(fake).import_products(file_path)

    assert result.status == "warning"
    assert result.preview == "Fila 2: campo obligatorio vacio: articulo_id"

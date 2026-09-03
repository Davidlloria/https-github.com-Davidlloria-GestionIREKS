from __future__ import annotations

from pathlib import Path

import pytest

from app.services.recipe_image_storage_service import resolve_recipe_image_path, store_recipe_image


def test_store_recipe_image_copies_file_and_returns_portable_path(tmp_path: Path) -> None:
    source = tmp_path / "origen" / "panettone.jpg"
    source.parent.mkdir()
    source.write_bytes(b"recipe-image")
    data_dir = tmp_path / "data"

    stored_path = store_recipe_image(source, data_dir=data_dir)
    resolved_path = resolve_recipe_image_path(stored_path, data_dir=data_dir)

    assert Path(stored_path).parts[0] == "recetas_imagenes"
    assert not Path(stored_path).is_absolute()
    assert resolved_path.name == "panettone.jpg"
    assert resolved_path.read_bytes() == b"recipe-image"
    assert resolved_path != source


def test_store_recipe_image_reuses_file_already_in_managed_folder(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    managed_image = data_dir / "recetas_imagenes" / "existing.png"
    managed_image.parent.mkdir(parents=True)
    managed_image.write_bytes(b"managed")

    stored_path = store_recipe_image(managed_image, data_dir=data_dir)

    assert stored_path == "recetas_imagenes/existing.png"
    assert list(managed_image.parent.iterdir()) == [managed_image]


def test_resolve_recipe_image_path_keeps_legacy_absolute_path(tmp_path: Path) -> None:
    source = (tmp_path / "legacy.webp").resolve()

    assert resolve_recipe_image_path(str(source), data_dir=tmp_path / "data") == source


def test_store_recipe_image_rejects_missing_or_unsupported_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no existe"):
        store_recipe_image(tmp_path / "missing.jpg", data_dir=tmp_path / "data")

    unsupported = tmp_path / "recipe.txt"
    unsupported.write_text("not an image", encoding="utf-8")
    with pytest.raises(ValueError, match="Formato no admitido"):
        store_recipe_image(unsupported, data_dir=tmp_path / "data")

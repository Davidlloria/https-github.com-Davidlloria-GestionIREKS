from __future__ import annotations

from pathlib import Path
import shutil
from uuid import uuid4

from app.core.config import DATA_DIR


RECIPE_IMAGES_FOLDER = "recetas_imagenes"
ALLOWED_RECIPE_IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".webp"}


def resolve_recipe_image_path(stored_path: str, *, data_dir: Path | None = None) -> Path:
    path = Path(str(stored_path or "").strip())
    if path.is_absolute():
        return path.resolve()
    root = Path(data_dir or DATA_DIR).resolve()
    return (root / path).resolve()


def store_recipe_image(source_path: Path, *, data_dir: Path | None = None) -> str:
    source = Path(source_path).resolve()
    if not source.is_file():
        raise ValueError("La imagen seleccionada no existe.")
    suffix = source.suffix.lower()
    if suffix not in ALLOWED_RECIPE_IMAGE_SUFFIXES:
        raise ValueError("Formato no admitido. Usa JPG, PNG, WEBP o BMP.")

    root = Path(data_dir or DATA_DIR).resolve()
    images_dir = (root / RECIPE_IMAGES_FOLDER).resolve()
    try:
        source.relative_to(images_dir)
        return source.relative_to(root).as_posix()
    except ValueError:
        pass

    target_dir = images_dir / uuid4().hex
    target_dir.mkdir(parents=True, exist_ok=False)
    target = target_dir / source.name
    shutil.copy2(source, target)
    return target.relative_to(root).as_posix()

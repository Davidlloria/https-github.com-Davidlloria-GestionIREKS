from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from app.api.errors import bad_request


MAX_LOCAL_PATH_LENGTH = 1024


def input_file_path(
    value: str,
    *,
    field_name: str,
    allowed_suffixes: Iterable[str],
) -> Path:
    path = _path(value, field_name=field_name, allowed_suffixes=allowed_suffixes)
    try:
        if not path.exists():
            raise bad_request(f"{field_name} no existe.")
        if not path.is_file():
            raise bad_request(f"{field_name} debe ser un archivo.")
    except OSError as exc:
        raise bad_request(f"{field_name} no es una ruta valida.") from exc
    return path


def output_file_path(
    value: str,
    *,
    field_name: str,
    allowed_suffixes: Iterable[str],
) -> Path:
    path = _path(value, field_name=field_name, allowed_suffixes=allowed_suffixes)
    try:
        if path.exists() and path.is_dir():
            raise bad_request(f"{field_name} no puede ser un directorio.")
    except OSError as exc:
        raise bad_request(f"{field_name} no es una ruta valida.") from exc
    return path


def _path(value: str, *, field_name: str, allowed_suffixes: Iterable[str]) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise bad_request(f"Indica {field_name}.")
    if len(raw) > MAX_LOCAL_PATH_LENGTH:
        raise bad_request(f"{field_name} supera la longitud maxima permitida.")
    if "\x00" in raw:
        raise bad_request(f"{field_name} no es una ruta valida.")

    path = Path(raw)
    allowed = {suffix.lower() for suffix in allowed_suffixes}
    suffix = path.suffix.lower()
    if allowed and suffix not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise bad_request(f"{field_name} debe usar extension: {allowed_list}.")
    return path

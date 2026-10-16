from __future__ import annotations

from pathlib import Path
import os
import re

from app.core.config import BASE_DIR


class WorkFilesError(ValueError):
    """A filesystem request cannot be completed within Trabajo."""


class WorkFilesService:
    def __init__(self, root: str | Path | None = None) -> None:
        self._configured_root = Path(root if root is not None else BASE_DIR.parent / "Trabajo").absolute()
        self.root = self._configured_root.resolve()

    @staticmethod
    def _validated_name(name: str) -> str:
        reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
        reserved |= {prefix + digit for prefix in ("COM", "LPT") for digit in "123456789¹²³"}
        if (not name or name != name.strip() or name in {".", ".."} or name.endswith(".")
                or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
                or name.split(".", 1)[0].upper() in reserved):
            raise WorkFilesError("Introduce un nombre válido de Windows, sin rutas ni caracteres reservados.")
        return name

    def create_folder(self, parent: str | Path, name: str) -> Path:
        parent = self.checked_path(parent, directory=True)
        destination = parent / self._validated_name(name)
        try:
            destination.mkdir()
        except FileExistsError as exc:
            raise WorkFilesError("Ya existe un archivo o una carpeta con ese nombre.") from exc
        except OSError as exc:
            raise WorkFilesError("No se pudo crear la carpeta. Comprueba los permisos y el nombre.") from exc
        return destination

    def rename(self, path: str | Path, name: str) -> Path:
        source = self.checked_path(path, allow_root=False)
        destination = source.with_name(self._validated_name(name))
        if source.name == name:
            return source
        case_only = os.name == "nt" and source.name.casefold() == name.casefold()
        if (destination.exists() or destination.is_symlink() or destination.is_junction()) and not case_only:
            raise WorkFilesError("Ya existe un archivo o una carpeta con ese nombre.")
        try:
            source.rename(destination)
        except OSError as exc:
            raise WorkFilesError("No se pudo renombrar. El elemento puede estar en uso o no tienes permisos.") from exc
        return destination

    def move(self, path: str | Path, directory: str | Path) -> Path:
        source = self.checked_path(path, allow_root=False)
        directory = self.checked_path(directory, directory=True)
        if directory == source.parent:
            raise WorkFilesError("El elemento ya está en la carpeta elegida.")
        if source.is_dir() and directory.is_relative_to(source):
            raise WorkFilesError("No se puede mover una carpeta dentro de sí misma.")
        destination = directory / source.name
        if destination.exists() or destination.is_symlink() or destination.is_junction():
            raise WorkFilesError("Ya existe un elemento con ese nombre en el destino. No se ha sobrescrito.")
        try:
            source.rename(destination)
        except OSError as exc:
            raise WorkFilesError("No se pudo mover. El elemento puede estar en uso o no tienes permisos.") from exc
        return destination

    def checked_path(self, path: str | Path, *, directory: bool = False,
                     allow_root: bool = True) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        try:
            resolved = candidate.resolve(strict=True)
            if (not resolved.is_relative_to(self.root)
                    or (resolved == self.root and not allow_root)):
                raise WorkFilesError("La operación debe permanecer dentro de Trabajo.")
            if (not self.root.is_dir() or self._configured_root.is_symlink()
                    or self._configured_root.is_junction() or self._configured_root.resolve() != self.root):
                raise WorkFilesError("No se encuentra la carpeta Trabajo o su ubicación ha cambiado.")
            # Do not browse through links, even when their target is currently internal.
            current = candidate.absolute()
            while current != self.root and current.is_relative_to(self.root):
                if current.is_symlink() or current.is_junction():
                    raise WorkFilesError("No se permite acceder mediante enlaces de carpetas o archivos.")
                current = current.parent
            if directory and not resolved.is_dir():
                raise WorkFilesError("Selecciona una carpeta.")
            return resolved
        except (OSError, RuntimeError) as exc:
            raise WorkFilesError("No se puede acceder a la ubicación. Comprueba que existe y tienes permisos.") from exc

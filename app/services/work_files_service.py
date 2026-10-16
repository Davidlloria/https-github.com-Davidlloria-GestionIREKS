from __future__ import annotations

from pathlib import Path

from app.core.config import BASE_DIR


class WorkFilesError(ValueError):
    """A filesystem request cannot be completed within Trabajo."""


class WorkFilesService:
    def __init__(self, root: str | Path | None = None) -> None:
        self._configured_root = Path(root if root is not None else BASE_DIR.parent / "Trabajo").absolute()
        self.root = self._configured_root.resolve()

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

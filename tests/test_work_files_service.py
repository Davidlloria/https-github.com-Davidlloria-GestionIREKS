from pathlib import Path

import pytest

from app.services.work_files_service import WorkFilesError, WorkFilesService


@pytest.fixture
def service(tmp_path):
    root = tmp_path / "Trabajo"
    root.mkdir()
    (root / "Clientes").mkdir()
    (root / "Clientes" / "nota.txt").write_text("contenido", encoding="utf-8")
    return WorkFilesService(root)


def test_paths_must_stay_inside_existing_work_root(service, tmp_path):
    assert service.checked_path("Clientes", directory=True) == service.root / "Clientes"
    assert service.checked_path(service.root) == service.root
    outside = tmp_path / "privado.txt"
    outside.write_text("fuera", encoding="utf-8")
    for path in (outside, "../privado.txt", "no-existe", service.root / "Clientes" / ".." / ".."):
        with pytest.raises(WorkFilesError):
            service.checked_path(path)
    with pytest.raises(WorkFilesError):
        service.checked_path(service.root, allow_root=False)
    with pytest.raises(WorkFilesError):
        service.checked_path("Clientes/nota.txt", directory=True)


def test_missing_root_is_not_created(tmp_path):
    service = WorkFilesService(tmp_path / "ausente")
    with pytest.raises(WorkFilesError):
        service.checked_path(service.root)
    assert not service.root.exists()


@pytest.mark.parametrize("name", ["", ".", "..", "../fuera", "a/b", "a\\b", "NUL.txt", "COM1", "LPT².txt", "a:", "con.", "a.", " a", "a ", "a\x00"])
def test_create_folder_rejects_invalid_windows_names(service, name):
    before = set(service.root.iterdir())
    with pytest.raises(WorkFilesError):
        service.create_folder(service.root, name)
    assert set(service.root.iterdir()) == before


def test_create_folder_preserves_existing_files_and_handles_permissions(service, monkeypatch):
    created = service.create_folder("Clientes", "Nueva carpeta")
    assert created.is_dir()
    with pytest.raises(WorkFilesError):
        service.create_folder("Clientes", "nota.txt")
    with pytest.raises(WorkFilesError):
        service.create_folder("Clientes", "Nueva carpeta")
    assert (service.root / "Clientes/nota.txt").read_text(encoding="utf-8") == "contenido"
    monkeypatch.setattr(Path, "mkdir", lambda *a, **kw: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(WorkFilesError, match="permisos"):
        service.create_folder(service.root, "Denegada")


def test_windows_junction_cannot_escape_root(service, tmp_path):
    import os
    import subprocess
    if os.name != "nt":
        pytest.skip("Windows junction")
    outside = tmp_path / "fuera"
    outside.mkdir()
    link = service.root / "enlace"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
    assert result.returncode == 0, result.stderr
    try:
        with pytest.raises(WorkFilesError):
            service.checked_path(link, directory=True)
    finally:
        link.rmdir()  # Remove only the junction, never its target.
    assert outside.is_dir()

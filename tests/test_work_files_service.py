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


def test_rename_file_and_folder_preserves_contents_and_case_changes(service):
    file = service.rename("Clientes/nota.txt", "Nota.txt")
    assert file.name == "Nota.txt"
    assert file.read_text(encoding="utf-8") == "contenido"
    folder = service.rename("Clientes", "Clientes antiguos")
    assert (folder / "Nota.txt").read_text(encoding="utf-8") == "contenido"
    assert service.rename(folder, folder.name) == folder


def test_rename_blocks_root_collisions_and_invalid_names(service):
    existing = service.root / "Clientes/existente.txt"
    existing.write_text("conservar", encoding="utf-8")
    for source, name in ((service.root, "Otra"), ("Clientes/nota.txt", "existente.txt"),
                         ("Clientes", "../fuera"), ("Clientes", "NUL")):
        with pytest.raises(WorkFilesError):
            service.rename(source, name)
    assert existing.read_text(encoding="utf-8") == "conservar"
    assert (service.root / "Clientes/nota.txt").read_text(encoding="utf-8") == "contenido"


def test_rename_locked_file_reports_error_without_removing_source(service, monkeypatch):
    def denied(*args):
        raise PermissionError("locked")
    monkeypatch.setattr(Path, "rename", denied)
    with pytest.raises(WorkFilesError, match="uso"):
        service.rename("Clientes/nota.txt", "otra.txt")
    assert (service.root / "Clientes/nota.txt").exists()


def test_move_files_and_populated_folders_preserves_content(service):
    target = service.create_folder(service.root, "Pedidos")
    folder = service.move("Clientes", target)
    assert not (service.root / "Clientes").exists()
    assert (folder / "nota.txt").read_text(encoding="utf-8") == "contenido"
    file = service.move(folder / "nota.txt", service.root)
    assert file.read_text(encoding="utf-8") == "contenido"


def test_move_rejects_external_destinations_root_descendants_and_collisions(service, tmp_path):
    nested = service.create_folder("Clientes", "Subcarpeta")
    duplicate = service.root / "nota.txt"
    duplicate.write_text("original", encoding="utf-8")
    for source, destination in ((service.root, nested), ("Clientes", nested), ("Clientes", "Clientes"),
                                ("Clientes/nota.txt", tmp_path), ("Clientes/nota.txt", service.root),
                                ("Clientes/nota.txt", "Clientes")):
        with pytest.raises(WorkFilesError):
            service.move(source, destination)
    assert duplicate.read_text(encoding="utf-8") == "original"
    assert (service.root / "Clientes/nota.txt").read_text(encoding="utf-8") == "contenido"


def test_move_permission_error_leaves_source_in_place(service, monkeypatch):
    def denied(*args):
        raise PermissionError()
    monkeypatch.setattr(Path, "rename", denied)
    with pytest.raises(WorkFilesError, match="uso"):
        service.move("Clientes/nota.txt", service.root)
    assert (service.root / "Clientes/nota.txt").exists()


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

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


def load_build_module():
    build_path = Path(__file__).resolve().parents[1] / 'scripts' / 'build_react_desktop_pyinstaller.py'
    spec = importlib.util.spec_from_file_location('build_react_desktop_pyinstaller', build_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_runtime_assets_copies_database_and_frontend():
    module = load_build_module()
    root = Path(__file__).resolve().parents[1]

    with tempfile.TemporaryDirectory(dir=root) as temp_dir:
        bundle_root = Path(temp_dir) / 'GestionIREKSReactDesktop'
        module.stage_runtime_assets(bundle_root)

        db_path = bundle_root / '_internal' / 'data' / 'gestion_ireks.db'
        frontend_index = bundle_root / '_internal' / 'frontend' / 'dist' / 'index.html'

        assert db_path.exists()
        assert db_path.stat().st_size > 0
        assert frontend_index.exists()


def test_stage_runtime_assets_rejects_empty_database(monkeypatch):
    module = load_build_module()
    root = Path(__file__).resolve().parents[1]

    with tempfile.TemporaryDirectory(dir=root) as temp_dir:
        temp_root = Path(temp_dir)
        empty_db = temp_root / 'gestion_ireks.db'
        empty_db.write_bytes(b'')
        fake_frontend_dist = root / 'frontend' / 'dist'

        monkeypatch.setattr(module, 'SOURCE_DB', empty_db)
        monkeypatch.setattr(module, 'FRONTEND_DIST', fake_frontend_dist)

        try:
            module.stage_runtime_assets(temp_root / 'bundle')
        except RuntimeError as exc:
            assert 'vacia' in str(exc).lower()
        else:
            raise AssertionError('stage_runtime_assets should reject an empty database')

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


def load_launcher_module():
    launcher_path = Path(__file__).resolve().parents[1] / 'scripts' / 'run_react_desktop_dev.py'
    spec = importlib.util.spec_from_file_location('run_react_desktop_dev', launcher_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DummyProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self._running = True

    def poll(self):
        return None if self._running else 0


def test_cleanup_terminates_children_and_waits_for_ports(monkeypatch):
    module = load_launcher_module()
    module._children = [DummyProcess(101), DummyProcess(202)]
    module._cleaning_up = False
    module._runtime_ports = ('127.0.0.1', 8000, 5173)

    terminated: list[int] = []
    waited: list[tuple[str, int]] = []

    def fake_terminate(process):
        terminated.append(process.pid)
        process._running = False

    def fake_wait_for_port_closed(host: str, port: int, timeout_seconds: int) -> bool:
        waited.append((host, port))
        return True

    monkeypatch.setattr(module, 'terminate_process', fake_terminate)
    monkeypatch.setattr(module, 'wait_for_port_closed', fake_wait_for_port_closed)

    module.cleanup()

    assert terminated == [202, 101]
    assert waited == [('127.0.0.1', 8000), ('127.0.0.1', 5173)]


def test_cleanup_keeps_trying_when_a_termination_step_fails(monkeypatch):
    module = load_launcher_module()
    module._children = [DummyProcess(101), DummyProcess(202)]
    module._cleaning_up = False
    module._runtime_ports = ('127.0.0.1', 8000, 5173)

    terminated: list[int] = []
    waited: list[tuple[str, int]] = []

    def fake_terminate(process):
        terminated.append(process.pid)
        if process.pid == 202:
            raise RuntimeError('boom')
        process._running = False

    def fake_wait_for_port_closed(host: str, port: int, timeout_seconds: int) -> bool:
        waited.append((host, port))
        return True

    monkeypatch.setattr(module, 'terminate_process', fake_terminate)
    monkeypatch.setattr(module, 'wait_for_port_closed', fake_wait_for_port_closed)

    module.cleanup()

    assert terminated == [202, 101]
    assert waited == [('127.0.0.1', 8000), ('127.0.0.1', 5173)]


def test_get_frontend_dist_uses_bundle_root(monkeypatch):
    module = load_launcher_module()
    monkeypatch.setattr(module, 'RUNNING_IN_BUNDLE', True)
    bundle_root = Path('C:/bundle-root')
    monkeypatch.setattr(module.sys, '_MEIPASS', str(bundle_root), raising=False)

    assert module.get_frontend_dist() == bundle_root / 'frontend' / 'dist'


def test_get_runtime_db_path_uses_bundle_root(monkeypatch):
    module = load_launcher_module()
    monkeypatch.setattr(module, 'RUNNING_IN_BUNDLE', True)
    monkeypatch.setattr(module.sys, 'executable', str(Path('C:/bundle-root/GestionIREKSReactDesktop.exe')), raising=False)

    assert module.get_runtime_db_path() == Path('C:/bundle-root/data/gestion_ireks.db')


def test_get_runtime_db_path_honors_env_override(monkeypatch):
    module = load_launcher_module()
    monkeypatch.setenv('GESTION_IREKS_DATA_DIR', 'C:/external-data')
    monkeypatch.setattr(module, 'RUNNING_IN_BUNDLE', True)
    monkeypatch.setattr(module.sys, 'executable', str(Path('C:/bundle-root/GestionIREKSReactDesktop.exe')), raising=False)

    assert module.get_runtime_db_path() == Path('C:/external-data/gestion_ireks.db')


def test_validate_runtime_database_rejects_missing_external_db(monkeypatch):
    module = load_launcher_module()
    monkeypatch.setattr(module, 'RUNNING_IN_BUNDLE', True)
    monkeypatch.setattr(module.sys, 'executable', str(Path('C:/bundle-root/GestionIREKSReactDesktop.exe')), raising=False)

    try:
        module.validate_runtime_database()
    except RuntimeError as exc:
        assert 'base de datos real' in str(exc).lower()
    else:
        raise AssertionError('validate_runtime_database should reject a missing external database')


def test_validate_runtime_database_rejects_empty_external_db(monkeypatch):
    module = load_launcher_module()
    monkeypatch.setattr(module, 'RUNNING_IN_BUNDLE', True)
    root = Path(__file__).resolve().parents[1]

    with tempfile.TemporaryDirectory(dir=root) as temp_dir:
        temp_root = Path(temp_dir)
        data_dir = temp_root / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / 'gestion_ireks.db'
        db_path.write_bytes(b'')
        monkeypatch.setattr(module.sys, 'executable', str(temp_root / 'GestionIREKSReactDesktop.exe'), raising=False)

        try:
            module.validate_runtime_database()
        except RuntimeError as exc:
            assert 'vacia' in str(exc).lower()
        else:
            raise AssertionError('validate_runtime_database should reject an empty external database')


def test_open_frontend_in_app_mode_uses_browser_app_mode(monkeypatch):
    module = load_launcher_module()
    browser_path = Path('C:/Browsers/Edge/msedge.exe')
    captured: dict[str, object] = {}

    monkeypatch.setattr(module, 'find_browser_app_path', lambda: browser_path)
    monkeypatch.setattr(module.subprocess, 'Popen', lambda command, **kwargs: captured.update({'command': command, 'kwargs': kwargs}))

    module.open_frontend_in_app_mode('http://127.0.0.1:5173')

    assert captured['command'] == [str(browser_path), '--app=http://127.0.0.1:5173']


def test_open_frontend_in_app_mode_falls_back_to_webbrowser(monkeypatch):
    module = load_launcher_module()
    captured: dict[str, object] = {}

    monkeypatch.setattr(module, 'find_browser_app_path', lambda: None)
    monkeypatch.setattr(module.webbrowser, 'open', lambda url: captured.update({'url': url}))

    module.open_frontend_in_app_mode('http://127.0.0.1:5173')

    assert captured['url'] == 'http://127.0.0.1:5173'

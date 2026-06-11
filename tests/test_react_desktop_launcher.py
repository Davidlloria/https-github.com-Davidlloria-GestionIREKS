from __future__ import annotations

import importlib.util
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
    bundle_root = Path('C:/bundle-root')
    monkeypatch.setattr(module.sys, '_MEIPASS', str(bundle_root), raising=False)

    assert module.get_runtime_db_path() == bundle_root / 'data' / 'gestion_ireks.db'

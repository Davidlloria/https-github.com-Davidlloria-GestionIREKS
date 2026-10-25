from pathlib import Path
import os
import subprocess
import sys
import time

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows desktop launcher")
ROOT = Path(__file__).resolve().parents[1]


def prepare_launcher(tmp_path):
    source = (ROOT / "run-desktop.vbs").read_text()
    # Report errors to the test process instead of displaying a modal dialog.
    source = source.replace("MsgBox ", "WScript.Echo ").replace(
        'python = "pythonw.exe"',
        'python = "' + str(Path(sys.executable).with_name("pythonw.exe")) + '"',
    )
    (tmp_path / "run-desktop.vbs").write_text(source)
    (tmp_path / "run-desktop.pyw").write_text((ROOT / "run-desktop.pyw").read_text())
    env = dict(os.environ, TEMP=str(tmp_path))
    return ["cscript.exe", "//nologo", str(tmp_path / "run-desktop.vbs")], env


def test_overlapping_launches_do_not_lock_each_others_log(tmp_path):
    command, env = prepare_launcher(tmp_path)
    (tmp_path / "run.py").write_text(
        "import pathlib, sys, time\n"
        "pathlib.Path('started').touch()\n"
        "print('started', flush=True)\n"
        "time.sleep(3)\n"
    )
    first = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "started").exists():
            assert first.poll() is None, first.communicate()
            assert time.monotonic() < deadline, "First launch did not start"
            time.sleep(0.05)
        second = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
        assert second.returncode == 0, second.stdout + second.stderr
        stdout, stderr = first.communicate(timeout=15)
        assert first.returncode == 0, stdout + stderr
        logs = list(tmp_path.glob("GestionIREKS-desktop*.log"))
        assert len(logs) == 2
        assert all("started" in log.read_text() for log in logs)
    finally:
        if first.poll() is None:
            first.wait(timeout=15)


def test_failed_launch_reports_exit_code_and_log(tmp_path):
    command, env = prepare_launcher(tmp_path)
    (tmp_path / "run.py").write_text('print("startup-failed")\nraise SystemExit(7)\n')
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 7
    assert "codigo 7" in result.stdout
    log, = tmp_path.glob("GestionIREKS-desktop*.log")
    assert str(log) in result.stdout
    assert "startup-failed" in log.read_text()


def test_first_launch_displays_window_without_console(tmp_path):
    command, env = prepare_launcher(tmp_path)
    (tmp_path / "run.py").write_text(
        "import ctypes\n"
        "from PySide6.QtWidgets import QApplication, QWidget\n"
        "app = QApplication([])\n"
        "window = QWidget()\n"
        "window.show()\n"
        "app.processEvents()\n"
        "assert not ctypes.windll.kernel32.GetConsoleWindow()\n"
        "assert ctypes.windll.user32.IsWindowVisible(int(window.winId()))\n"
        "window.close()\n"
        "print('visible-without-console')\n"
    )
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=20)
    log, = tmp_path.glob("GestionIREKS-desktop*.log")
    assert result.returncode == 0, log.read_text() + result.stdout + result.stderr
    assert "visible-without-console" in log.read_text()


@pytest.mark.parametrize("explicit_override", [False, True])
def test_preserves_data_directory_selection(tmp_path, explicit_override):
    command, env = prepare_launcher(tmp_path)
    sibling = tmp_path.parent / "GestionIREKS-Datos"
    sibling.mkdir(exist_ok=True)
    (sibling / "gestion_ireks.db").touch()
    expected = str(tmp_path / "custom-data") if explicit_override else str(sibling)
    env.pop("GESTION_IREKS_DATA_DIR", None)
    if explicit_override:
        env["GESTION_IREKS_DATA_DIR"] = expected
    (tmp_path / "run.py").write_text(
        "import os\n"
        f"assert os.environ['GESTION_IREKS_DATA_DIR'] == {expected!r}\n"
    )
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    log, = tmp_path.glob("GestionIREKS-desktop*.log")
    assert result.returncode == 0, log.read_text() + result.stdout + result.stderr


def test_unhandled_exception_is_logged(tmp_path):
    command, env = prepare_launcher(tmp_path)
    (tmp_path / "run.py").write_text('raise RuntimeError("startup-test-error")\n')
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    log, = tmp_path.glob("GestionIREKS-desktop*.log")
    assert "RuntimeError: startup-test-error" in log.read_text()


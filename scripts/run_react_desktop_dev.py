from __future__ import annotations

import argparse
import atexit
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
API_HOST = "127.0.0.1"
API_PORT = 8000
FRONTEND_PORT = 5173
RUNTIME_DATA_DIR_ENV = "GESTION_IREKS_DATA_DIR"
RUNNING_IN_BUNDLE = bool(getattr(sys, "frozen", False))


def get_runtime_root() -> Path:
    if RUNNING_IN_BUNDLE:
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            return Path(bundle_root)
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def get_distribution_root() -> Path:
    if RUNNING_IN_BUNDLE:
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def get_runtime_data_dir() -> Path:
    override = os.environ.get(RUNTIME_DATA_DIR_ENV)
    if override:
        return Path(override)
    return get_distribution_root() / "data"


def get_frontend_dist() -> Path:
    return get_runtime_root() / "frontend" / "dist"


def get_runtime_db_path() -> Path:
    return get_runtime_data_dir() / "gestion_ireks.db"


_children: list[subprocess.Popen[str]] = []
_frozen_api_server: uvicorn.Server | None = None
_frozen_api_thread: threading.Thread | None = None
_frozen_frontend_server: ThreadingHTTPServer | None = None
_frozen_frontend_thread: threading.Thread | None = None
_cleaning_up = False
_runtime_ports: tuple[str, int, int] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the React + FastAPI desktop spike locally.")
    parser.add_argument("--api-host", default=API_HOST)
    parser.add_argument("--api-port", type=int, default=API_PORT)
    parser.add_argument("--frontend-port", type=int, default=FRONTEND_PORT)
    parser.add_argument("--startup-timeout", type=int, default=60)
    parser.add_argument("--hold-seconds", type=int, default=5)
    parser.add_argument("--build", action="store_true", help="Run npm.cmd run build in frontend before starting.")
    parser.add_argument("--exit-after-start", action="store_true")
    parser.add_argument("--no-open-browser", action="store_true")
    return parser.parse_args()


def wait_for_port(host: str, port: int, timeout_seconds: int) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def wait_for_port_closed(host: str, port: int, timeout_seconds: int) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                time.sleep(0.5)
        except OSError:
            return True
    return False


def run_frontend_build() -> None:
    build_command = ["npm.cmd", "run", "build"]
    creationflags = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    result = subprocess.run(build_command, cwd=str(FRONTEND_DIR), check=False, creationflags=creationflags)
    if result.returncode != 0:
        raise RuntimeError("El build del frontend ha fallado. Ejecuta 'cd frontend' y 'npm.cmd run build' para ver el error.")


def validate_runtime_database() -> None:
    if not RUNNING_IN_BUNDLE:
        return

    db_path = get_runtime_db_path()
    if not db_path.exists():
        raise RuntimeError(
            "No existe la base de datos real en el bundle.\n"
            "Vuelve a ejecutar el build PyInstaller y asegúrate de copiar data/gestion_ireks.db."
        )
    if db_path.stat().st_size == 0:
        raise RuntimeError(
            "La base de datos del bundle esta vacia.\n"
            "Crea GestionIREKSReactDesktop/data/gestion_ireks.db con la base de datos real."
        )


def configure_runtime_environment() -> None:
    if RUNNING_IN_BUNDLE:
        os.environ.setdefault(RUNTIME_DATA_DIR_ENV, str(get_runtime_data_dir()))


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def start_process(command: list[str], cwd: Path, extra_env: dict[str, str] | None = None) -> subprocess.Popen[str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    popen_kwargs: dict[str, object] = {"cwd": str(cwd), "env": env}
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess,
            "CREATE_BREAKAWAY_FROM_JOB",
            0,
        )
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **popen_kwargs)
    _children.append(process)
    return process


def start_frozen_api_server(host: str, port: int) -> None:
    global _frozen_api_server, _frozen_api_thread

    configure_runtime_environment()
    from app.api.main import app as fastapi_app

    server = uvicorn.Server(
        uvicorn.Config(
            fastapi_app,
            host=host,
            port=port,
            access_log=False,
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, name="api-server", daemon=True)
    _frozen_api_server = server
    _frozen_api_thread = thread
    thread.start()


def start_frozen_frontend_server(port: int) -> None:
    global _frozen_frontend_server, _frozen_frontend_thread

    frontend_dist = get_frontend_dist()
    handler = partial(QuietStaticHandler, directory=str(frontend_dist))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, name="frontend-server", daemon=True)
    _frozen_frontend_server = server
    _frozen_frontend_thread = thread
    thread.start()


def terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    if os.name == "nt":
        try:
            taskkill = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                check=False,
                capture_output=True,
                text=True,
            )
            if taskkill.returncode == 0:
                return
        except BaseException:
            pass

    try:
        process.terminate()
        process.wait(timeout=5)
    except BaseException:
        try:
            process.kill()
            process.wait(timeout=5)
        except BaseException:
            pass


def cleanup_frozen_runtime() -> None:
    global _frozen_api_server, _frozen_api_thread, _frozen_frontend_server, _frozen_frontend_thread

    if _frozen_frontend_server is not None:
        try:
            _frozen_frontend_server.shutdown()
        except BaseException:
            pass
        try:
            _frozen_frontend_server.server_close()
        except BaseException:
            pass

    if _frozen_api_server is not None:
        try:
            _frozen_api_server.should_exit = True
        except BaseException:
            pass

    if _runtime_ports is not None:
        api_host, api_port, frontend_port = _runtime_ports
        for _ in range(3):
            api_closed = wait_for_port_closed(api_host, api_port, 2)
            frontend_closed = wait_for_port_closed("127.0.0.1", frontend_port, 2)
            if api_closed and frontend_closed:
                break
            if _frozen_frontend_server is not None:
                try:
                    _frozen_frontend_server.shutdown()
                except BaseException:
                    pass
            if _frozen_api_server is not None:
                try:
                    _frozen_api_server.should_exit = True
                except BaseException:
                    pass

    if _frozen_api_thread is not None:
        try:
            _frozen_api_thread.join(timeout=5)
        except BaseException:
            pass
    if _frozen_frontend_thread is not None:
        try:
            _frozen_frontend_thread.join(timeout=5)
        except BaseException:
            pass

    _frozen_api_server = None
    _frozen_api_thread = None
    _frozen_frontend_server = None
    _frozen_frontend_thread = None


def cleanup() -> None:
    global _cleaning_up
    if _cleaning_up:
        return
    _cleaning_up = True

    if RUNNING_IN_BUNDLE:
        cleanup_frozen_runtime()
        return

    for process in reversed(_children):
        try:
            terminate_process(process)
        except BaseException:
            pass
    if _runtime_ports is None:
        return
    api_host, api_port, frontend_port = _runtime_ports
    for _ in range(3):
        api_closed = wait_for_port_closed(api_host, api_port, 2)
        frontend_closed = wait_for_port_closed("127.0.0.1", frontend_port, 2)
        if api_closed and frontend_closed:
            return
        for process in reversed(_children):
            try:
                terminate_process(process)
            except BaseException:
                pass


def handle_signal(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main() -> int:
    args = parse_args()
    global _runtime_ports
    _runtime_ports = (args.api_host, args.api_port, args.frontend_port)

    if not RUNNING_IN_BUNDLE and not FRONTEND_DIR.exists():
        print(f"No existe el directorio frontend: {FRONTEND_DIR}", file=sys.stderr)
        return 1

    frontend_dist = get_frontend_dist()
    if not frontend_dist.exists():
        print(
            "No existe frontend/dist.\n"
            "Ejecuta primero:\n"
            "  cd frontend\n"
            "  npm.cmd run build\n"
            "Luego vuelve a lanzar este script.",
            file=sys.stderr,
        )
        return 1

    if args.build:
        if RUNNING_IN_BUNDLE:
            print("--build no esta disponible en el binario empaquetado. Usa el script de desarrollo.", file=sys.stderr)
            return 1
        try:
            run_frontend_build()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    atexit.register(cleanup)
    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    try:
        if RUNNING_IN_BUNDLE:
            validate_runtime_database()
            print(f"Starting API on http://{args.api_host}:{args.api_port}")
            start_frozen_api_server(args.api_host, args.api_port)

            if not wait_for_port(args.api_host, args.api_port, args.startup_timeout):
                print("La API no levanto a tiempo.", file=sys.stderr)
                return 1
            if _frozen_api_thread is not None and not _frozen_api_thread.is_alive():
                print("La API se cerro durante el arranque.", file=sys.stderr)
                return 1

            print(f"Starting frontend on http://127.0.0.1:{args.frontend_port}")
            start_frozen_frontend_server(args.frontend_port)

            if not wait_for_port("127.0.0.1", args.frontend_port, args.startup_timeout):
                print("El frontend no levanto a tiempo.", file=sys.stderr)
                return 1
            if _frozen_frontend_thread is not None and not _frozen_frontend_thread.is_alive():
                print("El frontend se cerro durante el arranque.", file=sys.stderr)
                return 1

            frontend_url = f"http://127.0.0.1:{args.frontend_port}"
            print(f"Frontend ready: {frontend_url}")
            print(f"API ready: http://{args.api_host}:{args.api_port}")

            if not args.no_open_browser:
                webbrowser.open(frontend_url)

            if args.exit_after_start:
                time.sleep(max(0, args.hold_seconds))
                return 0

            while True:
                if _frozen_api_thread is not None and not _frozen_api_thread.is_alive():
                    print("La API termino durante la ejecucion.", file=sys.stderr)
                    return 1
                if _frozen_frontend_thread is not None and not _frozen_frontend_thread.is_alive():
                    print("El frontend termino durante la ejecucion.", file=sys.stderr)
                    return 1
                time.sleep(1)

        api_command = [
            sys.executable,
            "-m",
            "uvicorn",
            "app.api.main:app",
            "--host",
            args.api_host,
            "--port",
            str(args.api_port),
        ]
        frontend_command = [
            sys.executable,
            "-m",
            "http.server",
            str(args.frontend_port),
            "--bind",
            "127.0.0.1",
            "--directory",
            str(frontend_dist),
        ]

        print(f"Starting API on http://{args.api_host}:{args.api_port}")
        api_process = start_process(api_command, PROJECT_ROOT)

        if not wait_for_port(args.api_host, args.api_port, args.startup_timeout):
            print("La API no levanto a tiempo.", file=sys.stderr)
            return 1
        if api_process.poll() is not None:
            print(f"La API se cerro con codigo {api_process.returncode}.", file=sys.stderr)
            return 1

        print(f"Starting frontend on http://127.0.0.1:{args.frontend_port}")
        frontend_process = start_process(frontend_command, PROJECT_ROOT)

        if not wait_for_port("127.0.0.1", args.frontend_port, args.startup_timeout):
            print("El frontend no levanto a tiempo.", file=sys.stderr)
            return 1
        if frontend_process.poll() is not None:
            print(f"El frontend se cerro con codigo {frontend_process.returncode}.", file=sys.stderr)
            return 1

        frontend_url = f"http://127.0.0.1:{args.frontend_port}"
        print(f"Frontend ready: {frontend_url}")
        print(f"API ready: http://{args.api_host}:{args.api_port}")

        if not args.no_open_browser:
            webbrowser.open(frontend_url)

        if args.exit_after_start:
            time.sleep(max(0, args.hold_seconds))
            return 0

        while True:
            if api_process.poll() is not None:
                print(f"La API termino con codigo {api_process.returncode}.", file=sys.stderr)
                return 1
            if frontend_process.poll() is not None:
                print(f"El frontend termino con codigo {frontend_process.returncode}.", file=sys.stderr)
                return 1
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

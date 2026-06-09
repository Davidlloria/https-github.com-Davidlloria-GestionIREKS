from __future__ import annotations

import argparse
import atexit
import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
API_HOST = "127.0.0.1"
API_PORT = 8000
FRONTEND_PORT = 5173

_children: list[subprocess.Popen[str]] = []
_cleaning_up = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the React + FastAPI desktop spike locally.")
    parser.add_argument("--api-host", default=API_HOST)
    parser.add_argument("--api-port", type=int, default=API_PORT)
    parser.add_argument("--frontend-port", type=int, default=FRONTEND_PORT)
    parser.add_argument("--startup-timeout", type=int, default=60)
    parser.add_argument("--hold-seconds", type=int, default=5)
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


def start_process(command: list[str], cwd: Path, extra_env: dict[str, str] | None = None) -> subprocess.Popen[str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    process = subprocess.Popen(command, cwd=str(cwd), env=env)
    _children.append(process)
    return process


def terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    if os.name == "nt":
        taskkill = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            check=False,
            capture_output=True,
            text=True,
        )
        if taskkill.returncode == 0:
            return

    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def cleanup() -> None:
    global _cleaning_up
    if _cleaning_up:
        return
    _cleaning_up = True
    for process in reversed(_children):
        terminate_process(process)


def handle_signal(_signum: int, _frame: object) -> None:
    cleanup()
    raise KeyboardInterrupt


def main() -> int:
    args = parse_args()

    if not FRONTEND_DIR.exists():
        print(f"No existe el directorio frontend: {FRONTEND_DIR}", file=sys.stderr)
        return 1

    if not FRONTEND_DIST.exists():
        print(
            "No existe frontend/dist.\n"
            "Ejecuta primero:\n"
            "  cd frontend\n"
            "  npm.cmd run build\n"
            "Luego vuelve a lanzar este script.",
            file=sys.stderr,
        )
        return 1

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
        str(FRONTEND_DIST),
    ]

    atexit.register(cleanup)
    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    print(f"Starting API on http://{args.api_host}:{args.api_port}")
    api_process = start_process(api_command, PROJECT_ROOT)

    if not wait_for_port(args.api_host, args.api_port, args.startup_timeout):
        cleanup()
        print("La API no levanto a tiempo.", file=sys.stderr)
        return 1
    if api_process.poll() is not None:
        cleanup()
        print(f"La API se cerro con codigo {api_process.returncode}.", file=sys.stderr)
        return 1

    print(f"Starting frontend on http://127.0.0.1:{args.frontend_port}")
    frontend_process = start_process(frontend_command, PROJECT_ROOT)

    if not wait_for_port("127.0.0.1", args.frontend_port, args.startup_timeout):
        cleanup()
        print("El frontend no levanto a tiempo.", file=sys.stderr)
        return 1
    if frontend_process.poll() is not None:
        cleanup()
        print(f"El frontend se cerro con codigo {frontend_process.returncode}.", file=sys.stderr)
        return 1

    frontend_url = f"http://127.0.0.1:{args.frontend_port}"
    print(f"Frontend ready: {frontend_url}")
    print(f"API ready: http://{args.api_host}:{args.api_port}")

    if not args.no_open_browser:
        webbrowser.open(frontend_url)

    if args.exit_after_start:
        time.sleep(max(0, args.hold_seconds))
        cleanup()
        return 0

    try:
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

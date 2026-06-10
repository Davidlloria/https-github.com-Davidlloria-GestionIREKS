from __future__ import annotations

import subprocess
import sys
from shutil import copytree, rmtree
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_FILE = ROOT / "react_desktop_launcher.spec"
FRONTEND_DIST = ROOT / "frontend" / "dist"


def main() -> int:
    if not SPEC_FILE.exists():
        print(f"No existe el spec de PyInstaller: {SPEC_FILE}", file=sys.stderr)
        return 1
    if not FRONTEND_DIST.exists():
        print(
            "No existe frontend/dist.\n"
            "Ejecuta primero:\n"
            "  cd frontend\n"
            "  npm.cmd run build",
            file=sys.stderr,
        )
        return 1

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(ROOT / "dist" / "react_desktop_pyinstaller"),
        "--workpath",
        str(ROOT / "build" / "react_desktop_pyinstaller"),
        str(SPEC_FILE),
    ]
    result = subprocess.run(command, cwd=str(ROOT))
    if result.returncode != 0:
        return result.returncode

    bundle_root = ROOT / "dist" / "react_desktop_pyinstaller" / "GestionIREKSReactDesktop"
    bundle_frontend_dist = bundle_root / "_internal" / "frontend" / "dist"
    if bundle_frontend_dist.exists():
        rmtree(bundle_frontend_dist)
    bundle_frontend_dist.parent.mkdir(parents=True, exist_ok=True)
    copytree(FRONTEND_DIST, bundle_frontend_dist)

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

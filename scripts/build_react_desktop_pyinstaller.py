from __future__ import annotations

import subprocess
import sys
from shutil import copy2, copytree, rmtree
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_FILE = ROOT / "react_desktop_launcher.spec"
FRONTEND_DIST = ROOT / "frontend" / "dist"
SOURCE_DB = ROOT / "data" / "gestion_ireks.db"


def stage_runtime_assets(bundle_root: Path) -> None:
    if not SOURCE_DB.exists():
        raise RuntimeError(f"No existe la base de datos real: {SOURCE_DB}")
    if SOURCE_DB.stat().st_size == 0:
        raise RuntimeError(f"La base de datos real esta vacia: {SOURCE_DB}")

    bundle_frontend_dist = bundle_root / "_internal" / "frontend" / "dist"
    if bundle_frontend_dist.exists():
        rmtree(bundle_frontend_dist)
    bundle_frontend_dist.parent.mkdir(parents=True, exist_ok=True)
    copytree(FRONTEND_DIST, bundle_frontend_dist)

    bundle_db = bundle_root / "data" / "gestion_ireks.db"
    if bundle_db.parent.exists() and bundle_db.is_file():
        bundle_db.unlink()
    bundle_db.parent.mkdir(parents=True, exist_ok=True)
    copy2(SOURCE_DB, bundle_db)
    for suffix in ("-wal", "-shm"):
        source_sidecar = SOURCE_DB.with_name(f"{SOURCE_DB.name}{suffix}")
        bundle_sidecar = bundle_db.with_name(f"{bundle_db.name}{suffix}")
        if source_sidecar.exists():
            copy2(source_sidecar, bundle_sidecar)
        elif bundle_sidecar.exists():
            bundle_sidecar.unlink()
    if bundle_db.stat().st_size == 0:
        raise RuntimeError(f"La base de datos empaquetada quedo vacia: {bundle_db}")


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
    stage_runtime_assets(bundle_root)

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

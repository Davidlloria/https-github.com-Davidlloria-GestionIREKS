"""Start the desktop UI without a console, preserving diagnostics."""
import os
from pathlib import Path
import runpy
import sys
import traceback


def main():
    root = Path(__file__).resolve().parent
    log_path = Path(sys.argv[1])
    data_dir = root.parent / "GestionIREKS-Datos"
    if (data_dir / "gestion_ireks.db").exists():
        os.environ.setdefault("GESTION_IREKS_DATA_DIR", str(data_dir))
    os.chdir(root)
    sys.argv = [str(root / "run.py")]
    with log_path.open("w", encoding="utf-8", buffering=1) as log:
        previous_stdout, previous_stderr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = log
        try:
            runpy.run_path(str(root / "run.py"), run_name="__main__")
        except Exception:
            traceback.print_exc()
            return 1
        finally:
            sys.stdout, sys.stderr = previous_stdout, previous_stderr
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

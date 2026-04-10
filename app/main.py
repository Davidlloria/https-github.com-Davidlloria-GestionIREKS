from pathlib import Path
import sys

# Allow direct execution: `python app/main.py`
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from app.core.database import init_db
from app.ui.main_window import MainWindow


def run() -> int:
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())

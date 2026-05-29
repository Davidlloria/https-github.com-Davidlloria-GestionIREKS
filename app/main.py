from pathlib import Path
import sys

# Allow direct execution: `python app/main.py`
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from app.core.database import init_db
from app.ui.main_window import MainWindow


def _load_global_stylesheet(app: QApplication) -> None:
    styles_path = Path(__file__).resolve().parents[1] / "assets" / "styles.qss"
    if not styles_path.exists():
        return
    app.setStyleSheet(styles_path.read_text(encoding="utf-8"))


def run() -> int:
    init_db()
    app = QApplication(sys.argv)
    _load_global_stylesheet(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())

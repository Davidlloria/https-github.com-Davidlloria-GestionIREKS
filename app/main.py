from pathlib import Path
import sys

# Allow direct execution: `python app/main.py`
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.core.database import init_db
from app.ui.main_window import MainWindow
from app.services.local_ai_service import OllamaModelLifecycle


def _load_global_stylesheet(app: QApplication) -> None:
    styles_path = Path(__file__).resolve().parents[1] / "assets" / "styles.qss"
    if not styles_path.exists():
        return
    app.setStyleSheet(styles_path.read_text(encoding="utf-8"))


def _connect_local_ai_lifecycle(app: QApplication) -> OllamaModelLifecycle:
    lifecycle = OllamaModelLifecycle()
    if not app.property("localAiLifecycleConnected"):
        app.setProperty("localAiLifecycleConnected", True)
        app._local_ai_lifecycle = lifecycle  # type: ignore[attr-defined]
        app.aboutToQuit.connect(lifecycle.unload)
        QTimer.singleShot(0, lifecycle.preload_async)
    return lifecycle


def run() -> int:
    init_db()
    app = QApplication(sys.argv)
    _load_global_stylesheet(app)
    lifecycle = _connect_local_ai_lifecycle(app)
    window = MainWindow()
    window.bind_local_ai_lifecycle(lifecycle)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())

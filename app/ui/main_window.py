from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from app.ui.widgets.customers_page import CustomersPage
from app.ui.widgets.ingredients_page import IngredientsIreksPage, IngredientsStdPage
from app.ui.widgets.placeholder_page import PlaceholderPage
from app.ui.widgets.recipes_page import RecipesPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Gestion Formulas - Panaderia/Pasteleria")
        self.resize(1300, 800)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)

        self.menu = QListWidget()
        self.menu.setMaximumWidth(250)
        self.menu.setSpacing(4)
        self.menu.setStyleSheet("QListWidget::item { padding: 10px; }")
        layout.addWidget(self.menu)

        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self._add_page("Clientes", CustomersPage())
        self._add_page("Ingredientes IREKS", IngredientsIreksPage())
        self._add_page("Materias primas", IngredientsStdPage())
        self._add_page("Recetas", RecipesPage())
        self._add_page(
            "Escandallos",
            PlaceholderPage("Escandallos", "Fase 3: calculo de costes, impresion y exportacion PDF."),
        )
        self._add_page(
            "Configuracion",
            PlaceholderPage("Configuracion", "Ajustes globales, impresoras y preferencias."),
        )

        self.menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.menu.setCurrentRow(0)

    def _add_page(self, name: str, widget: QWidget) -> None:
        self.pages.addWidget(widget)
        item = QListWidgetItem(name)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.menu.addItem(item)

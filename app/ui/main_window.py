import os

from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.config import USE_QML_CUSTOMERS
from app.ui.widgets.contacts_page import ContactsPage
from app.ui.widgets.courses_page import CoursesPage
from app.ui.widgets.customers_page import CustomersPage
from app.ui.widgets.distributors_page import DistributorsPage
from app.ui.widgets.ingredients_page import IngredientsIreksPage, IngredientsStdPage
from app.ui.widgets.orders_page import OrdersPage
from app.ui.widgets.placeholder_page import PlaceholderPage
from app.ui.widgets.recipes_page import RecipesPage
from app.ui.widgets.sales_page import SalesPage
from app.ui.widgets.settings_page import SettingsPage
from app.ui.widgets.technicians_page import TechniciansPage
from app.ui.widgets.warehouse_page import WarehousePage
try:
    from app.ui.qml_host import CustomersQmlPage
except Exception:  # noqa: BLE001
    CustomersQmlPage = None  # type: ignore[assignment]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Gestion IREKS")
        self.setMinimumSize(1180, 720)
        self.resize(1360, 840)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("mainRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.ribbon = self._build_ribbon()
        layout.addWidget(self.ribbon)

        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self._build_pages()
        self._build_ribbon_groups()
        self._set_current_page(0)

    def _build_ribbon(self) -> QWidget:
        ribbon = QFrame()
        ribbon.setObjectName("topRibbon")
        ribbon.setFrameShape(QFrame.Shape.StyledPanel)
        ribbon_layout = QHBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(12, 8, 12, 8)
        ribbon_layout.setSpacing(3)
        self.ribbon_layout = ribbon_layout
        self.ribbon_buttons = QButtonGroup(self)
        self.ribbon_buttons.setExclusive(True)
        return ribbon

    def _build_pages(self) -> None:
        self.page_names: list[str] = []
        self._add_page("Clientes", self._build_customers_page())
        self._add_page("Contactos", ContactsPage())
        self._add_page("Tecnicos", TechniciansPage())
        self._add_page("Distribuidores", DistributorsPage())
        self._add_page(
            "Colaboradores",
            PlaceholderPage("Colaboradores", "Gestion de colaboradores internos y externos."),
        )
        self._add_page("Cursos", CoursesPage())
        self._add_page("Formulas", RecipesPage())
        self._add_page("Almacen", WarehousePage())
        self._add_page("Productos IREKS", IngredientsIreksPage())
        self._add_page("Materias primas", IngredientsStdPage())
        self._add_page("Pedidos", OrdersPage())
        self._add_page("Ventas", SalesPage())
        self._add_page("Configuracion", SettingsPage())

    def _build_customers_page(self) -> QWidget:
        env_raw = os.getenv("USE_QML_CUSTOMERS")
        if env_raw is None:
            use_qml = bool(USE_QML_CUSTOMERS)
        else:
            use_qml = str(env_raw).strip().lower() in {"1", "true", "yes", "on"}
        if not use_qml or CustomersQmlPage is None:
            return CustomersPage()
        try:
            return CustomersQmlPage()
        except Exception:
            return CustomersPage()

    def _build_ribbon_groups(self) -> None:
        groups = [
            ["Clientes", "Contactos", "Tecnicos", "Distribuidores", "Colaboradores"],
            ["Cursos", "Formulas"],
            ["Almacen", "Productos IREKS", "Materias primas"],
            ["Pedidos", "Ventas"],
            ["Configuracion"],
        ]
        page_index_by_name = {name: idx for idx, name in enumerate(self.page_names)}

        for group_index, group in enumerate(groups):
            for name in group:
                self._add_ribbon_button(name, page_index_by_name[name])
            if group_index < len(groups) - 1:
                separator = QLabel("|")
                separator.setObjectName("ribbonSeparator")
                self.ribbon_layout.addWidget(separator)

        self.ribbon_layout.addStretch(1)

    def _add_page(self, name: str, widget: QWidget) -> None:
        self.pages.addWidget(widget)
        self.page_names.append(name)

    def _add_ribbon_button(self, text: str, page_index: int) -> None:
        button = QPushButton(text)
        button.setProperty("navButton", True)
        button.setCheckable(True)
        self._adjust_nav_button_width(button)
        button.clicked.connect(lambda _checked=False, i=page_index: self._set_current_page(i))
        self.ribbon_buttons.addButton(button, page_index)
        self.ribbon_layout.addWidget(button)

    def _adjust_nav_button_width(self, button: QPushButton) -> None:
        text_width = button.fontMetrics().horizontalAdvance(button.text())
        button.setMinimumWidth(text_width + 30)

    def _set_current_page(self, index: int) -> None:
        current_index = self.pages.currentIndex()
        if index == current_index:
            button = self.ribbon_buttons.button(index)
            if button is not None:
                button.setChecked(True)
            return

        self.pages.setCurrentIndex(index)
        button = self.ribbon_buttons.button(index)
        if button is not None:
            button.setChecked(True)
        page = self.pages.widget(index)
        self._refresh_page(page)

    def _refresh_page(self, page: QWidget) -> None:
        reload_fn = getattr(page, "reload", None)
        if callable(reload_fn):
            reload_fn()

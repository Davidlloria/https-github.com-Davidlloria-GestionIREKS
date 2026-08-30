import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.config import USE_QML_CUSTOMERS
from app.core.feature_flags import use_qml_customers_enabled
from app.ui.widgets.contacts_page import ContactsPage
from app.ui.widgets.dashboard_page import DashboardPage
from app.ui.widgets.courses_page import CoursesPage
from app.ui.widgets.customers_page import CustomersPage
from app.ui.widgets.distributors_page import DistributorsPage
from app.ui.widgets.document_library_page import DocumentLibraryPage
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
        self.setWindowTitle("Gestión IREKS")
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
        self.settings_page = SettingsPage(embedded=True)
        self.dashboard_page = DashboardPage(settings_page=self.settings_page)
        self._add_page("Inicio", self.dashboard_page)
        self._add_page("Clientes", self._build_customers_page())
        self._add_page("Contactos", ContactsPage())
        self._add_page("Tecnicos", TechniciansPage())
        self._add_page("Distribuidores", DistributorsPage())
        self._add_page(
            "Colaboradores",
            PlaceholderPage("Colaboradores", "Gestión de colaboradores internos y externos."),
        )
        self._add_page("Cursos", CoursesPage())
        self._add_page("Formulas", RecipesPage())
        self._add_page("Documentos", DocumentLibraryPage())
        self._add_page("Almacen", WarehousePage())
        self._add_page("Productos IREKS", IngredientsIreksPage())
        self._add_page("Materias primas", IngredientsStdPage())
        self._add_page("Pedidos", OrdersPage())
        self._add_page("Ventas", SalesPage())

    def bind_local_ai_lifecycle(self, lifecycle) -> None:
        self._local_ai_lifecycle = lifecycle
        self._local_ai_status_snapshot: tuple[str, str] | None = None
        self._local_ai_status_timer = QTimer(self)
        self._local_ai_status_timer.setInterval(250)
        self._local_ai_status_timer.timeout.connect(self._sync_local_ai_status)
        self._sync_local_ai_status()
        self._local_ai_status_timer.start()

    def _sync_local_ai_status(self) -> None:
        lifecycle = getattr(self, "_local_ai_lifecycle", None)
        if lifecycle is None:
            return
        snapshot = (
            str(getattr(lifecycle, "status_code", "unavailable")),
            str(getattr(lifecycle, "status", "IA local no disponible")),
        )
        if snapshot == self._local_ai_status_snapshot:
            return
        self._local_ai_status_snapshot = snapshot
        self.dashboard_page.set_local_ai_status(*snapshot)

    def _build_customers_page(self) -> QWidget:
        use_qml = use_qml_customers_enabled(
            os.getenv("USE_QML_CUSTOMERS"),
            default_flag=bool(USE_QML_CUSTOMERS),
        )
        if not use_qml or CustomersQmlPage is None:
            return CustomersPage()
        try:
            return CustomersQmlPage()
        except Exception:
            return CustomersPage()

    def _build_ribbon_groups(self) -> None:
        groups = [
            ["Inicio", "Clientes", "Contactos", "Tecnicos", "Distribuidores", "Colaboradores"],
            ["Cursos", "Formulas"],
            ["Almacen", "Productos IREKS", "Materias primas"],
            ["Pedidos", "Ventas", "Documentos"],
        ]
        ribbon_labels = {
            "Tecnicos": "Técnicos",
            "Formulas": "Fórmulas",
            "Almacen": "Almacén",
            "Productos IREKS": "Productos",
        }
        page_index_by_name = {name: idx for idx, name in enumerate(self.page_names)}

        ordered_names: list[str] = []
        for group in groups:
            ordered_names.extend(group)

        for name in ordered_names:
            self._add_ribbon_button(
                ribbon_labels.get(name, name),
                page_index_by_name[name],
            )

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
        button.ensurePolished()
        text_width = button.fontMetrics().horizontalAdvance(button.text())
        button.setMinimumWidth(max(text_width + 30, button.sizeHint().width()))

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

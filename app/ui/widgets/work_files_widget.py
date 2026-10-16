from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDir, QItemSelectionModel, QSortFilterProxyModel, QSize, Qt
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QKeySequence, QPainter, QPixmap, QShortcut, QTransform
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFileSystemModel, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QInputDialog, QLayout, QLineEdit, QListView, QMenu, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QStackedWidget, QToolButton, QTreeView, QVBoxLayout, QWidget,
)

from app.services.work_files_service import WorkFilesError, WorkFilesService


class _WorkFileModel(QFileSystemModel):
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and index.column() == 2 and self.isDir(index):
            return "Carpeta de archivos"
        return super().data(index, role)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ("Nombre", "Tamaño", "Tipo", "Fecha de modificación")[section] if section < 4 else None
        return super().headerData(section, orientation, role)


class _WorkPathFilter(QSortFilterProxyModel):
    def __init__(self, service: WorkFilesService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def filterAcceptsRow(self, row, parent):
        model = self.sourceModel()
        path = Path(model.filePath(model.index(row, 0, parent)))
        if path == self.service.root or self.service.root.is_relative_to(path):
            return True
        try:
            self.service.checked_path(path)
        except WorkFilesError:
            return False
        return super().filterAcceptsRow(row, parent)

    def lessThan(self, left, right):
        model = self.sourceModel()
        if model.isDir(left) != model.isDir(right):
            return model.isDir(left)
        return super().lessThan(left, right)


class WorkFilesWidget(QWidget):
    """Windows-style browser restricted to the installation's Trabajo folder."""

    def __init__(self, parent=None, *, service: WorkFilesService | None = None) -> None:
        super().__init__(parent)
        self.service = service or WorkFilesService()
        self.current_path = self.service.root
        self.history = [self.current_path]
        self.history_position = 0
        self.files_model = None
        self.tree_model = None
        self._pending_selection = None
        self._rebuilding_models = False
        self.setObjectName("workFilesRoot")
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        address_bar = QFrame()
        address_bar.setObjectName("workAddressBar")
        navigation = QHBoxLayout(address_bar)
        navigation.setContentsMargins(12, 10, 12, 10)
        navigation.setSpacing(4)
        self.back_button = self._navigation_button("Atrás · Alt+Izquierda", "chevron-right.svg", self.go_back, 180)
        self.forward_button = self._navigation_button("Adelante · Alt+Derecha", "chevron-right.svg", self.go_forward)
        self.up_button = self._navigation_button("Subir un nivel · Alt+Arriba", "arrow-up.svg", self.go_up)
        self.refresh_button = self._navigation_button("Actualizar · F5", "refresh-cw.svg", self.refresh)
        for button in (self.back_button, self.forward_button, self.up_button, self.refresh_button):
            navigation.addWidget(button)
        navigation.addSpacing(7)
        breadcrumb_host = QWidget()
        breadcrumb_host.setObjectName("workBreadcrumbHost")
        self.breadcrumbs = QHBoxLayout(breadcrumb_host)
        self.breadcrumbs.setContentsMargins(7, 0, 7, 0)
        self.breadcrumbs.setSpacing(0)
        self.breadcrumbs.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.breadcrumbs.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.breadcrumb_scroll = QScrollArea()
        self.breadcrumb_scroll.setObjectName("workBreadcrumbBar")
        self.breadcrumb_scroll.setWidgetResizable(True)
        self.breadcrumb_scroll.setWidget(breadcrumb_host)
        self.breadcrumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.breadcrumb_scroll.setFixedHeight(44)
        self.breadcrumb_scroll.setMinimumWidth(80)
        self.breadcrumb_scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        navigation.addWidget(self.breadcrumb_scroll, 1)
        navigation.addSpacing(7)
        self.filter_edit = QLineEdit()
        self.filter_edit.setObjectName("workSearch")
        self.filter_edit.setPlaceholderText("Filtrar esta carpeta")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setFixedSize(240, 40)
        self.filter_edit.addAction(self._icon("search-navy.svg", "#64748B"), QLineEdit.ActionPosition.LeadingPosition)
        self.filter_edit.textChanged.connect(self._filter_changed)
        navigation.addWidget(self.filter_edit)
        layout.addWidget(address_bar)

        command_bar = QFrame()
        command_bar.setObjectName("workCommandBar")
        self.actions_layout = QHBoxLayout(command_bar)
        self.actions_layout.setContentsMargins(12, 8, 12, 8)
        self.actions_layout.setSpacing(5)
        self.create_button = QPushButton("Nueva carpeta")
        self.create_button.setProperty("workRole", "primary")
        self.create_button.setIcon(self._icon("plus.svg", "#FFFFFF"))
        self.create_button.clicked.connect(self.create_folder)
        self.rename_button = QPushButton("Renombrar")
        self.rename_button.setIcon(self._icon("movement-edit-navy.svg"))
        self.rename_button.setToolTip("Renombrar · F2")
        self.rename_button.clicked.connect(self.rename_selected)
        self.move_button = QPushButton("Mover a…")
        self.move_button.setIcon(self._icon("export.svg"))
        self.move_button.clicked.connect(self.move_selected)
        self.recycle_button = QPushButton("Eliminar")
        self.recycle_button.setProperty("workRole", "danger")
        self.recycle_button.setIcon(self._icon("trash.svg", "#DC2626"))
        self.recycle_button.setToolTip("Enviar a la Papelera de Windows · Supr")
        self.recycle_button.clicked.connect(self.recycle_selected)
        self.actions_layout.addWidget(self.create_button)
        separator = QFrame()
        separator.setObjectName("workCommandSeparator")
        separator.setFixedSize(1, 22)
        self.actions_layout.addSpacing(7)
        self.actions_layout.addWidget(separator)
        self.actions_layout.addSpacing(7)
        for button in (self.rename_button, self.move_button, self.recycle_button):
            button.setEnabled(False)
            self.actions_layout.addWidget(button)
        self.actions_layout.addStretch()
        view_switch = QFrame()
        view_switch.setObjectName("workViewSwitch")
        views = QHBoxLayout(view_switch)
        views.setContentsMargins(3, 3, 3, 3)
        views.setSpacing(2)
        self.list_button = QToolButton()
        self.icons_button = QToolButton()
        for button, title, icon in ((self.list_button, "Lista", "list.svg"),
                                    (self.icons_button, "Iconos", "layout-dashboard.svg")):
            button.setCheckable(True)
            button.setToolTip(title)
            button.setAccessibleName(title)
            button.setIcon(self._icon(icon))
            button.setIconSize(QSize(18, 18))
            button.setFixedSize(30, 28)
            views.addWidget(button)
        self.list_button.setChecked(True)
        self.list_button.clicked.connect(lambda: self._set_view(False))
        self.icons_button.clicked.connect(lambda: self._set_view(True))
        self.actions_layout.addWidget(view_switch)
        self.actions_layout.addSpacing(8)
        self.details_button = QPushButton("Detalles")
        self.details_button.setIcon(self._icon("file-text.svg"))
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._toggle_details)
        self.actions_layout.addWidget(self.details_button)
        for button in (self.create_button, self.rename_button, self.move_button,
                       self.recycle_button, self.details_button):
            button.setFixedHeight(34)
            button.setIconSize(QSize(18, 18))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(command_bar)

        self.message = QLabel()
        self.message.setObjectName("workMessage")
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.splitter = QSplitter()
        self.splitter.setObjectName("workBrowserSplitter")
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)
        folders = QWidget()
        folders.setObjectName("workFolderPane")
        folders.setMinimumWidth(170)
        folders.setMaximumWidth(300)
        folder_layout = QVBoxLayout(folders)
        folder_layout.setContentsMargins(8, 14, 8, 8)
        folder_layout.setSpacing(8)
        folder_caption = QLabel("CARPETAS")
        folder_caption.setObjectName("workFolderCaption")
        folder_layout.addWidget(folder_caption)
        self.tree = QTreeView()
        self.tree.setObjectName("workFolderTree")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(18)
        self.tree.setIconSize(QSize(18, 18))
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.clicked.connect(self._tree_clicked)
        folder_layout.addWidget(self.tree, 1)
        self.splitter.addWidget(folders)

        self.file_views = QStackedWidget()
        self.file_views.setObjectName("workFileViews")
        self.file_views.setMinimumWidth(260)
        self.list_view = QTreeView()
        self.list_view.setObjectName("workFileList")
        self.list_view.setRootIsDecorated(False)
        self.list_view.setItemsExpandable(False)
        self.list_view.setSortingEnabled(True)
        self.list_view.setIconSize(QSize(20, 20))
        self.icons_view = QListView()
        self.icons_view.setObjectName("workFileIcons")
        self.icons_view.setViewMode(QListView.ViewMode.IconMode)
        self.icons_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.icons_view.setMovement(QListView.Movement.Static)
        self.icons_view.setIconSize(QSize(48, 48))
        self.icons_view.setGridSize(QSize(160, 112))
        self.icons_view.setWordWrap(True)
        for view in (self.list_view, self.icons_view):
            view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            view.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
            view.activated.connect(self._activate)
            view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            view.customContextMenuRequested.connect(lambda point, target=view: self._context_menu(target, point))
            self.file_views.addWidget(view)
        self.splitter.addWidget(self.file_views)

        self.details = QWidget()
        self.details.setObjectName("workDetailsPane")
        self.details.setMinimumWidth(210)
        self.details.setMaximumWidth(270)
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(20, 18, 20, 18)
        details_layout.setSpacing(14)
        details_caption = QLabel("DETALLES")
        details_caption.setObjectName("workDetailsCaption")
        details_layout.addWidget(details_caption)
        self.details_icon = QLabel()
        self.details_icon.setFixedHeight(72)
        self.details_name = QLabel("Selecciona un archivo o una carpeta")
        self.details_name.setObjectName("workDetailsName")
        self.details_info = QLabel()
        self.details_info.setObjectName("workDetailsInfo")
        for label in (self.details_name, self.details_info):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self.details_icon)
        details_layout.addWidget(self.details_name)
        details_layout.addWidget(self.details_info)
        self.open_button = QPushButton("Abrir")
        self.open_button.setProperty("workRole", "primary")
        self.open_button.setIcon(self._icon("folder-open-navy.svg", "#FFFFFF"))
        self.open_button.clicked.connect(self.open_selected)
        details_layout.addWidget(self.open_button)
        details_layout.addStretch()
        self.splitter.addWidget(self.details)
        self.details.hide()
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([210, 740, 240])
        layout.addWidget(self.splitter, 1)

        footer = QFrame()
        footer.setObjectName("workStatusBar")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 5, 12, 5)
        self.status = QLabel()
        self.status.setObjectName("workStatusText")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        footer_layout.addWidget(self.status)
        footer_layout.addStretch()
        self.open_windows_button = QPushButton("Abrir en Windows")
        self.open_windows_button.setProperty("workRole", "link")
        self.open_windows_button.setIcon(self._icon("folder-open-navy.svg", "#2563EB"))
        self.open_windows_button.setFixedHeight(30)
        self.open_windows_button.clicked.connect(self.open_in_windows)
        footer_layout.addWidget(self.open_windows_button)
        layout.addWidget(footer)
        for key, callback in (("Alt+Left", self.go_back), ("Alt+Right", self.go_forward),
                              ("Alt+Up", self.go_up), ("F5", self.refresh), ("F2", self.rename_selected)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
        delete_shortcut = QShortcut(QKeySequence("Delete"), self.file_views)
        delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        delete_shortcut.activated.connect(self.recycle_selected)
        self._apply_work_styles()
        self.open_button.ensurePolished()
        self.open_button.setFixedHeight(36)

    def _icon(self, asset, color="#475569", rotation=0):
        path = Path(__file__).resolve().parents[3] / "assets" / "icons" / asset
        renderer = QSvgRenderer(str(path))
        icon = QIcon()
        for mode, tint in ((QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, "#AEB8C7")):
            pixmap = QPixmap(36, 36)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), QColor(tint))
            painter.end()
            if rotation:
                pixmap = pixmap.transformed(QTransform().rotate(rotation), Qt.TransformationMode.SmoothTransformation)
            pixmap.setDevicePixelRatio(2)
            icon.addPixmap(pixmap, mode)
        return icon

    def _navigation_button(self, title, asset, callback, rotation=0):
        button = QToolButton()
        button.setObjectName("workNavigationButton")
        button.setToolTip(title)
        button.setAccessibleName(title)
        button.setFixedSize(32, 32)
        button.setIcon(self._icon(asset, rotation=rotation))
        button.setIconSize(QSize(18, 18))
        button.clicked.connect(callback)
        return button

    def _apply_work_styles(self):
        self.setStyleSheet("""
            QWidget#workFilesRoot { background: #FFFFFF; border: 1px solid #DCE4EF; border-radius: 12px; }
            QWidget#workFilesRoot QLabel { background: transparent; border: none; }
            QFrame#workAddressBar { background: transparent; border: none; border-bottom: 1px solid #EDF1F6; }
            QFrame#workCommandBar { background: #FFFFFF; border: none; border-bottom: 1px solid #E4EAF2; }
            QFrame#workCommandSeparator { background: #E2E8F0; border: none; }
            QWidget#workFilesRoot QPushButton {
                background: transparent; color: #475569; border: 1px solid transparent;
                border-radius: 6px; padding: 0 8px; min-height: 0; font-size: 13px;
            }
            QWidget#workFilesRoot QPushButton:hover { background: #F1F5F9; color: #0F172A; }
            QWidget#workFilesRoot QPushButton:pressed { background: #E2E8F0; }
            QWidget#workFilesRoot QPushButton:disabled { color: #A0AABB; background: transparent; }
            QWidget#workFilesRoot QPushButton[workRole="primary"] {
                background: #2563EB; color: #FFFFFF; font-weight: 600; border-color: #2563EB; padding: 0 13px;
            }
            QWidget#workFilesRoot QPushButton[workRole="primary"]:hover { background: #1D4ED8; border-color: #1D4ED8; }
            QWidget#workFilesRoot QPushButton[workRole="primary"]:disabled { background: #E2E8F0; border-color: #E2E8F0; color: #94A3B8; }
            QWidget#workFilesRoot QPushButton[workRole="danger"] { color: #DC2626; }
            QWidget#workFilesRoot QPushButton[workRole="danger"]:hover { background: #FEF2F2; }
            QWidget#workFilesRoot QPushButton[workRole="danger"]:disabled { color: #A0AABB; }
            QWidget#workFilesRoot QPushButton[workRole="link"] { color: #2563EB; font-size: 12px; }
            QWidget#workFilesRoot QPushButton[workRole="link"]:disabled { color: #A0AABB; }
            QWidget#workFilesRoot QPushButton:checked { color: #1D4ED8; background: #EFF6FF; border-color: #BFDBFE; }
            QWidget#workFilesRoot QToolButton {
                background: transparent; border: none; border-radius: 5px;
                padding: 0; min-height: 0; min-width: 0; color: #475569;
            }
            QWidget#workFilesRoot QToolButton:hover { background: #E9EFF7; }
            QWidget#workFilesRoot QToolButton:disabled { background: transparent; color: #AEB8C7; }
            QFrame#workViewSwitch { background: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 7px; }
            QFrame#workViewSwitch QToolButton:checked { background: #FFFFFF; border: 1px solid #D8E2F0; }
            QScrollArea#workBreadcrumbBar { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 7px; }
            QWidget#workBreadcrumbHost { background: transparent; border: none; }
            QWidget#workBreadcrumbHost QToolButton { padding: 0 7px; min-height: 24px; }
            QLineEdit#workSearch {
                background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 7px;
                padding: 0 8px; min-height: 0; color: #334155; selection-background-color: #DBEAFE;
            }
            QLineEdit#workSearch:focus { border-color: #93B4F5; background: #FFFFFF; }
            QWidget#workFolderPane { background: #FAFBFD; border: none; }
            QLabel#workFolderCaption, QLabel#workDetailsCaption { color: #8A98AC; font-size: 10px; font-weight: 700; padding: 0 10px; }
            QStackedWidget#workFileViews { background: #FFFFFF; border: none; }
            QSplitter#workBrowserSplitter::handle { background: #E7EDF4; }
            QWidget#workFilesRoot QTreeView, QWidget#workFilesRoot QListView {
                background: #FFFFFF; border: none; outline: none; color: #334155;
                selection-background-color: #E8F0FE; selection-color: #183E78;
            }
            QTreeView#workFolderTree { background: transparent; }
            QTreeView#workFolderTree::item { min-height: 24px; padding: 4px 2px; border-radius: 5px; }
            QTreeView#workFileList::item { min-height: 28px; padding: 4px 5px; border: none; }
            QWidget#workFilesRoot QTreeView::item:hover { background: #F0F5FC; }
            QWidget#workFilesRoot QTreeView::item:selected { background: #E8F0FE; color: #183E78; }
            QWidget#workFilesRoot QHeaderView { background: #F8FAFC; border: none; }
            QWidget#workFilesRoot QHeaderView::section {
                background: #F8FAFC; color: #64748B; font-size: 12px; font-weight: 600;
                padding: 10px 8px; border: none; border-bottom: 1px solid #E7EDF4;
            }
            QListView#workFileIcons { padding: 12px; }
            QListView#workFileIcons::item { padding: 9px; border: 1px solid transparent; border-radius: 8px; }
            QListView#workFileIcons::item:hover { background: #F3F7FD; border-color: #E2EAF6; }
            QListView#workFileIcons::item:selected { background: #E8F0FE; border-color: #B9CFF3; }
            QWidget#workDetailsPane { background: #F8FAFC; border: none; }
            QLabel#workDetailsCaption { padding: 0; }
            QLabel#workDetailsName { color: #1E293B; font-size: 14px; font-weight: 600; }
            QLabel#workDetailsInfo { color: #64748B; font-size: 12px; }
            QLabel#workMessage { color: #92400E; background: #FFFBEB; padding: 18px; }
            QFrame#workStatusBar { background: #FAFBFD; border: none; border-top: 1px solid #E7EDF4; }
            QLabel#workStatusText { color: #7B8A9E; font-size: 12px; }
            QMenu#workContextMenu { background: #FFFFFF; border: 1px solid #DCE4EF; padding: 5px; }
            QMenu#workContextMenu::item { padding: 8px 24px 8px 12px; border-radius: 4px; }
            QMenu#workContextMenu::item:selected { background: #EFF6FF; color: #1D4ED8; }
            QMenu#workContextMenu::separator { height: 1px; background: #E7EDF4; margin: 4px 8px; }
        """)

    def _install_models(self):
        self._rebuilding_models = True
        try:
            self._replace_models()
        finally:
            self._rebuilding_models = False

    def _replace_models(self):
        old_models = (getattr(self, "files_proxy", None), getattr(self, "tree_proxy", None),
                      self.files_model, self.tree_model)
        # Detach both views and their shared selection before replacing proxies.
        # Qt can emit selection/reset signals synchronously during setModel().
        self.list_view.setModel(None)
        self.icons_view.setModel(None)
        self.tree.setModel(None)
        for prefix, directories_only in (("tree", True), ("files", False)):
            model = _WorkFileModel(self)
            model.setReadOnly(True)
            # Native directory watchers can prevent Windows from renaming a visited
            # folder (or its ancestors). Mutations rebuild these models; external
            # changes are picked up with Actualizar/F5.
            model.setOption(QFileSystemModel.Option.DontWatchForChanges, True)
            model.setOption(QFileSystemModel.Option.DontResolveSymlinks, True)
            flags = QDir.Filter.NoDotAndDotDot | QDir.Filter.NoSymLinks
            flags |= QDir.Filter.Dirs if directories_only else QDir.Filter.AllEntries
            model.setFilter(flags)
            proxy = _WorkPathFilter(self.service, self)
            proxy.setSourceModel(model)
            model.setRootPath(str(self.service.root))
            setattr(self, prefix + "_model", model)
            setattr(self, prefix + "_proxy", proxy)
        self.tree.setModel(self.tree_proxy)
        for column in range(1, 4):
            self.tree.hideColumn(column)
        parent = self.tree_model.index(str(self.service.root.parent))
        self.tree.setRootIndex(self.tree_proxy.mapFromSource(parent))
        self.tree.expand(self.tree_proxy.mapFromSource(self.tree_model.index(str(self.service.root))))
        self.list_view.setModel(self.files_proxy)
        self.icons_view.setModel(self.files_proxy)
        self.icons_view.setSelectionModel(self.list_view.selectionModel())
        self.list_view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.list_view.header().moveSection(self.list_view.header().visualIndex(3), 1)
        self.list_view.header().moveSection(self.list_view.header().visualIndex(2), 2)
        for column in (1, 2, 3):
            self.list_view.header().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.list_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.list_view.selectionModel().selectionChanged.connect(self._update_selection)
        self.files_model.directoryLoaded.connect(self._update_status)
        self.files_proxy.rowsInserted.connect(self._update_status)
        self.files_proxy.rowsRemoved.connect(self._update_status)
        self.files_proxy.layoutChanged.connect(self._update_status)
        for model in old_models:
            if model is not None:
                model.deleteLater()

    def refresh(self):
        try:
            self.service.checked_path(self.service.root, directory=True)
            target = self.current_path
            while target != self.service.root:
                try:
                    self.service.checked_path(target, directory=True)
                    break
                except WorkFilesError:
                    target = target.parent
            self._install_models()
            self.splitter.show()
            self.navigate(target, record=False)
            self.message.hide()
        except (WorkFilesError, OSError) as exc:
            self.splitter.hide()
            self.message.setText(f"No se puede abrir Trabajo. {exc}\nUbicación: {self.service.root}")
            self.message.show()
            self.open_windows_button.setEnabled(False)
            for button in (self.rename_button, self.move_button, self.recycle_button):
                button.setEnabled(False)
            self._pending_selection = None
            self.status.setText("Carpeta no disponible")
            self._update_navigation()

    def navigate(self, path, *, record=True):
        try:
            path = self.service.checked_path(path, directory=True)
        except WorkFilesError as exc:
            QMessageBox.warning(self, "Trabajo", str(exc))
            return False
        self.current_path = path
        if record and self.history[self.history_position] != path:
            self.history = self.history[:self.history_position + 1] + [path]
            self.history_position += 1
        self.filter_edit.clear()
        index = self.files_proxy.mapFromSource(self.files_model.setRootPath(str(path)))
        self.list_view.setRootIndex(index)
        self.icons_view.setRootIndex(index)
        self.list_view.selectionModel().clear()
        tree_index = self.tree_proxy.mapFromSource(self.tree_model.index(str(path)))
        self.tree.setCurrentIndex(tree_index)
        self.tree.expand(tree_index)
        self._update_navigation()
        self._update_selection()
        self._update_status()
        return True

    def _update_navigation(self):
        available = self.service.root.is_dir() and self.splitter.isVisibleTo(self)
        self.back_button.setEnabled(available and self.history_position > 0)
        self.forward_button.setEnabled(available and self.history_position < len(self.history) - 1)
        self.up_button.setEnabled(available and self.current_path != self.service.root)
        self.open_windows_button.setEnabled(available)
        self.create_button.setEnabled(available)
        self.breadcrumb_scroll.setToolTip(str(self.current_path))
        while self.breadcrumbs.count():
            item = self.breadcrumbs.takeAt(0)
            item.widget().deleteLater()
        paths = [self.service.root]
        if self.current_path.is_relative_to(self.service.root):
            for part in self.current_path.relative_to(self.service.root).parts:
                paths.append(paths[-1] / part)
        for index, path in enumerate(paths):
            button = QToolButton()
            button.setText(("Trabajo" if index == 0 else path.name) + (" ›" if index < len(paths) - 1 else ""))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setToolTip(str(path))
            button.clicked.connect(lambda _checked=False, target=path: self.navigate(target))
            self.breadcrumbs.addWidget(button)
            button.ensurePolished()
            button.setFixedSize(max(40, button.fontMetrics().horizontalAdvance(button.text()) + 20), 24)

    def go_back(self):
        self._go_history(-1)

    def go_forward(self):
        self._go_history(1)

    def _go_history(self, step):
        position = self.history_position + step
        if 0 <= position < len(self.history) and self.navigate(self.history[position], record=False):
            self.history_position = position
            self._update_navigation()

    def go_up(self):
        if self.current_path != self.service.root:
            self.navigate(self.current_path.parent)

    def _tree_clicked(self, index):
        if not index.isValid() or index.model() is not self.tree_proxy:
            return
        self.navigate(self.tree_model.filePath(self.tree_proxy.mapToSource(index)))

    def _selected_path(self):
        if (self._rebuilding_models or self.files_model is None
                or self.list_view.model() is not self.files_proxy):
            return None
        rows = self.list_view.selectionModel().selectedRows(0)
        if not rows or rows[0].model() is not self.files_proxy:
            return None
        return Path(self.files_model.filePath(self.files_proxy.mapToSource(rows[0])))

    def _activate(self, index):
        if not index.isValid() or index.model() is not self.files_proxy:
            return
        path = Path(self.files_model.filePath(self.files_proxy.mapToSource(index.siblingAtColumn(0))))
        self._open_path(path)

    def open_selected(self):
        path = self._selected_path()
        if path is not None:
            self._open_path(path)

    def _open_path(self, path):
        try:
            path = self.service.checked_path(path)
            if path.is_dir():
                self.navigate(path)
            elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise WorkFilesError("Windows no ha podido abrir el archivo.")
        except WorkFilesError as exc:
            QMessageBox.warning(self, "Trabajo", str(exc))

    def open_in_windows(self):
        try:
            path = self.service.checked_path(self.current_path, directory=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise WorkFilesError("Windows no ha podido abrir la carpeta.")
        except WorkFilesError as exc:
            QMessageBox.warning(self, "Trabajo", str(exc))

    def _set_view(self, icons):
        self.file_views.setCurrentIndex(1 if icons else 0)
        self.icons_button.setChecked(icons)
        self.list_button.setChecked(not icons)

    def _filter_changed(self, text):
        if not self._rebuilding_models and self.files_model is not None:
            self.files_proxy.setFilterFixedString(text)
            self._update_selection()
            self._update_status()

    def _update_status(self, *_args):
        if (not self._rebuilding_models and self.files_model is not None
                and self.list_view.model() is self.files_proxy):
            count = self.files_proxy.rowCount(self.list_view.rootIndex())
            self.status.setText(f"{count} {'elemento' if count == 1 else 'elementos'}" if count else "Carpeta vacía o sin coincidencias")
            if self._pending_selection is not None:
                index = self.files_proxy.mapFromSource(self.files_model.index(str(self._pending_selection)))
                if index.isValid():
                    self._pending_selection = None
                    self.list_view.selectionModel().setCurrentIndex(
                        index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
                    )
                    self.list_view.scrollTo(index)

    def create_folder(self):
        name, accepted = QInputDialog.getText(self, "Nueva carpeta", "Nombre de la carpeta:")
        if not accepted:
            return
        try:
            path = self.service.create_folder(self.current_path, name)
            self._refresh_after_change(path)
        except WorkFilesError as exc:
            QMessageBox.warning(self, "Nueva carpeta", str(exc))

    def _refresh_after_change(self, selected=None):
        self.refresh()
        self._pending_selection = selected
        self._update_status()

    def rename_selected(self):
        path = self._selected_path()
        if path is None:
            return
        name, accepted = QInputDialog.getText(self, "Renombrar", "Nuevo nombre:", text=path.name)
        if not accepted:
            return
        if path.is_file() and path.suffix and path.suffix.lower() != Path(name).suffix.lower():
            answer = QMessageBox.question(
                self, "Cambiar extensión", "Cambiar la extensión puede impedir abrir el archivo. ¿Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self._refresh_after_change(self.service.rename(path, name))
        except WorkFilesError as exc:
            QMessageBox.warning(self, "Renombrar", str(exc))

    def _choose_destination(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Mover a…")
        dialog.resize(520, 440)
        layout = QVBoxLayout(dialog)
        caption = QLabel("Selecciona la carpeta de destino dentro de Trabajo.")
        layout.addWidget(caption)
        tree = QTreeView()
        tree.setObjectName("workMoveDestinationTree")
        tree.setModel(self.tree_proxy)
        tree.setHeaderHidden(True)
        tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for column in range(1, 4):
            tree.hideColumn(column)
        root_index = self.tree_proxy.mapFromSource(self.tree_model.index(str(self.service.root)))
        tree.setRootIndex(root_index.parent())
        tree.expand(root_index)
        tree.setCurrentIndex(root_index)
        layout.addWidget(tree, 1)
        destination_label = QLabel("Trabajo")
        destination_label.setTextFormat(Qt.TextFormat.PlainText)
        destination_label.setWordWrap(True)
        layout.addWidget(destination_label)
        selected = [self.service.root]

        def update_destination(index, _previous):
            try:
                if not index.isValid() or index.model() is not self.tree_proxy:
                    raise WorkFilesError("Selecciona una carpeta.")
                selected[0] = self.service.checked_path(
                    self.tree_model.filePath(self.tree_proxy.mapToSource(index)), directory=True,
                )
                destination_label.setText("Trabajo / " + str(selected[0].relative_to(self.service.root)))
                buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            except WorkFilesError:
                selected[0] = None
                destination_label.setText("La carpeta de destino ya no está disponible.")
                buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

        tree.selectionModel().currentChanged.connect(update_destination)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Mover aquí")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return selected[0] if dialog.exec() == QDialog.DialogCode.Accepted else None

    def move_selected(self):
        path = self._selected_path()
        if path is None:
            return
        destination = self._choose_destination()
        if destination is None:
            return
        try:
            self.service.move(path, destination)
            self._refresh_after_change()
        except WorkFilesError as exc:
            QMessageBox.warning(self, "Mover", str(exc))

    def recycle_selected(self):
        path = self._selected_path()
        if path is None:
            return
        content_note = " y su contenido" if path.is_dir() else ""
        answer = QMessageBox.question(
            self, "Enviar a la Papelera",
            f"Se enviará «{path.name}»{content_note} a la Papelera de Windows.\n"
            "Podrás restaurarlo desde allí.\n\n¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.recycle(path)
            self._refresh_after_change()
        except WorkFilesError as exc:
            QMessageBox.warning(self, "Papelera", str(exc))

    def _toggle_details(self, visible):
        self.details.setVisible(visible)
        self._update_selection()

    def _update_selection(self, *_args):
        if self._rebuilding_models:
            return
        path = self._selected_path()
        self.open_button.setEnabled(path is not None)
        self.rename_button.setEnabled(False)
        self.move_button.setEnabled(False)
        self.recycle_button.setEnabled(False)
        self.details_icon.clear()
        self.details_name.setText(path.name if path else "Selecciona un archivo o una carpeta")
        self.details_info.clear()
        if path:
            try:
                self.service.checked_path(path)
                self.rename_button.setEnabled(path != self.service.root)
                self.move_button.setEnabled(path != self.service.root)
                self.recycle_button.setEnabled(path != self.service.root)
                index = self.files_model.index(str(path))
                self.details_icon.setPixmap(self.files_model.fileIcon(index).pixmap(64, 64))
                kind = self.files_model.data(index.siblingAtColumn(2))
                self.details_info.setText(f"{kind}\n\nUbicación:\nTrabajo / {path.relative_to(self.service.root)}")
            except WorkFilesError:
                self.open_button.setEnabled(False)

    def _context_menu(self, view, point):
        index = view.indexAt(point)
        menu = QMenu(self)
        menu.setObjectName("workContextMenu")
        menu.addAction(self._icon("plus.svg"), "Nueva carpeta", self.create_folder).setEnabled(self.create_button.isEnabled())
        if index.isValid():
            view.setCurrentIndex(index)
            menu.addSeparator()
            menu.addAction(self._icon("folder-open-navy.svg"), "Abrir", self.open_selected)
            menu.addAction(self.rename_button.icon(), "Renombrar", self.rename_selected).setEnabled(self.rename_button.isEnabled())
            menu.addAction(self.move_button.icon(), "Mover a…", self.move_selected).setEnabled(self.move_button.isEnabled())
            menu.addSeparator()
            menu.addAction(self.recycle_button.icon(), "Enviar a la Papelera", self.recycle_selected).setEnabled(self.recycle_button.isEnabled())
        menu.exec(view.viewport().mapToGlobal(point))

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDir, QItemSelectionModel, QModelIndex, QSortFilterProxyModel, QSize, Qt
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFileSystemModel, QHBoxLayout, QHeaderView, QLabel,
    QInputDialog, QLineEdit, QListView, QMenu, QMessageBox, QPushButton, QSplitter,
    QStackedWidget, QStyle, QToolButton, QTreeView, QVBoxLayout, QWidget,
)

from app.services.work_files_service import WorkFilesError, WorkFilesService


class _WorkFileModel(QFileSystemModel):
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
        self.setObjectName("workFilesRoot")
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.actions_layout = QHBoxLayout()
        self.create_button = QPushButton("Nueva carpeta")
        self.create_button.clicked.connect(self.create_folder)
        self.actions_layout.addWidget(self.create_button)
        self.rename_button = QPushButton("Renombrar")
        self.rename_button.setEnabled(False)
        self.rename_button.clicked.connect(self.rename_selected)
        self.actions_layout.addWidget(self.rename_button)
        self.move_button = QPushButton("Mover a…")
        self.move_button.setEnabled(False)
        self.move_button.clicked.connect(self.move_selected)
        self.actions_layout.addWidget(self.move_button)
        self.recycle_button = QPushButton("Eliminar")
        self.recycle_button.setToolTip("Enviar a la Papelera de Windows")
        self.recycle_button.setEnabled(False)
        self.recycle_button.clicked.connect(self.recycle_selected)
        self.actions_layout.addWidget(self.recycle_button)
        self.actions_layout.addStretch()
        self.open_windows_button = QPushButton("Abrir en Windows")
        self.open_windows_button.clicked.connect(self.open_in_windows)
        self.actions_layout.addWidget(self.open_windows_button)
        layout.addLayout(self.actions_layout)

        navigation = QHBoxLayout()
        self.back_button = self._navigation_button("Atrás", QStyle.StandardPixmap.SP_ArrowBack, self.go_back)
        self.forward_button = self._navigation_button("Adelante", QStyle.StandardPixmap.SP_ArrowForward, self.go_forward)
        self.up_button = self._navigation_button("Subir un nivel", QStyle.StandardPixmap.SP_ArrowUp, self.go_up)
        self.refresh_button = self._navigation_button("Actualizar", QStyle.StandardPixmap.SP_BrowserReload, self.refresh)
        for button in (self.back_button, self.forward_button, self.up_button, self.refresh_button):
            navigation.addWidget(button)
        self.breadcrumbs = QHBoxLayout()
        self.breadcrumbs.setSpacing(2)
        navigation.addLayout(self.breadcrumbs, 1)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filtrar esta carpeta")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMaximumWidth(260)
        self.filter_edit.textChanged.connect(self._filter_changed)
        navigation.addWidget(self.filter_edit)
        layout.addLayout(navigation)

        views = QHBoxLayout()
        views.addStretch()
        self.list_button = QPushButton("Lista")
        self.icons_button = QPushButton("Iconos")
        self.details_button = QPushButton("Detalles")
        for button in (self.list_button, self.icons_button, self.details_button):
            button.setCheckable(True)
            views.addWidget(button)
        self.list_button.setChecked(True)
        self.list_button.clicked.connect(lambda: self._set_view(False))
        self.icons_button.clicked.connect(lambda: self._set_view(True))
        self.details_button.toggled.connect(self._toggle_details)
        layout.addLayout(views)

        self.message = QLabel()
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.splitter = QSplitter()
        self.tree = QTreeView()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(150)
        self.tree.setMaximumWidth(350)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.clicked.connect(self._tree_clicked)
        self.splitter.addWidget(self.tree)
        self.file_views = QStackedWidget()
        self.list_view = QTreeView()
        self.list_view.setRootIsDecorated(False)
        self.list_view.setItemsExpandable(False)
        self.list_view.setSortingEnabled(True)
        self.list_view.setAlternatingRowColors(True)
        self.icons_view = QListView()
        self.icons_view.setViewMode(QListView.ViewMode.IconMode)
        self.icons_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.icons_view.setMovement(QListView.Movement.Static)
        self.icons_view.setIconSize(QSize(48, 48))
        self.icons_view.setGridSize(QSize(180, 100))
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
        self.details.setMinimumWidth(180)
        self.details.setMaximumWidth(260)
        details_layout = QVBoxLayout(self.details)
        self.details_icon = QLabel()
        self.details_name = QLabel("Selecciona un archivo o una carpeta")
        self.details_info = QLabel()
        for label in (self.details_name, self.details_info):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self.details_icon)
        details_layout.addWidget(self.details_name)
        details_layout.addWidget(self.details_info)
        self.open_button = QPushButton("Abrir")
        self.open_button.clicked.connect(self.open_selected)
        details_layout.addWidget(self.open_button)
        details_layout.addStretch()
        self.splitter.addWidget(self.details)
        self.details.hide()
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([210, 650, 220])
        layout.addWidget(self.splitter, 1)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        for key, callback in (("Alt+Left", self.go_back), ("Alt+Right", self.go_forward),
                              ("Alt+Up", self.go_up), ("F5", self.refresh), ("F2", self.rename_selected)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
        delete_shortcut = QShortcut(QKeySequence("Delete"), self.file_views)
        delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        delete_shortcut.activated.connect(self.recycle_selected)
        self.setStyleSheet("""
            QWidget#workFilesRoot QTreeView, QWidget#workFilesRoot QListView {
                background: white; border: 1px solid #DCE4EF; border-radius: 6px;
                selection-background-color: #DBEAFE; selection-color: #0F172A;
                alternate-background-color: #F8FAFC;
            }
            QWidget#workFilesRoot QTreeView::item { min-height: 30px; }
            QWidget#workFilesRoot QHeaderView::section { background: #F4F6F9; padding: 7px; border: none; }
            QWidget#workFilesRoot QPushButton, QWidget#workFilesRoot QToolButton {
                background: white; border: 1px solid #CBD5E1; border-radius: 6px; padding: 7px 10px;
            }
            QWidget#workFilesRoot QPushButton:checked { background: #DBEAFE; color: #1D4ED8; }
            QWidget#workFilesRoot QPushButton:disabled { color: #94A3B8; }
            QWidget#workFilesRoot QLineEdit { background: white; padding: 8px; border: 1px solid #CBD5E1; border-radius: 6px; }
        """)

    def _navigation_button(self, title, icon, callback):
        button = QToolButton()
        button.setToolTip(title)
        button.setAccessibleName(title)
        button.setIcon(self.style().standardIcon(icon))
        button.clicked.connect(callback)
        return button

    def _install_models(self):
        old_models = (getattr(self, "files_proxy", None), getattr(self, "tree_proxy", None),
                      self.files_model, self.tree_model)
        for prefix, directories_only in (("tree", True), ("files", False)):
            model = _WorkFileModel(self)
            model.setReadOnly(True)
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
            button.setToolTip(str(path))
            button.clicked.connect(lambda _checked=False, target=path: self.navigate(target))
            self.breadcrumbs.addWidget(button)

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
        self.navigate(self.tree_model.filePath(self.tree_proxy.mapToSource(index)))

    def _selected_path(self):
        if self.files_model is None:
            return None
        rows = self.list_view.selectionModel().selectedRows(0)
        return Path(self.files_model.filePath(self.files_proxy.mapToSource(rows[0]))) if rows else None

    def _activate(self, index):
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
        if self.files_model is not None:
            self.files_proxy.setFilterFixedString(text)
            self._update_selection()
            self._update_status()

    def _update_status(self, *_args):
        if self.files_model is not None:
            count = self.files_proxy.rowCount(self.list_view.rootIndex())
            self.status.setText(f"{count} elemento(s)" if count else "Carpeta vacía o sin coincidencias")
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
                if not index.isValid():
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
                self.details_info.setText(f"{self.files_model.type(index)}\n\nUbicación:\nTrabajo / {path.relative_to(self.service.root)}")
            except WorkFilesError:
                self.open_button.setEnabled(False)

    def _context_menu(self, view, point):
        index = view.indexAt(point)
        menu = QMenu(self)
        menu.addAction("Nueva carpeta", self.create_folder).setEnabled(self.create_button.isEnabled())
        if index.isValid():
            view.setCurrentIndex(index)
            menu.addSeparator()
            menu.addAction("Abrir", self.open_selected)
            menu.addAction("Renombrar", self.rename_selected).setEnabled(self.rename_button.isEnabled())
            menu.addAction("Mover a…", self.move_selected).setEnabled(self.move_button.isEnabled())
            menu.addSeparator()
            menu.addAction("Enviar a la Papelera", self.recycle_selected).setEnabled(self.recycle_button.isEnabled())
        menu.exec(view.viewport().mapToGlobal(point))

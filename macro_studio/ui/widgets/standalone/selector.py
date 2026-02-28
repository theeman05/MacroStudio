from typing import Callable, Iterable, Optional

from PySide6.QtCore import Qt, Signal, QEvent, QPoint
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QComboBox, QHBoxLayout, QLabel, QScrollArea, QWidget, \
    QMessageBox, QMenu, QFrame, QPushButton

from macro_studio.ui.shared import HoverButton, updateLabelIcon, IconColor, flashError
from .approval_event import ApprovalEvent
from .empty_state_widget import EmptyStateWidget


class SelectorRowWidget(QWidget):
    def __init__(self, item_data: Optional[object], popup: "SelectorPopup"):
        super().__init__()
        self.popup = popup
        self.is_adding = item_data is None

        # Store the generic item and extract its ID/Name using the popup's getters
        self.item_data = item_data
        self.item_id = popup.id_getter(item_data) if item_data else None
        self.name = popup.name_getter(item_data) if item_data else ""
        self.is_hovering = False

        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(10)

        self.icon_label = QLabel()

        layout.addWidget(self.icon_label)

        self.name_label = QLabel(self.name)
        layout.addWidget(self.name_label)

        self.name_edit = QLineEdit(self.name)
        self.name_edit.hide()
        self.name_edit.editingFinished.connect(self.attemptRename)
        self.name_edit.installEventFilter(self)
        layout.addWidget(self.name_edit)

        layout.addStretch()

        self.dots_btn = HoverButton("ph.dots-three-outline-fill", size=24)
        self.dots_btn.setAutoDefault(False)
        self.dots_btn.setDefault(False)
        self.dots_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dots_btn.clicked.connect(self.showContextMenu)
        self.dots_btn.hide()
        layout.addWidget(self.dots_btn)

        self.activeStateChanged()

    def updateModel(self, new_item_data: object):
        old_id = self.item_id
        self.item_data = new_item_data
        self.item_id = self.popup.id_getter(new_item_data)
        self.name = self.popup.name_getter(new_item_data)

        if self.popup.active_id == self.item_id:
            # Just created a new object
            self.activeStateChanged()

        if old_id and old_id != self.item_id:
            self.popup.widgetIDChanged(old_id, self)

        self.name_label.setText(self.name)
        self.name_edit.setText(self.name)

    def updateLabelState(self):
        if self.is_hovering:
            self.name_label.setStyleSheet(f"color: {IconColor.SELECTED};")
        elif self.isActive():
            self.name_label.setStyleSheet(f"color: {IconColor.SELECTED_HOVER};")
        else:
            self.name_label.setStyleSheet("")

    def enterEvent(self, event):
        self.is_hovering = True
        if not self.popup.isReadOnly():
            self.dots_btn.show()
        self.updateLabelState()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovering = False
        self.dots_btn.hide()
        self.updateLabelState()
        super().leaveEvent(event)

    def activeStateChanged(self):
        self.updateLabelState()
        if self.isActive():
            updateLabelIcon(self.icon_label, self.popup.active_icon)
        else:
            updateLabelIcon(self.icon_label, self.popup.inactive_icon)

    def isActive(self):
        return self.popup.active_id == self.item_id

    def mousePressEvent(self, event):
        if self.name_edit.isVisible() or self.is_adding: return
        if event.button() == Qt.MouseButton.LeftButton:
            self.popup.requestSelection(self.item_id)
        elif event.button() == Qt.MouseButton.RightButton:
            self.showContextMenu()

    def eventFilter(self, source, event):
        if source == self.name_edit and event.type() == QEvent.Type.FocusOut and event.reason() != Qt.FocusReason.TabFocusReason:
            self.cancelRename()
            return True
        return super().eventFilter(source, event)

    def showContextMenu(self):
        if self.is_adding or self.popup.isReadOnly(): return
        menu = QMenu(self)
        menu.addAction("Rename").triggered.connect(self.enableRenameMode)
        menu.addAction("Duplicate").triggered.connect(lambda: self.popup.requestDuplicate(self.item_id))
        menu.addSeparator()
        menu.addAction("Delete").triggered.connect(lambda: self.popup.requestDelete(self.item_id, self.name))
        menu.exec(QCursor.pos())

    def enableRenameMode(self):
        self.name_label.hide()
        self.name_edit.setText(self.name or " ")
        self.name_edit.show()
        self.name_edit.setFocus()
        self.name_edit.selectAll()
        self.name_edit.setStyleSheet("")

    def attemptRename(self):
        if not self.name_edit.isVisible(): return
        new_name = self.name_edit.text().strip()

        if new_name == self.name:
            self.cancelRename()
            return
        if not new_name:
            flashError(self.name_edit)
            return

        # Hand off to the popup to emit the synchronous ApprovalEvent
        success, error_msg, updated_data = self.popup.processRenameOrAdd(self, new_name)

        if success:
            if updated_data:
                self.updateModel(updated_data)
            else:
                self.name = new_name
                self.name_label.setText(new_name)

            if self.is_adding:
                self.is_adding = False
                self.popup.finalizeTempWidget(self)
            self.cancelRename()
        else:
            flashError(self.name_edit)
            self.name_edit.setToolTip(error_msg)

    def cancelRename(self):
        if not self.is_adding:
            self.name_edit.hide()
            self.name_label.show()
            self.name_edit.setStyleSheet("")
            self.name_edit.setToolTip("")
        else:
            self.popup.scroll_layout.removeWidget(self)
            self.deleteLater()


DEFAULT_INACTIVE_ICON = "ph.file"
DEFAULT_ACTIVE_ICON = "ph.file-text"


class SelectorPopup(QDialog):
    # Signals now decouple the UI from the database logic
    itemSelected = Signal(object)  # Emits item_id
    createRequested = Signal(ApprovalEvent)  # event.value = new_name
    renameRequested = Signal(object, ApprovalEvent)  # item_id, event
    deleteRequested = Signal(object, ApprovalEvent)  # item_id, event
    duplicateRequested = Signal(object, ApprovalEvent)  # item_id, event

    def __init__(self, parent=None, read_only=False, inactive_icon = DEFAULT_INACTIVE_ICON, active_icon = DEFAULT_ACTIVE_ICON):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(400, 400)
        self._read_only = False

        self.widgets_map: dict[object, SelectorRowWidget] = {} # dict[item_id, SelectorRowWidget]

        self.inactive_icon = inactive_icon
        self.active_icon = active_icon

        self.active_id = None

        # Callbacks for data extraction
        self.id_getter: Callable = lambda x: x
        self.name_getter: Callable = lambda x: str(x)
        self.sort_modes = {}  # dict[str, dict]

        self._setupUI()
        self.setReadOnly(read_only)

    def _setupUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- The Blue Header ---
        header_container = QFrame()
        header_container.setFixedHeight(50)
        header_container.setObjectName("BlueHeader")

        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(10, 5, 10, 5)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.textChanged.connect(self.refreshView)
        header_layout.addWidget(self.search_bar, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.currentIndexChanged.connect(self.refreshView)
        header_layout.addWidget(self.sort_combo)

        self.btn_add = HoverButton("ph.plus-circle", size=22)
        self.btn_add.setAutoDefault(False)
        self.btn_add.setDefault(False)
        self.btn_add.setToolTip("Add New Item")
        self.btn_add.clicked.connect(self.createTempWidget)
        header_layout.addWidget(self.btn_add)

        layout.addWidget(header_container)

        # --- Scroll Area ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("Transparent")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(10, 0, 10, 0)
        self.scroll_layout.setSpacing(2)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.empty_state = EmptyStateWidget()
        self.scroll_layout.addWidget(self.empty_state)

        self.empty_state.action_btn.clicked.connect(self.createTempWidget)

        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

    # --- Configuration APIs ---

    def populate(self, items: Iterable[object], id_getter: Callable=None, name_getter: Callable=None):
        """Inject the data and tell the popup how to read it."""
        self.id_getter = id_getter or self.id_getter
        self.name_getter = name_getter or self.name_getter

        # Clear existing
        for w in self.widgets_map.values():
            w.setParent(None)
            w.deleteLater()
        self.widgets_map.clear()

        # Build new
        for item in items:
            self._addWidget(item)

        self.refreshView()

    def addSortMode(self, display_name: str, key_func: Callable, reverse: bool = False):
        """
        Adds a sort option to the dropdown.
        key_func should accept the underlying `item_data` object.
        """
        self.sort_modes[display_name] = {"key": key_func, "reverse": reverse}
        self.sort_combo.addItem(display_name)

    def setActiveID(self, new_id):
        if self.active_id == new_id: return
        widget = self.widgets_map.get(self.active_id)
        self.active_id = new_id
        # Deactivate previous
        if widget: widget.activeStateChanged()

        widget = self.widgets_map.get(new_id)
        if widget: widget.activeStateChanged()

    def addExternalItem(self, item_data):
        """Called when a new task is created outside the popup."""
        self._addWidget(item_data)
        self.refreshView()

    def removeExternalItem(self, item_id):
        widget = self.widgets_map.pop(item_id, None)
        if widget:
            if self.active_id == item_id: self.setActiveID(None)
            self.scroll_layout.removeWidget(widget)
            widget.deleteLater()
            self.refreshView()

    def updateExternalItem(self, item_id, new_item_data):
        widget = self.widgets_map.get(item_id)
        if widget:
            widget.updateModel(new_item_data)
            self.refreshView()

    def widgetIDChanged(self, old_id, widget):
        self.widgets_map[widget.item_id] = widget
        self.widgets_map.pop(old_id, None)

    def getItemData(self, item_id):
        if item_id not in self.widgets_map: return None
        return self.widgets_map.get(item_id).item_data

    def setReadOnly(self, value: bool):
        if value == self._read_only: return
        self._read_only = value
        self.btn_add.setVisible(not value)

    def isReadOnly(self):
        return self._read_only

    # --- Internal Logic & Signal Routing ---

    def _addWidget(self, item_data: object) -> SelectorRowWidget:
        widget = SelectorRowWidget(item_data, self)
        # Store by ID instead of appending to a list
        if widget.item_id is not None:
            self.widgets_map[widget.item_id] = widget

        return widget

    def createTempWidget(self):
        widget = SelectorRowWidget(None, self)
        self.scroll_layout.insertWidget(0, widget)
        widget.enableRenameMode()

    def finalizeTempWidget(self, widget: SelectorRowWidget):
        self.widgets_map[widget.item_id] = widget
        self.refreshView()

    def processRenameOrAdd(self, widget: SelectorRowWidget, new_name: str):
        """Handles emitting the ApprovalEvent to the parent application."""
        event = ApprovalEvent(new_name)

        if widget.is_adding:
            self.createRequested.emit(event)
        else:
            self.renameRequested.emit(widget.item_id, event)

        return event.isAccepted, event.reason, event.return_data

    def requestDelete(self, item_id, item_name):
        reply = QMessageBox.question(self.parent(), "Delete", f'Are you sure you want to delete "{item_name}"?\nThis action cannot be undone.')
        if reply == QMessageBox.StandardButton.Yes:
            event = ApprovalEvent(item_id)
            self.deleteRequested.emit(item_id, event)

            if event.isAccepted:
                self.removeExternalItem(item_id)
            elif event.reason:
                QMessageBox.warning(self, "Error", event.reason)

    def requestDuplicate(self, item_id):
        event = ApprovalEvent(item_id)
        self.duplicateRequested.emit(item_id, event)
        if event.isAccepted and event.return_data:
            self._addWidget(event.return_data)
            self.refreshView()

    def requestSelection(self, item_id):
        self.itemSelected.emit(item_id)
        self.accept()

    def refreshView(self):
        """
        Updates the visibility of rows based on search/sort
        and toggles the empty state.
        """
        # 1. Hide all widgets except the empty state
        for i in range(self.scroll_layout.count()):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget and widget != self.empty_state:
                widget.hide()

        search_text = self.search_bar.text().lower()

        # 2. Filter widgets
        visible_widgets = [w for w in self.widgets_map.values() if search_text in w.name.lower()]

        # 3. Handle Empty State visibility
        if not visible_widgets:
            # Update the text based on whether the user is searching or if the list is just empty
            if search_text:
                self.empty_state.setupState(
                    "ph.magnifying-glass",
                    "No Matches Found",
                    f"We couldn't find anything for '{search_text}'"
                )
            elif self.isReadOnly():
                self.empty_state.defaultState()
            else:
                self.empty_state.defaultState(
                    subtitle="Select the add button to add a new item",
                    btn_text="Add Item"
                )

            self.empty_state.show()
        else:
            self.empty_state.hide()

        # 4. Sort visible widgets
        sort_mode = self.sort_combo.currentText()
        sort_config = self.sort_modes.get(sort_mode)

        if sort_config:
            key_func = sort_config["key"]
            reverse = sort_config["reverse"]
            visible_widgets.sort(key=lambda w: key_func(w.item_data) if w.item_data else "", reverse=reverse)

        # 5. Re-add and show visible widgets
        for w in visible_widgets:
            self.scroll_layout.addWidget(w)
            w.show()


class EditableSelectorDropdown(QWidget):
    selectionChanged = Signal(object) # Emits item_id
    renameRequested = Signal(object, ApprovalEvent)
    createRequested = Signal(ApprovalEvent)
    duplicateRequested = Signal(object, ApprovalEvent)
    deleteRequested = Signal(object, ApprovalEvent)

    def __init__(self, parent=None, read_only=False, display_selected_str=False):
        super().__init__(parent)
        self.setFixedHeight(35)  # Standard control height

        self.current_item_id = None
        self.current_item_data = None
        self.is_creating = False
        self.display_selected_str = display_selected_str

        # We instantiate the popup ONCE here
        self.popup = SelectorPopup(self, read_only)

        self._setupUI()
        self._connectSignals()

    def _setupUI(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 1. The Main Button
        self.btn_display = QPushButton("Select Item...")
        self.btn_display.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_display.clicked.connect(self.togglePopup)
        layout.addWidget(self.btn_display)

        # 2. The Inline Editor (Hidden by default)
        self.edit_box = QLineEdit()
        self.edit_box.hide()
        self.edit_box.editingFinished.connect(self._attemptRename)
        self.edit_box.installEventFilter(self)
        layout.addWidget(self.edit_box)

    def _connectSignals(self):
        self.popup.itemSelected.connect(self._onItemSelected)
        self.popup.renameRequested.connect(self._handlePopupRename)
        self.popup.createRequested.connect(self._onCreateRequested)
        self.popup.deleteRequested.connect(self._handlePopupDeleted)
        self.popup.duplicateRequested.connect(self.duplicateRequested)

    # --- Intercept Methods ---

    def _onItemSelected(self, item_id):
        if self.current_item_data != item_id:
            self.setCurrentItem(self.popup.getItemData(item_id))
            self.selectionChanged.emit(item_id)

    def _handlePopupDeleted(self, item_id, event):
        self.deleteRequested.emit(item_id, event)

        if event.isAccepted:
            if item_id == self.current_item_id: # Current item was deleted, try to select the next one
                popup_iter = iter(self.popup.widgets_map)
                next_id = next(popup_iter, None)
                if next_id == item_id:
                    next_id = next(popup_iter, None)

                next_data = self.popup.getItemData(next_id)
                self.setCurrentItem(next_data)
                self.selectionChanged.emit(next_id)

    def _handlePopupRename(self, item_id, event):
        self.renameRequested.emit(item_id, event)

        if event.isAccepted:
            # If the user renamed the item that is currently selected, update the button!
            if item_id == self.current_item_id:
                self.setCurrentItem(event.return_data)

    def _onCreateRequested(self, event):
        self.createRequested.emit(event)
        if event.isAccepted:
            self.setCurrentItem(event.return_data)

    # --- Configuration ---

    def populate(self, items, id_getter=None, name_getter=None):
        self.popup.populate(items, id_getter, name_getter)

    def setCurrentItem(self, item_data):
        self.current_item_data = item_data
        self.current_item_id = self.popup.id_getter(item_data) if item_data else None

        self.popup.setActiveID(self.current_item_id)

        if item_data:
            display_name = self.popup.name_getter(item_data)
            if self.display_selected_str:
                display_name = f'Selected: "{display_name}"'
        else:
            display_name = "Select Item..."

        self.btn_display.setText(display_name)

    # --- Interaction Logic ---

    def togglePopup(self):
        if self.popup.isVisible():
            self.popup.hide()
        else:
            # Anchor the popup exactly below this widget
            pos = self.mapToGlobal(QPoint(0, self.height()))
            self.popup.move(pos)
            self.popup.show()

    def duplicateSelected(self):
        if not self.current_item_id: return

        event = ApprovalEvent(self.current_item_id)
        self.duplicateRequested.emit(self.current_item_id, event)

        if event.isAccepted and event.return_data:
            # Automatically select the new duplicate
            self.setCurrentItem(event.return_data)
            # Add it to the popup's list
            self.popup.addExternalItem(event.return_data)

    def deleteSelected(self):
        if not self.current_item_id: return
        self.popup.requestDelete(self.current_item_id, self.popup.name_getter(self.current_item_data))

    # --- Inline Naming Logic ---

    def enableCreateMode(self):
        self.is_creating = True
        self.btn_display.hide()
        self.edit_box.setText("")
        self.edit_box.setPlaceholderText("Enter new name...")
        self.edit_box.show()
        self.edit_box.setFocus()

    def enableRenameMode(self):
        if not self.current_item_data: return
        self.is_creating = False
        self.btn_display.hide()
        self.edit_box.setText(self.popup.name_getter(self.current_item_data))
        self.edit_box.setPlaceholderText("")
        self.edit_box.show()
        self.edit_box.setFocus()
        self.edit_box.selectAll()

    def _attemptRename(self):
        if not self.edit_box.isVisible(): return
        new_name = self.edit_box.text().strip()

        if not new_name:
            flashError(self.edit_box)
            return

        event = ApprovalEvent(new_name)

        # Route to the correct signal based on our state flag
        if self.is_creating:
            self.createRequested.emit(event)
        else:
            # Cancel if the name didn't actually change
            if self.current_item_data and new_name == self.popup.name_getter(self.current_item_data):
                self._cancelRename()
                return
            self.renameRequested.emit(self.current_item_id, event)

        if event.isAccepted:
            # Parent approved! Update our UI.
            edit_id = self.current_item_id
            self.setCurrentItem(event.return_data)

            # Keep the popup in sync
            if self.is_creating:
                self.popup.addExternalItem(event.return_data)
            else:
                self.popup.updateExternalItem(edit_id, event.return_data)

            self._cancelRename()
        else:
            flashError(self.edit_box)
            self.edit_box.setToolTip(event.reason)

    def _cancelRename(self):
        self.is_creating = False
        self.edit_box.hide()
        self.btn_display.show()
        self.edit_box.setStyleSheet("")
        self.edit_box.setToolTip("")

    def eventFilter(self, source, event):
        if source == self.edit_box and event.type() == QEvent.Type.FocusOut:
            self._cancelRename()
            return True
        return super().eventFilter(source, event)
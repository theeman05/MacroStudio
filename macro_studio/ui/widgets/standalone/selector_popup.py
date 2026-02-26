from typing import Callable, Iterable, Optional

from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QComboBox, QHBoxLayout, QLabel, QScrollArea, QWidget, \
    QMessageBox, QMenu, QFrame

from macro_studio.ui.shared import HoverButton, createIconLabel, IconColor
from .approval_event import ApprovalEvent


class SelectorRowWidget(QWidget):
    def __init__(self, item_data: Optional[object], popup: "SelectorPopup"):
        super().__init__()
        self.popup = popup
        self.is_adding = item_data is None

        # Store the generic item and extract its ID/Name using the popup's getters
        self.item_data = item_data
        self.item_id = popup.id_getter(item_data) if item_data else None
        self.name = popup.name_getter(item_data) if item_data else ""

        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(10)

        layout.addWidget(createIconLabel("ph.file"))

        self.name_label = QLabel(self.name)
        layout.addWidget(self.name_label)

        self.name_edit = QLineEdit(self.name)
        self.name_edit.hide()
        self.name_edit.editingFinished.connect(self.attemptRename)
        self.name_edit.installEventFilter(self)
        layout.addWidget(self.name_edit)

        layout.addStretch()

        self.dots_btn = HoverButton("ph.dots-three-outline-fill", size=24)
        self.dots_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dots_btn.clicked.connect(self.showContextMenu)
        self.dots_btn.hide()
        layout.addWidget(self.dots_btn)

    def updateModel(self, new_item_data: object):
        """Updates the widget using the popup's generic getters."""
        self.item_data = new_item_data
        self.item_id = self.popup.id_getter(new_item_data)
        self.name = self.popup.name_getter(new_item_data)

        self.name_label.setText(self.name)
        self.name_edit.setText(self.name)

    def enterEvent(self, event):
        self.dots_btn.show()
        self.setStyleSheet(f"color: {IconColor.SELECTED};")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.dots_btn.hide()
        self.setStyleSheet("")
        super().leaveEvent(event)

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
        if self.is_adding: return
        menu = QMenu(self)
        menu.addAction("Rename").triggered.connect(self.enableRenameMode)
        menu.addAction("Duplicate").triggered.connect(lambda: self.popup.requestDuplicate(self.item_id))
        menu.addSeparator()
        menu.addAction("Delete").triggered.connect(lambda: self.popup.requestDelete(self.item_id, self.name))
        menu.exec(QCursor.pos())

    def enableRenameMode(self):
        self.name_label.hide()
        self.name_edit.setText(self.name or "")
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
            self.name_edit.setStyleSheet("border: 1px solid #E53935;")
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
            self.name_edit.setStyleSheet("border: 1px solid #E53935;")
            self.name_edit.setToolTip(error_msg)

    def cancelRename(self):
        if not self.is_adding:
            self.name_edit.hide()
            self.name_label.show()
            self.name_edit.setStyleSheet("")
            self.name_edit.setToolTip("")
        else:
            self.popup.removeTempWidget(self)


class SelectorPopup(QDialog):
    # Signals now decouple the UI from the database logic
    itemSelected = Signal(object)  # Emits item_id
    createRequested = Signal(ApprovalEvent)  # event.value = new_name
    renameRequested = Signal(object, ApprovalEvent)  # item_id, event
    deleteRequested = Signal(object, ApprovalEvent)  # item_id, event
    duplicateRequested = Signal(object, ApprovalEvent)  # item_id, event

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(400, 500)

        self.rows_list: list[SelectorRowWidget] = []

        # Callbacks for data extraction
        self.id_getter: Callable = lambda x: x
        self.name_getter: Callable = lambda x: str(x)
        self.sort_modes = {}  # dict[str, dict]

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- The Blue Header ---
        header_container = QWidget()
        header_container.setObjectName("BlueHeader")
        header_container.setFixedHeight(50)
        # Add your CSS styling for #BlueHeader elsewhere to make it blue!

        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(10, 5, 10, 5)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.textChanged.connect(self.refreshView)
        header_layout.addWidget(self.search_bar, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.currentIndexChanged.connect(self.refreshView)
        header_layout.addWidget(self.sort_combo)

        btn_add = HoverButton("ph.plus-circle", size=22)
        btn_add.clicked.connect(self.createTempWidget)
        header_layout.addWidget(btn_add)
        layout.addWidget(header_container)

        # --- Scroll Area ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(2)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

    # --- Configuration APIs ---

    def populate(self, items: Iterable[object], id_getter: Callable, name_getter: Callable):
        """Inject the data and tell the popup how to read it."""
        self.id_getter = id_getter
        self.name_getter = name_getter

        # Clear existing
        for w in self.rows_list:
            w.setParent(None)
            w.deleteLater()
        self.rows_list.clear()

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

    # --- Internal Logic & Signal Routing ---

    def _addWidget(self, item_data: object) -> SelectorRowWidget:
        widget = SelectorRowWidget(item_data, self)
        self.rows_list.append(widget)
        return widget

    def createTempWidget(self):
        widget = SelectorRowWidget(None, self)
        self.scroll_layout.insertWidget(0, widget)
        widget.enableRenameMode()

    def removeTempWidget(self, widget: SelectorRowWidget):
        self.scroll_layout.removeWidget(widget)
        widget.deleteLater()

    def finalizeTempWidget(self, widget: SelectorRowWidget):
        self.rows_list.append(widget)
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
        reply = QMessageBox.question(self, "Delete", f"Delete '{item_name}'?")
        if reply == QMessageBox.StandardButton.Yes:
            event = ApprovalEvent(item_id)
            self.deleteRequested.emit(item_id, event)

            if event.isAccepted:
                self.rows_list = [w for w in self.rows_list if w.item_id != item_id]
                self.refreshView()
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
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget(): item.widget().hide()

        search_text = self.search_bar.text().lower()
        visible_widgets = [w for w in self.rows_list if search_text in w.name.lower()]

        sort_mode = self.sort_combo.currentText()
        sort_config = self.sort_modes.get(sort_mode)

        if sort_config:
            key_func = sort_config["key"]
            reverse = sort_config["reverse"]
            # Sort by calling the user's key function on the underlying item_data
            visible_widgets.sort(key=lambda w: key_func(w.item_data) if w.item_data else "", reverse=reverse)

        for w in visible_widgets:
            self.scroll_layout.addWidget(w)
            w.show()
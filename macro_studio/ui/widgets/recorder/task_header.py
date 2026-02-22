from typing import TYPE_CHECKING

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QDialog, QScrollArea, QFrame, QMenu, QComboBox,
    QMessageBox, QFileDialog, QCheckBox
)
from PySide6.QtCore import Qt, QPoint, QEvent, Signal
from PySide6.QtGui import QCursor

from macro_studio.ui.shared import HoverButton, createIconLabel, IconColor

if TYPE_CHECKING:
    from macro_studio.core.data import TaskStore

class TaskRowWidget(QWidget):
    def __init__(self, name, parent_popup):
        super().__init__()
        self.is_adding = name is None

        self.name = name
        self.parent_popup = parent_popup
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(10)

        # 1. Icon
        layout.addWidget(createIconLabel("ph.file"))

        # 2. Name Label
        self.name_label = QLabel(name)
        layout.addWidget(self.name_label)

        # 3. Name Edit (Initially Hidden)
        self.name_edit = QLineEdit(name or "")
        self.name_edit.hide()
        # Connect signals for saving
        self.name_edit.editingFinished.connect(self.attemptRename)
        self.name_edit.installEventFilter(self)
        layout.addWidget(self.name_edit)

        layout.addStretch()

        # 4. The 3-Dots Button
        self.dots_btn = HoverButton("ph.dots-three-outline-fill", size=24)
        self.dots_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dots_btn.setAutoDefault(False)
        self.dots_btn.setDefault(False)
        self.dots_btn.clicked.connect(self.showContextMenu)
        self.dots_btn.hide()
        layout.addWidget(self.dots_btn)

    def enterEvent(self, event):
        self.dots_btn.show()
        self.setStyleSheet(f"color: {IconColor.SELECTED};")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.dots_btn.hide()
        self.setStyleSheet("")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.name_edit.isVisible(): return
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent_popup.selectTask(self.name)
        elif event.button() == Qt.MouseButton.RightButton:
            self.showContextMenu()

    def eventFilter(self, source, event):
        """Cancel renames when clicking out of task_name_edit"""
        if source == self.name_edit and event.type() == QEvent.Type.FocusOut and event.reason() != Qt.FocusReason.TabFocusReason:
            self.cancelRename()
            return True

        return super().eventFilter(source, event)

    def showContextMenu(self):
        menu = QMenu(self)

        act_rename = menu.addAction("Rename")
        act_rename.triggered.connect(self.enableRenameMode)

        act_dup = menu.addAction("Duplicate")
        act_dup.triggered.connect(lambda: self.parent_popup.duplicateTask(self.name))

        menu.addSeparator()

        act_del = menu.addAction("Delete")
        act_del.triggered.connect(lambda: self.parent_popup.deleteTask(self.name))

        menu.exec(QCursor.pos())

    def enableRenameMode(self):
        self.name_label.hide()
        self.name_edit.setText(self.name or " ")
        self.name_edit.show()
        self.name_edit.setFocus()
        self.name_edit.selectAll()
        self.name_edit.setStyleSheet("")

    def attemptRename(self):
        if not self.name_edit.isVisible():
            return

        new_name = self.name_edit.text().strip()

        # Case 1: No change
        if new_name == self.name:
            self.cancelRename()
            return

        # Case 2: Empty name
        if not new_name:
            self.name_edit.setStyleSheet("border: 1px solid red;")
            return

        # Case 3: Try to rename via parent
        success, error_msg = self.parent_popup.renameTask(self.name, new_name)

        if success:
            self.name = new_name
            self.name_label.setText(new_name)
            if self.is_adding:
                self.is_adding = False
                self.parent_popup.finalizeTempTask(self)
            self.cancelRename()
        else:
            self.name_edit.setStyleSheet("border: 1px solid red;")
            self.name_edit.setToolTip(error_msg)

    def cancelRename(self):
        if not self.is_adding:
            self.name_edit.hide()
            self.name_label.show()
            self.name_edit.setStyleSheet("")
            self.name_edit.setToolTip("")
        else:
            self.parent_popup.scroll_layout.removeWidget(self)
            self.deleteLater()

class TaskSelectorPopup(QDialog):
    def __init__(self, task_store: "TaskStore", parent_header):
        super().__init__(parent_header)
        self.setObjectName("TaskPopup")
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(300, 400)

        self.tasks = task_store
        self.parent_header = parent_header

        self.rows_list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # --- Search & Sort ---
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search")
        self.search_bar.textChanged.connect(self.refreshView)
        layout.addWidget(self.search_bar)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Alphabetical (A to Z)", "Alphabetical (Z to A)", "Newest First", "Oldest First"])
        self.sort_combo.currentIndexChanged.connect(self.refreshView)
        layout.addWidget(self.sort_combo)

        # --- Header ---
        header_layout = QHBoxLayout()

        btn_add = HoverButton("ph.plus-circle", size=25)
        btn_add.setAutoDefault(False)
        btn_add.setDefault(False)
        btn_add.clicked.connect(self.createTempTask)

        header_label = QLabel("TASKS")
        header_label.setObjectName("header_label")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        header_layout.addWidget(btn_add)
        layout.addLayout(header_layout)

        # --- Scroll Area ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_content.setObjectName("AltBgContainer")
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(2)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Initial Build
        for t in task_store.tasks:
            self.addTaskWidget(t.name)

        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)
        self.refreshView()

    # --- Core Logic ---

    def addTaskWidget(self, task_name):
        """Creates the widget and registers it in our map."""
        widget = TaskRowWidget(task_name, self)
        self.rows_list.append(widget)

        # Note: We don't add to layout here, refresh_view handles that
        return widget

    def createTempTask(self):
        widget = TaskRowWidget(None, self)
        self.scroll_layout.insertWidget(0, widget)
        widget.enableRenameMode()

    def finalizeTempTask(self, widget: TaskRowWidget):
        self.rows_list.append(widget)
        self.tasks.createTask(widget.name)
        self.refreshView()

    def duplicateTask(self, task_name):
        if duped_task := self.tasks.duplicate_task(task_name):
            self.addTaskWidget(duped_task.name)
            self.refreshView()

    def renameTask(self, old_name, new_name):
        """
        Validates and executes a rename.
        Returns (True, None) on success.
        Returns (False, ErrorMessage) on failure.
        """
        task_match = None
        for task in self.tasks.tasks:
            if task.name == old_name:
                task_match = task
            elif task.name == new_name:
                return False, "Task name already exists"

        if old_name:
            # If there is no old name, we are creating a new one
            if not task_match:
                return False, "Original task not found"

            self.tasks.updateTaskName(task_match, new_name)

        # Update Parent Header (if it was selected)
        if task_match == self.tasks.getActiveTask():
            self.parent_header.updateTaskDisplay()

        return True, None

    def deleteTask(self, task_name):
        reply = QMessageBox.question(
            self, "Delete Task",
            f"Are you sure you want to delete '{task_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            active_idx = self.tasks.getActiveTaskIdx()
            popped_task = self.tasks.popTask(active_idx)
            if popped_task:
                self.scroll_layout.removeWidget(self.rows_list.pop(active_idx))
                if popped_task.name == task_name:
                    self.parent_header.updateTaskDisplay()

    def refreshView(self):
        """
        Efficiently hides/shows and reorders widgets based on search/sort.
        Does NOT destroy widgets.
        """
        # 1. Detach all from layout (visually)
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().hide()

        search_text = self.search_bar.text().lower()
        sort_mode = self.sort_combo.currentText()

        # 2. Filter
        visible_widgets = [w for w in self.rows_list if search_text in w.name.lower()]

        # 3. Sort
        if sort_mode == "Alphabetical (A to Z)":
            visible_widgets.sort(key=lambda x: x.name.lower())
        elif sort_mode == "Alphabetical (Z to A)":
            visible_widgets.sort(key=lambda x: x.name.lower(), reverse=True)
        elif sort_mode == "Newest First":
            # Assuming rows_list is in creation order
            visible_widgets.reverse()
        elif sort_mode == "Oldest First":
            pass  # Default order

        # 4. Re-attach to layout
        for w in visible_widgets:
            self.scroll_layout.addWidget(w)
            w.show()

    def selectTask(self, task_name):
        task_idx = self.tasks.getTaskIdx(task_name)
        if task_idx != -1 and self.parent_header.requestTaskSwitch(task_idx):
            self.accept()

class TaskHeaderWidget(QWidget):
    saveRequested = Signal()
    def __init__(self, task_store: "TaskStore"):
        super().__init__()
        self.setFixedHeight(50)

        self.task_selector = None

        # Shared state for tasks
        self.tasks = task_store
        self.is_creating_new = False
        self.has_changes = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)

        self.btn_task = QPushButton()
        self.btn_task.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_task.setFixedWidth(250)

        btn_layout = QHBoxLayout(self.btn_task)
        btn_layout.addStretch()
        btn_layout.addWidget(createIconLabel("ei.chevron-down", size=(15,15)))
        self.btn_task.clicked.connect(lambda: self.toggleSelectorPopup())

        layout.addWidget(self.btn_task)

        # Rename Edit (Initially Hidden)
        self.task_name_edit = QLineEdit()
        self.task_name_edit.setFixedWidth(200)
        self.task_name_edit.hide()
        self.task_name_edit.editingFinished.connect(self.saveRename)
        self.task_name_edit.installEventFilter(self)
        layout.addWidget(self.task_name_edit)

        self.btn_menu = HoverButton("ph.dots-three-outline-fill", size=30)
        self.btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu.clicked.connect(self.showMainMenu)

        layout.addWidget(self.btn_menu)

        line = QFrame()
        line.setFixedHeight(20)
        line.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(line)

        self.btn_new = QPushButton("New Task")
        self.btn_new.setObjectName("new_task_btn")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.clicked.connect(self.onAdd)
        layout.addWidget(self.btn_new)
        layout.addStretch()

        self.updateTaskDisplay()

    def eventFilter(self, source, event):
        """Cancel renames when clicking out of task_name_edit"""
        if source == self.task_name_edit and event.type() == QEvent.Type.FocusOut:
            self.cancelRename()
            return True

        return super().eventFilter(source, event)

    def setModified(self, modified: bool):
        self.has_changes = modified
        current_text = self.btn_task.text().replace("*", "")
        if modified:
            self.btn_task.setText(current_text + "*")
        else:
            self.btn_task.setText(current_text)

    def confirmDiscardChanges(self) -> bool:
        """
        Checks for unsaved changes.
        Returns True if it's safe to proceed (changes saved, discarded, or none existed).
        Returns False if the action should be canceled.
        """
        if not self.has_changes:
            return True

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Unsaved Changes")
        msg_box.setText("There are changes that haven't been saved yet.")
        msg_box.setInformativeText("Do you want to save your changes?")
        
        btn_save = msg_box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        btn_discard = msg_box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        clicked_button = msg_box.clickedButton()

        if clicked_button == btn_save:
            self.saveRequested.emit()
            return True
        elif clicked_button == btn_discard:
            self.setModified(False)  # Discard changes
            return True
        
        return False

    def requestTaskSwitch(self, new_task_idx):
        """
        Attempts to switch to a new task, handling unsaved changes.
        Returns True if switch successful, False if cancelled.
        """
        if self.confirmDiscardChanges():
            self.tasks.setActiveTask(new_task_idx)
            self.updateTaskDisplay()
            return True
        return False

    def updateTaskDisplay(self):
        active_task = self.tasks.getActiveTask()
        self.btn_task.setText(f'"{active_task.name if active_task else "New Task"}"')
        self.has_changes = False # Reset changes on new task load

    def toggleSelectorPopup(self, show=None):
        current_popup = self.task_selector
        is_visible = current_popup is not None and current_popup.isVisible()
        should_show = (not is_visible) if show is None else show

        if should_show:
            if is_visible: return

            self.task_selector = TaskSelectorPopup(self.tasks, self)
            pos = self.btn_task.mapToGlobal(QPoint(0, self.btn_task.height()))
            self.task_selector.move(pos)
            self.task_selector.exec()
            self.task_selector = None
        elif current_popup:
            current_popup.close()
            self.task_selector = None

    def showMainMenu(self):
        menu = QMenu(self)

        act_add = menu.addAction("Add")
        act_add.triggered.connect(self.onAdd)

        act_import = menu.addAction("Import")
        act_import.triggered.connect(self.onImport)

        menu.addSeparator()
        
        act_rename = menu.addAction("Rename")
        act_rename.triggered.connect(self.enableRenameMode)
        
        act_dup = menu.addAction("Duplicate")
        act_dup.triggered.connect(self.onDuplicate)

        act_export = menu.addAction("Export")
        act_export.triggered.connect(self.onExport)

        menu.addSeparator()
        
        act_del = menu.addAction("Delete")
        act_del.triggered.connect(self.onDelete)

        pos = self.btn_menu.mapToGlobal(QPoint(0, self.btn_menu.height()))
        menu.exec(pos)

    def enableRenameMode(self):
        # Determine what text to start with
        active_task = self.tasks.getActiveTask()
        if self.is_creating_new or not active_task:
            start_text = ""  # Start empty for new tasks
        else:
            start_text = active_task.name

        self.btn_task.hide()
        self.task_name_edit.setText(start_text)
        self.task_name_edit.show()
        self.task_name_edit.setFocus()
        self.task_name_edit.selectAll()

        # Clear any previous error styles
        self.task_name_edit.setStyleSheet("")
        self.task_name_edit.setToolTip("")

    def saveRename(self):
        if not self.task_name_edit.isVisible():
            return

        current_name = None if self.is_creating_new else self.btn_task.text().replace("*", "")

        is_valid, result = self.tasks.validateRename(self.task_name_edit.text(), current_name)

        if not is_valid:
            if self.task_name_edit.hasFocus():
                self.task_name_edit.setStyleSheet("border: 1px solid #E53935;")  # Red border
                self.task_name_edit.setToolTip(result)
                return  # Stay in edit mode
            else:
                self.cancelRename()
                return

        new_name = result

        if new_name == current_name:
            self.cancelRename()
            return

        active_task = self.tasks.getActiveTask()
        if self.is_creating_new or not active_task:
            self.is_creating_new = False
            self.tasks.createTask(new_name, set_as_active=True)
            self.updateTaskDisplay()
        else:
            self.tasks.updateTaskName(active_task, new_name)
            if self.has_changes:
                self.btn_task.setText(new_name + "*")
            else:
                self.btn_task.setText(new_name)

        # Finish up
        self.cancelRename()

    def cancelRename(self):
        """Helper to cleanly exit edit mode"""
        self.is_creating_new = False
        self.task_name_edit.hide()
        self.btn_task.show()
        self.task_name_edit.setStyleSheet("")  # Reset styles
        self.task_name_edit.setToolTip("")

    # --- Menu Actions ---

    def onAdd(self):
        # Doesn't add a new one until task_name_edit is set
        self.toggleSelectorPopup(False)

        if not self.confirmDiscardChanges():
            return

        self.is_creating_new = True
        self.btn_task.hide()
        self.task_name_edit.clear()
        self.task_name_edit.show()
        self.task_name_edit.setFocus()

    def onImport(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Task", "", "Task Files (*.task)")
        if filepath:
            self.tasks.importTask(filepath)

    def onExport(self):
        if not self.confirmDiscardChanges(): return
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Task", "", "Task Files (*.task)")
        if filepath:
            self.tasks.exportActiveTask(filepath)

    def onDuplicate(self):
        if not self.confirmDiscardChanges():
            return

        if self.tasks.duplicate_task():
            self.updateTaskDisplay()

    def onDelete(self):
        active_task = self.tasks.getActiveTask()
        if not active_task: return

        reply = QMessageBox.question(
            self, "Delete Task", 
            f"Are you sure you want to delete '{active_task.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.tasks.popTask()
            self.updateTaskDisplay()
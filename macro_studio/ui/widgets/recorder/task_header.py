from typing import TYPE_CHECKING

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QPushButton,
                               QFrame, QMenu,
                               QMessageBox, QFileDialog
                               )
from PySide6.QtCore import Qt, QPoint, Signal

from macro_studio.ui.shared import HoverButton
from macro_studio.ui.widgets.standalone.approval_event import ApprovalEvent
from macro_studio.ui.widgets.standalone.selector import EditableSelectorDropdown
from macro_studio.core.execution.manual_task_wrapper import ManualTaskWrapper
from .code_export_dialog import CodeExportDialog

if TYPE_CHECKING:
    from macro_studio.core.data import Profile


class TaskHeaderWidget(QWidget):
    saveRequested = Signal()

    def __init__(self, profile: "Profile"):
        super().__init__()
        self.setFixedHeight(50)

        self.profile = profile
        self.tasks = profile.tasks
        self.has_changes = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)

        # --- 1. The Smart Selector ---
        self.task_selector = EditableSelectorDropdown(self, display_selected_str=True)
        self.task_selector.setFixedWidth(250)

        # Add Sort Modes
        self.task_selector.popup.addSortMode("Alphabetical (A to Z)", lambda t: t.name.lower())
        self.task_selector.popup.addSortMode("Alphabetical (Z to A)", lambda t: t.name.lower(), reverse=True)
        self.task_selector.popup.addSortMode("Newest First", lambda t: t.id, reverse=True)
        self.task_selector.popup.addSortMode("Oldest First", lambda t: t.id)

        layout.addWidget(self.task_selector)

        # --- 2. Menu Button ---
        self.btn_menu = HoverButton("ph.dots-three-outline-fill", size=30)
        self.btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu.clicked.connect(self.showMainMenu)
        layout.addWidget(self.btn_menu)

        # --- 3. Divider ---
        line = QFrame()
        line.setFixedHeight(20)
        line.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(line)

        # --- 4. Add Button ---
        self.btn_new = QPushButton("New Task")
        self.btn_new.setObjectName("new_task_btn")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_new)

        layout.addStretch()

        # Initialize
        self._connectSignals()

    def _connectSignals(self):
        self.btn_new.clicked.connect(self.task_selector.enableCreateMode)
        self.profile.loaded.connect(self._onProfileInitLoaded)
        self.task_selector.selectionChanged.connect(self.requestTaskSwitch)
        self.task_selector.renameRequested.connect(self.handleRename)
        self.task_selector.createRequested.connect(self.handleCreate)
        self.task_selector.duplicateRequested.connect(self.handleDuplicate)
        self.task_selector.deleteRequested.connect(self.handleDelete)

    def _onProfileInitLoaded(self):
        # We only need this on initial load, disconnect after that
        self.profile.loaded.disconnect(self._onProfileInitLoaded)
        self.task_selector.populate(
            items=self.tasks.tasks.values(),
            id_getter=lambda t: t.id,
            name_getter=lambda t: t.name
        )
        self.updateTaskDisplay()

    # --- Display & State Management ---

    def updateTaskDisplay(self):
        active_task = self.tasks.getActiveTask()
        self.task_selector.setCurrentItem(active_task)
        self.has_changes = False

    def setModified(self, modified: bool):
        self.has_changes = modified
        active_task = self.tasks.getActiveTask()
        if not active_task: return

        base_str = f'Selected: "{active_task.name}"'
        if modified:
            self.task_selector.btn_display.setText(f"{base_str}*")
        else:
            self.task_selector.btn_display.setText(base_str)

    def confirmDiscardChanges(self) -> bool:
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
            self.setModified(False)
            return True

        return False

    # --- Selector Signal Handlers ---

    def requestTaskSwitch(self, new_task_id):
        # Handle clear event (e.g. active task was deleted)
        if new_task_id is None:
            self.tasks.setActiveId(None)
            self.has_changes = False
            return True

        if self.confirmDiscardChanges():
            self.tasks.setActiveId(new_task_id)
            self.updateTaskDisplay()
            self.setModified(False)
            return True
        else:
            # User aborted, revert the selector back to the old active task
            self.task_selector.setCurrentItem(self.tasks.getActiveTask())
            return False

    def handleRename(self, item_id: int, event: ApprovalEvent):
        task = self.tasks.tasks.get(item_id)
        if not task:
            event.ignore("Original task not found.")
            return

        is_valid, msg = self.tasks.validateRename(event.value, task.name)
        if not is_valid:
            event.ignore(msg)
            return

        self.tasks.updateTaskName(task, event.value)
        event.accept(task)

        # Restore the asterisk if we renamed the active, unsaved task
        if self.has_changes and item_id == self.tasks.getActiveId():
            self.setModified(True)

    def handleCreate(self, event: ApprovalEvent):
        if not self.confirmDiscardChanges():
            event.ignore("Save cancelled.")
            return

        is_valid, msg = self.tasks.validateRename(event.value, None)
        if not is_valid:
            event.ignore(msg)
            return

        new_task = self.tasks.createTask(event.value, set_as_active=True)
        self.has_changes = False
        event.accept(new_task)

    def handleDuplicate(self, item_id: int, event: ApprovalEvent):
        if not self.confirmDiscardChanges():
            event.ignore("Save cancelled.")
            return

        task = self.tasks.tasks.get(item_id)
        if not task:
            event.ignore("Task not found.")
            return

        new_task = self.tasks.duplicateTask(task.name)
        if new_task:
            self.has_changes = False
            event.accept(new_task)
        else:
            event.ignore("Failed to duplicate task.")

    def handleDelete(self, item_id: int, event: ApprovalEvent):
        popped_task = self.tasks.popTask(item_id)
        if popped_task:
            event.accept()
        else:
            event.ignore("Failed to delete task.")

    # --- Menu Actions ---

    def showMainMenu(self):
        menu = QMenu(self)

        act_add = menu.addAction("Add")
        act_add.triggered.connect(self.task_selector.enableCreateMode)

        act_import = menu.addAction("Import")
        act_import.triggered.connect(self.onImport)

        if self.tasks.getActiveTask():
            menu.addSeparator()

            act_rename = menu.addAction("Rename")
            act_rename.triggered.connect(self.task_selector.enableRenameMode)

            act_dup = menu.addAction("Duplicate")
            act_dup.triggered.connect(self.task_selector.duplicateSelected)

            menu.addSeparator()

            act_export = menu.addAction("Export to File")
            act_export.triggered.connect(self.onExport)

            act_export_py = menu.addAction("Export to Python")
            act_export_py.triggered.connect(self.onExportToPy)

            menu.addSeparator()

            act_del = menu.addAction("Delete")
            act_del.triggered.connect(self.task_selector.deleteSelected)

        pos = self.btn_menu.mapToGlobal(QPoint(0, self.btn_menu.height()))
        menu.exec(pos)

    def onImport(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Task", "", "Task Files (*.task)")
        if filepath:
            self.tasks.importTask(filepath)

    def onExport(self):
        if not self.confirmDiscardChanges() or not self.tasks.getActiveTask(): return
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Task", "", "Task Files (*.task)")
        if filepath:
            self.tasks.exportActiveTask(filepath)

    def onExportToPy(self):
        active_task = self.tasks.getActiveTask()
        if not self.confirmDiscardChanges() or not active_task: return
        temp_wrapper = ManualTaskWrapper(self.profile.vars, active_task)
        generated_code = temp_wrapper.generatePythonCode(task_name=active_task.name)

        dialog = CodeExportDialog(generated_code, parent=self)
        dialog.exec()
        dialog.deleteLater()
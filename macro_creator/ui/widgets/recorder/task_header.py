import sys, re
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QDialog, QScrollArea, QFrame, QMenu, QComboBox,
    QMessageBox, QFileDialog, QCheckBox
)
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QCursor

from macro_creator.core.task_manager import TaskManager
from macro_creator.ui.shared import HoverButton, createIconLabel, SELECTED_COLOR


def validate_task_rename(new_name, current_name, task_manager: TaskManager):
    """
    Validates a name change.
    Returns: (is_valid, result_string_or_error_message)
    """
    clean_name = new_name.strip()

    # 1. Check Empty
    if not clean_name:
        return False, "Task name cannot be empty"

    # 2. Check No Change (Valid, but nothing to do)
    if clean_name == current_name:
        return True, clean_name

    # 3. Check Duplicates
    if task_manager.getTaskIdx(current_name) != -1:
        return False, f"Task '{clean_name}' already exists"

    return True, clean_name

def generate_unique_name(base_name, task_manager):
    """
    Generates a unique name based off base_name.
    If base is present, returns a name like base_name (1), base_name (2), etc.
    """
    existing_names = {task.name for task in task_manager.tasks}

    # Smart Strip: Check if base_name already ends in "(digits)"
    match_existing = re.match(r"^(.*?)\s\(\d+\)$", base_name)

    if match_existing:
        # User passed "Task (1)", so our core name is just "Task"
        core_name = match_existing.group(1)
    else:
        # User passed "Task", so that is our core name
        core_name = base_name

    if base_name not in existing_names:
        return base_name

    i = 1
    while base_name in existing_names:
        base_name = f"{core_name} ({i})"
        i += 1

    return base_name

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
        self.name_edit.editingFinished.connect(self.attempt_rename)
        self.name_edit.installEventFilter(self)
        layout.addWidget(self.name_edit)

        layout.addStretch()

        # 4. The 3-Dots Button
        self.dots_btn = HoverButton("ph.dots-three-outline-fill", size=24)
        self.dots_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dots_btn.setAutoDefault(False)
        self.dots_btn.setDefault(False)
        self.dots_btn.clicked.connect(self.show_context_menu)
        self.dots_btn.hide()
        layout.addWidget(self.dots_btn)

    def enterEvent(self, event):
        self.dots_btn.show()
        self.setStyleSheet(f"color: {SELECTED_COLOR};")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.dots_btn.hide()
        self.setStyleSheet("")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.name_edit.isVisible(): return
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent_popup.select_task(self.name)
        elif event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu()

    def eventFilter(self, source, event):
        """Cancel renames when clicking out of task_name_edit"""
        if source == self.name_edit and event.type() == QEvent.Type.FocusOut and event.reason() != Qt.FocusReason.TabFocusReason:
            self.cancel_rename()
            return True

        return super().eventFilter(source, event)

    def show_context_menu(self):
        menu = QMenu(self)

        act_rename = menu.addAction("Rename")
        act_rename.triggered.connect(self.enable_rename_mode)

        act_dup = menu.addAction("Duplicate")
        act_dup.triggered.connect(lambda: self.parent_popup.duplicate_task(self.name))

        menu.addSeparator()

        act_del = menu.addAction("Delete")
        act_del.triggered.connect(lambda: self.parent_popup.delete_task(self.name))

        menu.exec(QCursor.pos())

    def enable_rename_mode(self):
        self.name_label.hide()
        self.name_edit.setText(self.name or " ")
        self.name_edit.show()
        self.name_edit.setFocus()
        self.name_edit.selectAll()
        self.name_edit.setStyleSheet("")

    def attempt_rename(self):
        if not self.name_edit.isVisible():
            return

        new_name = self.name_edit.text().strip()

        # Case 1: No change
        if new_name == self.name:
            self.cancel_rename()
            return

        # Case 2: Empty name
        if not new_name:
            self.name_edit.setStyleSheet("border: 1px solid red;")
            return

        # Case 3: Try to rename via parent
        success, error_msg = self.parent_popup.rename_task(self.name, new_name)

        if success:
            self.name = new_name
            self.name_label.setText(new_name)
            if self.is_adding:
                self.is_adding = False
                self.parent_popup.finalize_temp_task(self)
            self.cancel_rename()
        else:
            self.name_edit.setStyleSheet("border: 1px solid red;")
            self.name_edit.setToolTip(error_msg)

    def cancel_rename(self):
        if not self.is_adding:
            self.name_edit.hide()
            self.name_label.show()
            self.name_edit.setStyleSheet("")
            self.name_edit.setToolTip("")
        else:
            self.parent_popup.scroll_layout.removeWidget(self)
            self.deleteLater()

class TaskSelectorPopup(QDialog):
    def __init__(self, task_manager: TaskManager, parent_header):
        super().__init__(parent_header)
        self.setObjectName("TaskPopup")
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(300, 400)

        self.task_manager = task_manager
        self.parent_header = parent_header

        self.rows_list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # --- Search & Sort ---
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search")
        self.search_bar.textChanged.connect(self.refresh_view)
        layout.addWidget(self.search_bar)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Alphabetical (A to Z)", "Alphabetical (Z to A)", "Newest First", "Oldest First"])
        self.sort_combo.currentIndexChanged.connect(self.refresh_view)
        layout.addWidget(self.sort_combo)

        # --- Header ---
        header_layout = QHBoxLayout()

        btn_add = HoverButton("ph.plus-circle", size=25)
        btn_add.setAutoDefault(False)
        btn_add.setDefault(False)
        btn_add.clicked.connect(self.creat_temp_task)

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
        for t in task_manager.tasks:
            self.add_task_widget(t.name)

        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)
        self.refresh_view()

    # --- Core Logic ---

    def add_task_widget(self, task_name):
        """Creates the widget and registers it in our map."""
        widget = TaskRowWidget(task_name, self)
        self.rows_list.append(widget)

        # Note: We don't add to layout here, refresh_view handles that
        return widget

    def creat_temp_task(self):
        widget = TaskRowWidget(None, self)
        self.scroll_layout.insertWidget(0, widget)
        widget.enable_rename_mode()

    def finalize_temp_task(self, widget: TaskRowWidget):
        self.rows_list.append(widget)
        self.task_manager.createTask(widget.name)
        self.refresh_view()

    def duplicate_task(self, task_name):
        new_name = generate_unique_name(task_name, self.task_manager)
        self.task_manager.createTask(new_name)
        self.add_task_widget(new_name)
        self.refresh_view()

    def rename_task(self, old_name, new_name):
        """
        Validates and executes a rename.
        Returns (True, None) on success.
        Returns (False, ErrorMessage) on failure.
        """
        task_match = None
        for task in self.task_manager.tasks:
            if task.name == old_name:
                task_match = task
            elif task.name == new_name:
                return False, "Task name already exists"

        if old_name:
            # If there is no old name, we are creating a new one
            if not task_match:
                return False, "Original task not found"

            task_match.name = new_name

        # Update Parent Header (if it was selected)
        if task_match == self.task_manager.getActiveTask():
            self.parent_header.update_task_display()

        return True, None

    def delete_task(self, task_name):
        reply = QMessageBox.question(
            self, "Delete Task",
            f"Are you sure you want to delete '{task_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            active_task = self.task_manager.getActiveTask()
            remove_idx = self.task_manager.removeTask(task_name)

            if remove_idx != -1:
                # Remove from UI
                widget = self.rows_list.pop(remove_idx)
                self.scroll_layout.removeWidget(widget)
                widget.deleteLater()

                if active_task.name == task_name:
                    self.parent_header.update_task_display()

    def refresh_view(self):
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

    def select_task(self, task_name):
        task_idx = self.task_manager.getTaskIdx(task_name)
        if task_idx != -1 and self.parent_header.request_task_switch(task_idx):
            self.accept()

class TaskHeaderWidget(QWidget):
    def __init__(self, task_manager: TaskManager):
        super().__init__()
        self.setFixedHeight(50)

        self.task_selector = None

        # Shared state for tasks
        self.task_manager = task_manager
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
        self.btn_task.clicked.connect(lambda: self.toggle_task_selector())

        layout.addWidget(self.btn_task)

        # Rename Edit (Initially Hidden)
        self.task_name_edit = QLineEdit()
        self.task_name_edit.setFixedWidth(200)
        self.task_name_edit.hide()
        self.task_name_edit.editingFinished.connect(self.save_rename)
        self.task_name_edit.installEventFilter(self)
        layout.addWidget(self.task_name_edit)

        self.btn_menu = HoverButton("ph.dots-three-outline-fill", size=30)
        self.btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu.clicked.connect(self.show_main_menu)

        layout.addWidget(self.btn_menu)

        line = QFrame()
        line.setFixedHeight(20)
        line.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(line)

        self.btn_new = QPushButton("New Task")
        self.btn_new.setObjectName("new_task_btn")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.clicked.connect(self.on_add)
        layout.addWidget(self.btn_new)

        layout.addStretch()

        self.chk_loop = QCheckBox("Auto Loop")
        self.chk_loop.setToolTip("Automatically restart the task when it finishes.")
        self.chk_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_loop.clicked.connect(self.toggle_auto_loop)
        layout.addWidget(self.chk_loop)

        self.update_task_display()

    def eventFilter(self, source, event):
        """Cancel renames when clicking out of task_name_edit"""
        if source == self.task_name_edit and event.type() == QEvent.Type.FocusOut:
            self.cancel_rename()
            return True

        return super().eventFilter(source, event)

    def toggle_auto_loop(self, checked: bool):
        active_task = self.task_manager.getActiveTask()
        if active_task:
            prev_state = active_task.auto_loop
            if prev_state != checked:
                active_task.auto_loop = checked
        elif checked:
            self.task_manager.createTask("New Task").auto_loop = True

    def set_modified(self, modified: bool):
        self.has_changes = modified
        current_text = self.btn_task.text().replace("*", "")
        if modified:
            self.btn_task.setText(current_text + "*")
        else:
            self.btn_task.setText(current_text)

    def save_changes(self):
        print(f"Saving changes for {self.btn_task.text().replace('*', '')}")
        self.set_modified(False)

    def confirm_discard_changes(self) -> bool:
        """
        Checks for unsaved changes.
        Returns True if it's safe to proceed (changes saved, discarded, or none existed).
        Returns False if the action should be cancelled.
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
            self.save_changes()
            return True
        elif clicked_button == btn_discard:
            self.set_modified(False) # Discard changes
            return True
        
        return False

    def request_task_switch(self, new_task_idx):
        """
        Attempts to switch to a new task, handling unsaved changes.
        Returns True if switch successful, False if cancelled.
        """
        if self.confirm_discard_changes():
            self.task_manager.setActiveTask(new_task_idx)
            self.update_task_display()
            return True
        return False

    def update_task_display(self):
        active_task = self.task_manager.getActiveTask()
        self.chk_loop.setChecked(active_task.auto_loop if active_task else False)
        self.btn_task.setText(active_task.name if active_task else "New Task")
        self.has_changes = False # Reset changes on new task load

    def toggle_task_selector(self, show=None):
        current_popup = self.task_selector
        is_visible = current_popup is not None and current_popup.isVisible()
        should_show = (not is_visible) if show is None else show

        if should_show:
            if is_visible: return

            self.task_selector = TaskSelectorPopup(self.task_manager, self)
            pos = self.btn_task.mapToGlobal(QPoint(0, self.btn_task.height()))
            self.task_selector.move(pos)
            self.task_selector.exec()
            self.task_selector = None
        elif current_popup:
            current_popup.close()
            self.task_selector = None

    def show_main_menu(self):
        menu = QMenu(self)

        act_add = menu.addAction("Add")
        act_add.triggered.connect(self.on_add)

        act_import = menu.addAction("Import")
        act_import.triggered.connect(self.on_import)

        menu.addSeparator()
        
        act_rename = menu.addAction("Rename")
        act_rename.triggered.connect(self.enable_rename_mode)
        
        act_dup = menu.addAction("Duplicate")
        act_dup.triggered.connect(self.on_duplicate)

        act_export = menu.addAction("Export")
        act_export.triggered.connect(self.on_export)

        menu.addSeparator()
        
        act_del = menu.addAction("Delete")
        act_del.triggered.connect(self.on_delete)

        # Debug action to simulate changes
        menu.addSeparator()
        act_mod = menu.addAction("Simulate Change")
        act_mod.triggered.connect(lambda: self.set_modified(True))

        pos = self.btn_menu.mapToGlobal(QPoint(0, self.btn_menu.height()))
        menu.exec(pos)

    def enable_rename_mode(self):
        # Determine what text to start with
        active_task = self.task_manager.getActiveTask()
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

    def save_rename(self):
        if not self.task_name_edit.isVisible():
            return

        current_name = None if self.is_creating_new else self.btn_task.text().replace("*", "")

        is_valid, result = validate_task_rename(
            self.task_name_edit.text(),
            current_name,
            self.task_manager
        )

        if not is_valid:
            if self.task_name_edit.hasFocus():
                self.task_name_edit.setStyleSheet("border: 1px solid #E53935;")  # Red border
                self.task_name_edit.setToolTip(result)
                return  # Stay in edit mode
            else:
                self.cancel_rename()
                return

        new_name = result

        if new_name == current_name:
            self.cancel_rename()
            return

        active_task = self.task_manager.getActiveTask()
        if self.is_creating_new or not active_task:
            self.is_creating_new = False
            self.task_manager.createTask(new_name, set_as_active=True)
            self.update_task_display()
        else:
            active_task.name = new_name

            if self.has_changes:
                self.btn_task.setText(new_name + "*")
            else:
                self.btn_task.setText(new_name)

        # Finish up
        self.cancel_rename()

    def cancel_rename(self):
        """Helper to cleanly exit edit mode"""
        self.is_creating_new = False
        self.task_name_edit.hide()
        self.btn_task.show()
        self.task_name_edit.setStyleSheet("")  # Reset styles
        self.task_name_edit.setToolTip("")

    # --- Menu Actions ---

    def on_add(self):
        # Doesn't add a new one until task_name_edit is set
        self.toggle_task_selector(False)

        if not self.confirm_discard_changes():
            return

        self.is_creating_new = True
        self.btn_task.hide()
        self.task_name_edit.clear()
        self.task_name_edit.show()
        self.task_name_edit.setFocus()

    def on_import(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Import Task", "", "Task Files (*.task)")
        if fname:
            print(f"Importing from {fname}")

    def on_duplicate(self):
        if not self.confirm_discard_changes():
            return

        new_name = "New Task"
        if active_task := self.task_manager.getActiveTask():
            new_name = generate_unique_name(active_task.name, self.task_manager)

        self.task_manager.createTask(new_name, set_as_active=True)
        self.update_task_display()

    def on_export(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Export Macro", "", "Macro Files (*.json *.macro)")
        if fname:
            print(f"Exporting to {fname}")

    def on_delete(self):
        active_task = self.task_manager.getActiveTask()
        if not active_task: return

        reply = QMessageBox.question(
            self, "Delete Task", 
            f"Are you sure you want to delete '{active_task.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.task_manager.popTask()
            self.update_task_display()


# --- BOILERPLATE TO RUN IT ---
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Create a container window to hold our widget
    main_window = QWidget()
    main_window.setWindowTitle("Macro Recorder UI")
    main_window.resize(600, 400)

    main_layout = QVBoxLayout(main_window)
    main_layout.setContentsMargins(0, 0, 0, 0)

    manager = TaskManager()
    manager.createTask("Auto Clicker")
    manager.createTask("Anti-Afk")
    manager.createTask("Farm Resources")
    manager.createTask("Burgers")

    # Add our custom widget to the top
    header = TaskHeaderWidget(manager)
    main_layout.addWidget(header)

    # Spacer to push it to the top
    main_layout.addStretch()

    main_window.show()
    sys.exit(app.exec())
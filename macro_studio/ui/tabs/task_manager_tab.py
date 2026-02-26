from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea
from PySide6.QtCore import QTimer

from macro_studio.ui.widgets.task_manager.task_row_widget import TaskRowWidget
from macro_studio.ui.widgets.task_manager.manager_header import ManagerHeader


class TaskManagerTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)

        self.header = ManagerHeader()

        self.scroll_area = QScrollArea()

        self.scroll_area.setWidgetResizable(True)

        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("list_container")

        self.tasks_layout = QVBoxLayout(self.scroll_widget)
        self.tasks_layout.setContentsMargins(5, 5, 5, 5)
        self.tasks_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.header)
        self.main_layout.addWidget(self.scroll_area)

        self.task_rows = {}

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.refreshUi)
        self.update_timer.start(100)  # 10 FPS UI updates

    def refreshUi(self):
        # Fetch the live dictionary directly from the manager
        active_controllers = self.manager.controllers

        for task_key, controller in active_controllers.items():
            if task_key not in self.task_rows:
                new_row = TaskRowWidget(controller)
                # Insert right above the stretch space at the bottom
                self.tasks_layout.insertWidget(self.tasks_layout.count() - 1, new_row)
                self.task_rows[task_key] = new_row

        stale_keys = []
        for task_key, row_widget in self.task_rows.items():
            if task_key not in active_controllers:
                # The task was removed from the engine. Destroy the UI row.
                row_widget.setParent(None)
                row_widget.deleteLater()
                stale_keys.append(task_key)
            else:
                # The task still exists. Trigger its color/button update!
                row_widget.updateUi()

        for key in stale_keys:
            del self.task_rows[key]
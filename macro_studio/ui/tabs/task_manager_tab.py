from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea
from PySide6.QtCore import QTimer

from macro_studio.ui.widgets.task_manager.task_row_widget import TaskRowWidget
from macro_studio.ui.widgets.task_manager.manager_header import ManagerHeader
from macro_studio.ui.widgets.standalone.selector import SelectorPopup
from macro_studio.ui.widgets.standalone.empty_state_widget import EmptyStateWidget

if TYPE_CHECKING:
    from macro_studio.core.controllers.task_manager import TaskManager
    from macro_studio.ui.main_window import MainWindow


class TaskManagerTab(QWidget):
    def __init__(self, main_window: "MainWindow", manager: "TaskManager"):
        super().__init__()
        self.manager = manager
        self.main_window = main_window

        self.task_selector = SelectorPopup(parent=self, read_only=True)
        self.task_selector.empty_state.default_title = "No Tasks Available"
        self.task_selector.empty_state.default_action_txt = "View Recorder Tab"
        self.task_selector.addSortMode("Alphabetical (A to Z)", lambda t: t.name.lower())
        self.task_selector.addSortMode("Alphabetical (Z to A)", lambda t: t.name.lower(), reverse=True)
        self.task_selector.addSortMode("Newest First", lambda t: t.id, reverse=True)
        self.task_selector.addSortMode("Oldest First", lambda t: t.id)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)

        self.header = ManagerHeader()

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("list_container")

        self.tasks_layout = QVBoxLayout(self.scroll_widget)
        self.tasks_layout.setContentsMargins(5, 5, 5, 5)
        self.tasks_layout.setSpacing(4)

        self.empty_state = EmptyStateWidget()
        self.empty_state.defaultState(
            subtitle="There are no tasks to display",
            btn_text="Add Recorded Task"
        )
        self.empty_state.hide()
        self.tasks_layout.addWidget(self.empty_state)

        self.tasks_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.header)
        self.main_layout.addWidget(self.scroll_area)

        self.task_rows = {}

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.refreshUi)
        self.update_timer.start(100)  # 10 FPS UI updates

        self._connectSignals()

    def _connectSignals(self):
        self.header.add_btn.clicked.connect(self._showTaskSelector)
        self.task_selector.itemSelected.connect(self.manager.profile.createRelationship)
        self.empty_state.action_btn.clicked.connect(self._showTaskSelector)
        self.task_selector.empty_state.action_btn.clicked.connect(self._showRecordTab)

    def _showRecordTab(self):
        self.task_selector.hide()
        self.main_window.tabs.setCurrentWidget(self.main_window.recorder_tab)

    def _showTaskSelector(self):
        # Filters out currently active tasks and shows the popup.
        active_controllers = self.manager.controllers

        if active_controllers:
            self.task_selector.empty_state.default_subtitle = "All available tasks have been added already"
        else:
            self.task_selector.empty_state.default_subtitle = "No recorded tasks have been created"

        available_tasks = [
            task for task in self.manager.profile.tasks.tasks.values()
            if task.name not in active_controllers
        ]

        self.task_selector.populate(
            items=available_tasks,
            id_getter=lambda t: t.id,
            name_getter=lambda t: t.name
        )

        self.task_selector.exec()

    def _onRequestDelete(self, controller):
        # Only can delete manual controllers, they have relationship
        self.manager.profile.removeRelationship(controller.relationship.task_id)
        self.manager.removeController(controller)

    def refreshUi(self):
        # Fetch the live dictionary directly from the manager
        active_controllers = self.manager.controllers

        for task_key, controller in active_controllers.items():
            if task_key not in self.task_rows:
                new_row = TaskRowWidget(controller)
                # Insert right above the stretch space at the bottom
                self.tasks_layout.insertWidget(self.tasks_layout.count() - 1, new_row)
                self.task_rows[task_key] = new_row
                if isinstance(controller.name, str):
                    new_row.removeRequested.connect(self._onRequestDelete)

        search_text = self.header.search_bar.text().lower().strip()

        stale_keys = []
        visible_count = 0

        for task_key, row_widget in self.task_rows.items():
            if task_key not in active_controllers:
                # The task was removed from the engine. Destroy the UI row.
                row_widget.setParent(None)
                row_widget.deleteLater()
                stale_keys.append(task_key)
            else:
                controller = active_controllers[task_key]
                row_widget.updateUi()

                # Simulate the UI prefix to ensure "Task " searches match properly
                display_name = f"task {str(controller.name).lower()}"

                # Filter visibility
                if search_text in display_name:
                    row_widget.show()
                    visible_count += 1
                else:
                    row_widget.hide()

        for key in stale_keys:
            del self.task_rows[key]

        if not active_controllers:
            # The list is completely empty
            self.empty_state.defaultState(
                subtitle="There are no tasks to display",
                btn_text="Add Recorded Task"
            )
            self.empty_state.show()
        elif visible_count == 0:
            # Tasks exist, but the search filtered them all out
            self.empty_state.setupState(
                icon_name="ph.magnifying-glass",
                title="No Matches Found",
                subtitle=f"We couldn't find any tasks named '{self.header.search_bar.text()}'"
            )
            self.empty_state.show()
        else:
            self.empty_state.hide()
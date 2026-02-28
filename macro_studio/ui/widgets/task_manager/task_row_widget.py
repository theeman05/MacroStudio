from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QSizePolicy, QWidget, QGridLayout, QMenu, QMessageBox

from macro_studio.core.controllers.task_controller import TaskState
from macro_studio.ui.shared import ToggleHoverButton, HoverButton, IconColor
from macro_studio.core.controllers.threaded_controller import ThreadedController
from macro_studio.ui.widgets.standalone.approval_event import ApprovalEvent

if TYPE_CHECKING:
    from macro_studio.core.controllers.task_controller import TaskController

ICON_SIZE = 24

from PySide6.QtWidgets import QLabel


class CircularStatusLabel(QLabel):
    def __init__(self, size=12, starting_color=IconColor.DISABLED, parent=None):
        super().__init__(parent)
        self.circle_size = size
        self.setFixedSize(self.circle_size, self.circle_size)
        self.setText("")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.updateColor(starting_color)

    def updateColor(self, color_hex: str):
        border_radius = self.circle_size // 2

        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color_hex};
                border-radius: {border_radius}px;
            }}
        """)


class TaskRowWidget(QFrame):
    removeRequested = Signal(object) # controller

    def __init__(self, controller: "TaskController"):
        super().__init__()
        self.controller = controller
        self.prev_name = None

        self.setObjectName("TaskCard")

        # Left Zone: Identity
        self.lbl_status_dot = CircularStatusLabel()
        self.btn_toggle = ToggleHoverButton("ph.circle-dashed-bold", "ph.circle-bold", normal_tooltip="Enable Task", checked_tooltip="Disable Task", size=28)

        self.lbl_name = QLabel()
        self.lbl_name.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.lbl_state_text = QLabel()
        self.lbl_state_text.setStyleSheet("color: #888888; font-size: 11px;")

        # Right Zone: Actions
        self.btn_loop = ToggleHoverButton("ph.repeat-bold", normal_tooltip="Enable Repeat", checked_tooltip="Disable Repeat", size=ICON_SIZE)
        self.btn_restart = HoverButton("ph.arrow-u-up-left-bold", tooltip="Restart Task", size=ICON_SIZE)
        self.btn_pause_resume = ToggleHoverButton("ph.pause-bold", "ph.play-bold", normal_color=IconColor.DEFAULT, hover_color=IconColor.SELECTED_HOVER, checked_color=IconColor.DEFAULT, checked_hover_color=IconColor.SELECTED_HOVER, normal_tooltip="Pause Task", checked_tooltip="Resume Task", size=ICON_SIZE)
        self.btn_interrupt = HoverButton("mdi.alert-octagon-outline", hover_color="#F46800", tooltip="Interrupt Task", size=ICON_SIZE)
        self.btn_stop = HoverButton("ph.stop-bold", hover_color="#f44336", tooltip="Stop Task", size=ICON_SIZE)

        self.setupLayout()
        self.connectSignals()
        self.updateUi()

    def setupLayout(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 4, 12, 8)
        main_layout.setSpacing(10)

        status_widget = QWidget()
        status_stack = QGridLayout(status_widget)
        status_stack.setContentsMargins(0, 0, 0, 0)

        # Left Zone Assembly
        status_stack.addWidget(self.btn_toggle, 0, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        status_stack.addWidget(self.lbl_status_dot, 0, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(status_widget)
        self.lbl_status_dot.raise_()

        name_badge_layout = QHBoxLayout()
        name_badge_layout.setSpacing(6)
        name_badge_layout.addWidget(self.lbl_name)

        is_threaded = isinstance(self.controller, ThreadedController)
        if is_threaded:
            lbl_badge = QLabel("THREADED")
            lbl_badge.setObjectName("pill_style")
            lbl_badge.setStyleSheet("""
                        QLabel {
                            background-color: #3f3f3f; 
                            color: #aaaaaa; 
                            border-radius: 4px; 
                            padding: 2px 6px; 
                            font-size: 9px; 
                            font-weight: bold;
                            letter-spacing: 1px;
                        }
                    """)
            name_badge_layout.addWidget(lbl_badge)

        name_badge_layout.addStretch()

        name_state_layout = QVBoxLayout()
        name_state_layout.setSpacing(0)
        name_state_layout.addLayout(name_badge_layout)
        name_state_layout.addWidget(self.lbl_state_text)
        main_layout.addLayout(name_state_layout)

        # The Spacer (Pushes actions to the far right)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        main_layout.addWidget(spacer)

        # Right Zone Assembly
        main_layout.addWidget(self.btn_loop)
        main_layout.addWidget(self.btn_restart)
        main_layout.addWidget(self.btn_pause_resume)
        main_layout.addWidget(self.btn_interrupt)
        main_layout.addWidget(self.btn_stop)

    def connectSignals(self):
        self.btn_pause_resume.clicked.connect(self._onSmartPauseClicked)
        self.btn_loop.clicked.connect(self._updateAutoLoop)
        self.btn_interrupt.clicked.connect(lambda: self.controller.pause(interrupt=True))
        self.btn_stop.clicked.connect(self.controller.stop)
        self.btn_restart.clicked.connect(lambda: self.controller.restart())
        self.btn_toggle.clicked.connect(self._updateEnabled)

    def _updateAutoLoop(self, is_checked: bool):
        """Updates the backend controller when the user clicks the UI."""
        if self.controller.repeat != is_checked:
            self.controller.repeat = is_checked

        self.btn_loop.setChecked(is_checked)

    def _updateEnabled(self, is_checked: bool):
        if self.controller.isEnabled() != is_checked:
            self.controller.setEnabled(is_checked)

        if is_checked:
            self.lbl_status_dot.show()
        else:
            self.lbl_status_dot.hide()

        self.btn_toggle.setChecked(is_checked)

    def _onSmartPauseClicked(self):
        """Handles the dynamic Pause/Resume button."""
        if self.controller.isPaused():
            self.controller.resume()
        else:
            self.controller.pause()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and isinstance(self.controller.name, str):
            self.showContextMenu()

    def showContextMenu(self):
        menu = QMenu(self)
        menu.addAction("Remove").triggered.connect(self._requestDelete)
        menu.exec(QCursor.pos())

    def _requestDelete(self):
        self.removeRequested.emit(self.controller)

    def updateUi(self):
        is_alive = self.controller.isAlive()
        is_paused = self.controller.isPaused()
        is_enabled = self.controller.isEnabled()
        worker_alive = self.controller.worker.isAlive()
        worker_paused = self.controller.worker.isPaused()
        worker_running = worker_alive and not worker_paused
        current_state = self.controller.getState()

        display_text = "Unknown"
        state_color = IconColor.DISABLED
        if not is_enabled:
            display_text = "Disabled"

        elif current_state == TaskState.STOPPED and not self.controller.state_change_by_worker:
            display_text = "Stopped"

        elif current_state == TaskState.FINISHED:
            display_text = "Finished"

        elif current_state == TaskState.INTERRUPTED:
            if worker_running:
                display_text = "Interrupted"
            else:
                display_text = "Interrupted (Waiting for Engine)"
            state_color = "#F46800"

        elif current_state == TaskState.CRASHED:
            display_text = "Crashed"
            state_color = "#f44336"

        elif current_state == TaskState.PAUSED or worker_paused:
            display_text = "Paused" if not worker_paused else "Paused (Waiting for Engine)"
            state_color = "#FFC300"

        elif not worker_running:
            display_text = "Ready (Waiting for Engine)"
            state_color = "#2196f3"

        elif current_state == TaskState.RUNNING:
            display_text = "Running"
            state_color = "#4caf50"

        if is_enabled: self.lbl_status_dot.updateColor(state_color)

        name = self.controller.name
        if name != self.prev_name:
            self.prev_name = name
            self.lbl_name.setText("Task " + (f'"{name}"' if isinstance(name, str) else str(name)))

        self.lbl_state_text.setText(display_text)
        self.btn_loop.setChecked(self.controller.repeat)
        self._updateEnabled(is_enabled)
        self.btn_pause_resume.setChecked(is_alive and is_paused)

        # Dynamic Enabling/Disabling
        if not worker_alive:
            # If the engine is completely stopped, lock all action buttons
            self.btn_pause_resume.setEnabled(False)
            self.btn_interrupt.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.btn_restart.setEnabled(False)
        else:
            # If the engine is actively running, unlock based on live micro-states
            self.btn_pause_resume.setEnabled(is_alive and not worker_paused)
            self.btn_interrupt.setEnabled(is_alive and not self.controller.isInterrupted() and not worker_paused)
            self.btn_stop.setEnabled(is_alive)
            self.btn_restart.setEnabled(is_enabled)
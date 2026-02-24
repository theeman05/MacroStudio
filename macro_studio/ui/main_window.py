import ctypes
import os
import uuid, sys, signal
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QTabWidget, QDockWidget, QStatusBar,QVBoxLayout, QWidget
)
from PySide6.QtGui import QCloseEvent, QFont, QIcon
from PySide6.QtCore import Qt, Signal, QTimer
from pynput import keyboard

from macro_studio.core.types_and_enums import LogPacket, LogLevel, LogErrorPacket, WorkerState
from macro_studio.core.utils import global_logger
from .tabs.recorder_tab import RecorderTab
from .tabs.task_manager_tab import TaskManagerTab
from .theme_manager import ThemeManager
from .tabs.variables_tab import VariablesTab
from .overlay import TransparentOverlay
from .widgets.console import LogWidget
from .widgets.main_window.integrated_header import IntegratedHeader
from .widgets.main_window.runtime_widget import RuntimeWidget


class MainWindow(QMainWindow):
    start_signal = Signal()
    stop_signal = Signal(bool)
    pause_signal = Signal(bool) # Interrupted
    hotkey_signal = Signal(str)

    def __init__(self, task_manager, profile):
        if sys.platform == 'win32':
            my_app_id = 'com.theeman05.macro_studio.client.v1'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)

        self.app = QApplication(sys.argv)
        super().__init__()
        self.setWindowTitle(f"Macro Studio")
        self.resize(900, 700)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self._setIcon()

        global_font = QFont("Segoe UI", 10)
        global_font.setStyleHint(QFont.StyleHint.SansSerif)
        global_font.setWeight(QFont.Weight.Medium)

        self.app.setFont(global_font)

        self.profile = profile
        self.state = WorkerState.IDLE

        # 1. Core UI Components
        self.overlay = TransparentOverlay(self)
        self.manager_tab = TaskManagerTab(task_manager)
        self.variables_tab = VariablesTab(profile.vars, self.overlay)
        self.recorder_tab = RecorderTab(self.overlay, profile)
        ThemeManager.applyTheme(self)

        # 2. Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)  # Remove margin so header touches edges

        # 3. Setup Dock & Toolbar
        self._setupStatusBar()
        self.header = IntegratedHeader(profile.name)
        self._setupLogDock()
        self.main_layout.addWidget(self.header)

        # 4. Create Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self.manager_tab, "Task Manager")
        self.tabs.addTab(self.variables_tab, "Variables")
        self.tabs.addTab(self.recorder_tab, "Recorder")
        self.main_layout.addWidget(self.tabs)

        # Needed for interrrupted close
        timer_breathe = QTimer()
        timer_breathe.timeout.connect(lambda: None)
        timer_breathe.start(500)

        # 5. Connections
        signal.signal(signal.SIGINT, self._handleInterrupt)
        global_logger.log_emitted.connect(self.log)
        self.header.btn_start.clicked.connect(self.onStartClicked)
        self.header.btn_stop.clicked.connect(self.onStopClicked)
        self.header.btn_interrupt.clicked.connect(self.onInterruptClicked)
        self.header.btn_overlay.clicked.connect(self.toggleOverlay)
        self.tabs.currentChanged.connect(self._onTabChanged)
        self.hotkey_signal.connect(self._onHotkey)
        self.listener = keyboard.GlobalHotKeys({
            '<f10>': lambda: self.hotkey_signal.emit("F10"),
            '<f8>': lambda: self.hotkey_signal.emit("F8"),
            '<f6>': lambda: self.hotkey_signal.emit("F6")
        })

        # Initial state stuff
        self.listener.start()
        self._onTabChanged(0)
        self.toggleOverlay()
        self.stopMacroVisuals()

    def _setIcon(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)
        icon_path = os.path.join(root_dir, "assets", "app_icon.ico")
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            self.app.setWindowIcon(app_icon)
        else:
            print(f"ERROR: Icon not found! Check the path above.")

    def _handleInterrupt(self, signum, frame):
        self.stop_signal.emit(True)
        QApplication.instance().quit()

    def _onTabChanged(self, index):
        min_size = getattr(self.tabs.widget(index), 'MIN_SIZE', None)
        if min_size is not None:
            width, height = min_size

            self.setMinimumSize(width, height)

            if self.width() < width or self.height() < height:
                self.resize(width, height)

    def _setupLogDock(self):
        self.log_dock = QDockWidget("Console Output", self)
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)

        self.console = LogWidget()
        self.log_dock.setWidget(self.console)

        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)

    def _setupStatusBar(self):
        status_bar = QStatusBar()
        status_bar.setSizeGripEnabled(False)
        self.setStatusBar(status_bar)

        self.status_label = QLabel("STATUS: IDLE")
        self.status_label.setStyleSheet("font-weight: bold; margin-right: 10px;")

        status_bar.addPermanentWidget(self.status_label)

        self.runtime_widget = RuntimeWidget()
        status_bar.addPermanentWidget(self.runtime_widget, 0)

    # --- ACTION HANDLERS ---
    def onStartClicked(self):
        if self.state == WorkerState.IDLE:
            self.startMacroVisuals()
            self.start_signal.emit()
        elif self.state == WorkerState.RUNNING:
            self.pauseMacroVisuals()
            self.pause_signal.emit(False)
        else:
            self.resumeMacroVisuals()
            self.start_signal.emit()

    def onInterruptClicked(self):
        if self.state in (WorkerState.RUNNING, WorkerState.PAUSED):
            self.pauseMacroVisuals(True)
            self.pause_signal.emit(True)

    def onStopClicked(self):
        self.stopMacroVisuals()
        self.stop_signal.emit(False)

    def startMacroVisuals(self):
        self.setState(WorkerState.RUNNING)
        self.recorder_tab.setEnabled(False)
        self.runtime_widget.startCounting()

    def pauseMacroVisuals(self, interrupt=False):
        self.runtime_widget.pauseCounting()
        self.setState(WorkerState.INTERRUPTED if interrupt else WorkerState.PAUSED)

    def resumeMacroVisuals(self):
        self.setState(WorkerState.RUNNING)
        self.runtime_widget.resumeCounting()

    def stopMacroVisuals(self):
        self.setState(WorkerState.IDLE)
        self.recorder_tab.setEnabled(True)
        self.runtime_widget.stopCounting()

    def setState(self, state: WorkerState):
        self.state = state
        self.status_label.setText(f"STATUS: {state.name}")
        self.header.updateStateVisual(state)

    def toggleOverlay(self):
        self.overlay.showing_geometry = self.header.btn_overlay.isChecked()

    def _onHotkey(self, hotkey_id: str):
        if hotkey_id == "F6":
            self.onStartClicked()
        elif hotkey_id == "F8":
            if self.state == WorkerState.IDLE:
                self.recorder_tab.toggleRecording()
            else:
                self.onInterruptClicked()
        elif hotkey_id == "F10":
            self.stop_signal.emit(False)
            self.stopMacroVisuals()

    def closeEvent(self, event: QCloseEvent):
        self.stop_signal.emit(True)
        self.overlay.destroy()
        self.profile.save()
        event.accept()

    # --- LOGGING (Thread Safe) ---
    def log(self, payload):
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = payload
        if isinstance(payload, LogPacket):
            text = self._formatLogParts(payload)
            task_id = f"Task {payload.task_name}" if payload.task_name != -1 else "SYSTEM"

            # Simple color mapping
            color = "#00ff00" if payload.task_name == -1 else ""
            if payload.level is LogLevel.ERROR:
                color = "red"
            elif payload.level is LogLevel.WARN:
                color = "orange"

            message = f'<span style="color: {color};">[{task_id}] {text}</span>'
        elif isinstance(payload, LogErrorPacket):
            if payload.task_name != -1:
                message = f'<b style="color:darkred">CRITICAL ERROR in Task {payload.task_name}: {payload.message}</b> '
            else:
                message = f'<b style="color:darkred">CRITICAL ERROR: {payload.message}</b> '

            if payload.traceback:
                trace_id = uuid.uuid4().hex
                self.console.traceback_storage[trace_id] = payload.traceback
                message += f'<a href="#id_{trace_id}" style="color:red;">[View Traceback]</a>'

        self.console.append(f'[{timestamp}] {message}')
        # Auto Scroll
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    @staticmethod
    def _formatLogParts(packet: LogPacket):
        # (Same logic as before, just compact)
        return " ".join([x.to_html() if hasattr(x, 'to_html') else str(x) for x in packet.parts])

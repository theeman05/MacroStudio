import uuid, sys
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QTabWidget, QDockWidget, QStatusBar, QProgressBar, QPushButton,
    QVBoxLayout, QWidget, QHBoxLayout, QFrame
)
from PySide6.QtGui import QCloseEvent
from PySide6.QtCore import Qt, Signal
from pynput import keyboard

from macro_creator.core.types_and_enums import LogPacket, LogLevel, LogErrorPacket
from macro_creator.core.utils import global_logger
from .tabs.recorder_tab import RecorderTab
from .theme_manager import ThemeManager
from .tabs.variables_tab import VariablesTab
from .overlay import TransparentOverlay
from .widgets.console import LogWidget
from .shared import setBtnState

class MainWindow(QMainWindow):
    start_signal = Signal()
    stop_signal = Signal(bool)
    pause_signal = Signal()
    hotkey_signal = Signal(str)

    def __init__(self, profile):
        self.app = QApplication(sys.argv)
        super().__init__()
        self.setWindowTitle(f"Macro Engine v1.5")
        self.resize(900, 700)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        self.profile = profile
        self.running = False
        self.paused = False

        # 1. Core UI Components
        self.overlay = TransparentOverlay(self)
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
        self._setupIntegratedHeader(profile.name)
        self._setupLogDock()

        # 4. Create Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self.variables_tab, "Variables")
        self.tabs.addTab(self.recorder_tab, "Recorder")
        self.main_layout.addWidget(self.tabs)

        # 5. Connections
        global_logger.log_emitted.connect(self.log)
        self.tabs.currentChanged.connect(self._onTabChanged)
        self.hotkey_signal.connect(self._onHotkey)
        self.listener = keyboard.GlobalHotKeys({
            '<f10>': lambda: self.hotkey_signal.emit("F10"),
            '<f8>': lambda: self.hotkey_signal.emit("F8"),
            '<f6>': lambda: self.hotkey_signal.emit("F6")
        })
        self.listener.start()
        self._onTabChanged(0)

    def _onTabChanged(self, index):
        min_size = getattr(self.tabs.widget(index), 'MIN_SIZE', None)
        if min_size is not None:
            width, height = min_size

            self.setMinimumSize(width, height)

            if self.width() < width or self.height() < height:
                self.resize(width, height)

    def _setupIntegratedHeader(self, name):
        """Combines Title, Controls, and Overlay into one unified header bar"""
        # 1. The Container (Background & Border)
        header_container = QWidget()
        header_container.setObjectName("header_container")

        # 2. Horizontal Layout
        layout = QHBoxLayout(header_container)
        layout.setContentsMargins(15, 10, 15, 10)  # Padding: Left, Top, Right, Bottom
        layout.setSpacing(15)  # Space between items

        # --- LEFT SIDE: Title ---
        title_label = QLabel(f"MACRO // {name}")
        title_label.setObjectName("header_label")
        title_label.setStyleSheet("font-size: 15px;")
        layout.addWidget(title_label)

        # Vertical Divider Line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #444;")
        line.setFixedHeight(25)
        layout.addWidget(line)

        # --- CENTER LEFT: Main Controls ---

        # START Button
        self.btn_start = QPushButton("START [F6]")
        self.btn_start.setObjectName("btn_start")  # ID for QSS styling
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setMinimumHeight(36)
        self.btn_start.setMinimumWidth(140)
        self.btn_start.clicked.connect(self.onStartClicked)
        layout.addWidget(self.btn_start)

        # STOP Button
        self.btn_stop = QPushButton("STOP [F10]")
        self.btn_stop.setObjectName("btn_stop")  # ID for QSS styling
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setMinimumHeight(36)
        self.btn_stop.setMinimumWidth(120)
        self.btn_stop.clicked.connect(self.stopMacroVisuals)
        layout.addWidget(self.btn_stop)

        # --- SPACER (Pushes Overlay to the right) ---
        layout.addStretch()

        # --- RIGHT SIDE: Overlay Toggle ---
        self.btn_overlay = QPushButton()
        self.btn_overlay.setCheckable(True)
        self.btn_overlay.setChecked(True)
        self.btn_overlay.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_overlay.setFixedWidth(110)
        self.btn_overlay.clicked.connect(self.toggleOverlay)

        layout.addWidget(self.btn_overlay)

        # Add the completed header to the main layout
        self.main_layout.addWidget(header_container)

        # Sync initial state
        self.toggleOverlay()
        self.stopMacroVisuals()

    def _setupLogDock(self):
        self.log_dock = QDockWidget("Console Output", self)
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)

        self.console = LogWidget()
        self.log_dock.setWidget(self.console)

        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)

    def _setupStatusBar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.status_label = QLabel("STATUS: IDLE")
        self.status_label.setStyleSheet("font-weight: bold; margin-right: 15px;")

        self.progress = QProgressBar()
        self.progress.setFixedWidth(200)
        self.progress.setTextVisible(False)

        self.status.addPermanentWidget(self.status_label)
        self.status.addPermanentWidget(self.progress)

    # --- ACTION HANDLERS ---
    def onStartClicked(self):
        if not self.running:
            self.startMacroVisuals()
            self.start_signal.emit()
        elif not self.paused:
            self.pauseMacroVisuals()
            self.pause_signal.emit()
        else:
            self.resumeMacroVisuals()
            self.start_signal.emit()

    def startMacroVisuals(self):
        self.running = True
        self.paused = False
        self._updateStateVisuals("INTERRUPT (F6)", "RUNNING", 0)
        self.recorder_tab.setEnabled(False)

    def pauseMacroVisuals(self):
        self.paused = True
        self._updateStateVisuals("RESUME (F6)", "PAUSED", 100)
        self.progress.setValue(100)

    def resumeMacroVisuals(self):
        self.paused = False
        self._updateStateVisuals("INTERRUPT (F6)", "RUNNING", 0)

    def stopMacroVisuals(self):
        self.running = False
        self.paused = False
        self._updateStateVisuals("START (F6)", "IDLE", 100)
        self.progress.setValue(0)
        self.stop_signal.emit(False)
        self.recorder_tab.setEnabled(True)

    def _updateStateVisuals(self, btn_text: str, status_text: str, progress: int):
        self.btn_start.setText(btn_text)
        setBtnState(self.btn_start, "paused" if ("INTERRUPT" in btn_text) else "")
        self.status_label.setText(f"STATUS: {status_text}")
        self.progress.setVisible(progress != 100)
        self.progress.setRange(0, progress)
        setBtnState(self.progress, "paused" if status_text == "PAUSED" else "")

    def toggleOverlay(self):
        should_show = self.btn_overlay.isChecked()

        if should_show:
            self.btn_overlay.setText("Overlay: ON")
            self.btn_overlay.setStyleSheet("background-color: #d29922; color: #fff;")
        else:
            self.btn_overlay.setText("Overlay: OFF")
            self.btn_overlay.setStyleSheet("")

        self.overlay.showing_geometry = should_show

    def _onHotkey(self, hotkey_id: str):
        if hotkey_id == "F6":
            self.onStartClicked()
        elif hotkey_id == "F8":
            self.recorder_tab.toggleRecording()
        elif hotkey_id == "F10":
            self.stopMacroVisuals()

    def closeEvent(self, event: QCloseEvent):
        self.stop_signal.emit(True)
        self.overlay.destroy()
        self.profile.save()
        event.accept()

    # --- LOGGING (Thread Safe) ---
    def log(self, payload):
        if isinstance(payload, LogPacket):
            timestamp = datetime.now().strftime("%H:%M:%S")
            text = self._formatLogParts(payload)
            task_id = f"Task {payload.task_id}" if payload.task_id != -1 else "SYSTEM"

            # Simple color mapping
            color = "#00ff00" if payload.task_id == -1 else ""
            if payload.level is LogLevel.ERROR:
                color = "red"
            elif payload.level is LogLevel.WARN:
                color = "orange"

            self.console.append(f'[{timestamp}] <span style="color: {color};">[{task_id}] {text}</span>')

        elif isinstance(payload, LogErrorPacket):
            message = f'<b style="color:darkred">CRITICAL ERROR in Task {payload.task_id}: {payload.message}</b> '
            if payload.traceback:
                trace_id = uuid.uuid4().hex
                self.console.traceback_storage[trace_id] = payload.traceback
                message += f'<a href="#id_{trace_id}" style="color:red;">[View Traceback]</a>'
            self.console.append(message)
        elif isinstance(payload, str):
            self.console.append(payload)

        # Auto Scroll
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    @staticmethod
    def _formatLogParts(packet: LogPacket):
        # (Same logic as before, just compact)
        return " ".join([x.to_html() if hasattr(x, 'to_html') else str(x) for x in packet.parts])

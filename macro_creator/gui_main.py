import uuid, sys
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QSplitter, QProgressBar, QStatusBar, QMenu, QTextBrowser,
    QDialog, QPlainTextEdit, QDialogButtonBox
)
from PySide6.QtGui import QCloseEvent, QBrush, QColor, QFont, QDesktopServices
from PySide6.QtCore import Qt, Signal, QPoint, QTimer, QRect, QUrl
from typing import Hashable
from pynput import keyboard

from .type_handler import GlobalTypeHandler
from .overlay import TransparentOverlay
from .types_and_enums import Pickable, CaptureMode, PICKABLE_TYPES, LogPacket, LogLevel, LogErrorPacket
from .variable_config import VariableConfig

# --- THEME & STYLING (QSS) ---
# I'm NGL, I just used AI for this design lmaooo
# This defines the "look and feel" - Dark Mode, Flat Design.
DARK_THEME = """
QMainWindow {
    background-color: #1e1e1e;
}
QWidget {
    color: #e0e0e0;
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
}
/* --- Buttons --- */
QPushButton {
    background-color: #3c3c3c;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px 12px;
    color: #fff;
}
QPushButton:hover {
    background-color: #505050;
    border-color: #666;
}
QPushButton:pressed {
    background-color: #2d2d2d;
}
/* Specific Button Colors */
QPushButton#btn_start {
    background-color: #2ea043; /* Green */
    border: 1px solid #298e3b;
    font-weight: bold;
}
QPushButton#btn_start:hover { background-color: #3fb950; }

QPushButton#btn_stop {
    background-color: #da3633; /* Red */
    border: 1px solid #d82a27;
}
QPushButton#btn_stop:hover { background-color: #f85149; }

QPushButton#btn_reset {
    background-color: #1f6feb; /* Blue */
    border: 1px solid #1158c7;
}

QPushButton#btn_pick {
    background-color: #264f78; 
    border: none; 
    border-radius: 2px;
}
QPushButton#btn_pick:hover { background-color: #3a6ea5; }

QProgressBar {
    border: 1px solid #bbb;
    border-radius: 4px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #4CAF50; /* Green */
    width: 20px;
}

/* DYNAMIC STATES */
QPushButton#btn_start[state="paused"] {
    background-color: #d29922;
    border: 1px solid #b08800;
}
QPushButton#btn_start[state="paused"]:hover {
    background-color: #eac54f; /* Lighter Orange for Hover */
    border-color: #d29922;
}

QProgressBar[state="paused"]::chunk {
    background-color: #FFEB3B; /* Yellow */
}

/* --- Table (Setup Steps) --- */
QTableWidget {
    background-color: #252526;
    border: 1px solid #333;
    gridline-color: #333;
    selection-background-color: #264f78;
}
QHeaderView::section {
    background-color: #333333;
    padding: 4px;
    border: 1px solid #1e1e1e;
    color: #cccccc;
    font-weight: bold;
}

/* --- Console/Logs --- */
QTextEdit {
    background-color: #111111;
    border: 1px solid #333;
    color: white;
    font-family: 'Consolas', monospace;
    font-size: 12px;
}
"""


def _set_btn_state(btn, state_value):
    """
    Updates a dynamic property and forces PyQt to re-read the CSS.
    """
    btn.setProperty("state", state_value)
    btn.style().unpolish(btn)
    btn.style().polish(btn)

def _safe_cast(value_str, target_type, default=None):
    """
    Casts a string to a target type safely.
    :param value_str: The raw string from the UI (e.g., "123", "True")
    :param target_type: The type class (int, float, bool, str)
    :param default: What to return if casting fails (or raise error)
    """
    try:
        # 1. Handle Empty Strings
        if value_str == "" and target_type is not str:
            return default

            # 2. Handle Booleans (The Special Case)
        if target_type is bool:
            # Check against common string representations
            return str(value_str).lower() in ("true", "1", "yes", "on")

        # 3. Handle Standard Types (int, float, str)
        return target_type(value_str)

    except (ValueError, TypeError):
        print(f"Failed to cast '{value_str}' to {target_type}")
        return default

def _flashError(item):
    # Save the original background so we can restore it later
    original_background = item.background()

    # Set Error Color (Light Red)
    red_brush = QBrush(QColor("#FFCDD2"))  # A nice soft red
    item.setBackground(red_brush)

    # Schedule the restoration
    QTimer.singleShot(250, lambda: item.setBackground(original_background))

class MainWindow(QMainWindow):
    # Signals to talk to your Engine
    start_signal = Signal()
    stop_signal = Signal()
    pause_signal = Signal()
    hotkey_signal = Signal(str)

    def __init__(self):
        self.app = QApplication(sys.argv)
        super().__init__()
        self.setWindowTitle("Macro Engine v1.0")
        self.resize(1000, 700)

        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        self.overlay = TransparentOverlay(self)

        self.paused = False
        self.running = False
        self._pending_capture_item = None

        # Apply the Theme
        self.setStyleSheet(DARK_THEME)

        # Main Layout Container
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # Build UI components
        self._setupHeader()
        self._setupControls()
        self._setupSplitView()
        self._setupStatusBar()

        # Do connections
        self.hotkey_signal.connect(self._onHotkey)

        self.listener = keyboard.GlobalHotKeys({
            '<f10>': lambda: self.hotkey_signal.emit("F10"),
            '<f6>': lambda: self.hotkey_signal.emit("F6")
        })
        self.listener.start()
        self.setup_table.itemChanged.connect(self._onTableChanged)

    def _setupHeader(self):
        """Top bar with Title and Overlay Toggle"""
        header_layout = QHBoxLayout()

        title = QLabel("MACRO // CONTROLLER")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #888;")

        self.btn_overlay = QPushButton("Toggle Overlay")
        self.btn_overlay.setCheckable(True)
        self.btn_overlay.setChecked(True)
        self.toggleOverlay()
        self.btn_overlay.clicked.connect(self.toggleOverlay)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_overlay)

        self.main_layout.addLayout(header_layout)

        # Divider line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #333;")
        self.main_layout.addWidget(line)

    def _setupControls(self):
        """The main action buttons"""
        control_layout = QHBoxLayout()

        self.btn_start = QPushButton("START [F6]")
        self.btn_start.setObjectName("btn_start")  # ID for CSS
        self.btn_start.setMinimumHeight(40)
        self.btn_start.clicked.connect(self.onStartClicked)

        self.btn_stop = QPushButton("STOP [F10]")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.clicked.connect(self.stopMacroVisuals)

        control_layout.addWidget(self.btn_start, 3)
        control_layout.addWidget(self.btn_stop, 2)

        self.main_layout.addLayout(control_layout)

    def _setupSplitView(self):
        """Splitter between Setup List and Console"""
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. SETUP TABLE
        self.setup_table = QTableWidget()
        labels = ["Variable ID", "Type", "Value"]
        self.setup_table.setColumnCount(len(labels))
        self.setup_table.setHorizontalHeaderLabels(labels)

        header = self.setup_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID fits content
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Type fits content
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Value takes space

        # 2. CONSOLE
        self.console = LogWidget()

        splitter.addWidget(self.setup_table)
        splitter.addWidget(self.console)
        splitter.setStretchFactor(0, 3)  # Table takes 75% height
        splitter.setStretchFactor(1, 1)  # Console takes 25%

        self.main_layout.addWidget(splitter)

        self.setup_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setup_table.customContextMenuRequested.connect(self._openMenu)

        # Table hover stuff
        self.setup_table.setMouseTracking(True)
        self.setup_table.itemEntered.connect(self._onItemHovered)
        self.setup_table.leaveEvent = self._onTableLeave

    def _setupStatusBar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.status_label = QLabel("STATUS: IDLE")
        self.status_label.setStyleSheet("font-weight: bold; margin-right: 15px;")

        self.progress = QProgressBar()
        self.progress.setFixedWidth(200)
        self.progress.setTextVisible(False)
        _set_btn_state(self.progress, "")

        self.status.addPermanentWidget(self.status_label)
        self.status.addPermanentWidget(self.progress)

    def _onTableChanged(self, item):
        """
        Triggered when ANY cell is changed (by user or code).
        """
        # 1. We only care if the user edited the "Value" column (Column 2)
        if item.column() != 2:
            return

        var_config = item.data(Qt.ItemDataRole.UserRole)
        if var_config is None:
            return # This wasn't a value cell (maybe it was a header?)

        if var_config.data_type is bool:
            var_config.value = item.checkState() == Qt.CheckState.Checked
        else:
            success = True
            try:
                var_config.value = GlobalTypeHandler.parse(var_config.data_type, item.text())
            except (ValueError, TypeError):
                success = False

            if not success:
                self._updateVariableDisplay(item)
                _flashError(item)
            elif var_config.data_type in PICKABLE_TYPES and var_config.value:
                # Update overlay
                self.overlay.update()

    def _onItemHovered(self, item):
        config = item.data(Qt.ItemDataRole.UserRole)
        prev_highlighted = self.overlay.highlighted_config
        self.overlay.highlighted_config = config if (config and config.data_type in PICKABLE_TYPES) else None
        # If the config changed, update the overlay
        if prev_highlighted != self.overlay.highlighted_config:
            self.overlay.update()

    def _onTableLeave(self, event):
        if self.overlay.highlighted_config:
            self.overlay.highlighted_config = None
            self.overlay.update()
        QTableWidget.leaveEvent(self.setup_table, event)

    def _onHotkey(self, hotkey_id: str):
        if hotkey_id == "F6":
            self.onStartClicked()
        elif hotkey_id == "F10":
            self.stopMacroVisuals()

    def _openMenu(self, position):
        item = self.setup_table.itemAt(position)
        if not item: return

        config = item.data(Qt.ItemDataRole.UserRole)
        if not config: return

        if config.data_type in PICKABLE_TYPES:
            menu = QMenu()
            capture_action = menu.addAction("Capture Data")

            # 3. Connect Action
            # Use functools.partial to pass the specific config object to your capture tool
            action = menu.exec(self.setup_table.viewport().mapToGlobal(position))

            if action == capture_action:
                self._startCaptureOverlay(item, config)

    # --- FUNCTIONALITY HOOKS ---
    def addSetupItem(self, var_id: Hashable, config: VariableConfig):
        """
        Adds a row WITHOUT triggering the 'itemChanged' signal.
        """
        # Block signals so adding rows doesn't trigger "on_table_changed"
        self.setup_table.blockSignals(True)

        row = self.setup_table.rowCount()
        self.setup_table.insertRow(row)

        # Col 0: ID (Read only)
        id_item = QTableWidgetItem(str(var_id))
        id_item.setFlags(id_item.flags() ^ Qt.ItemFlag.ItemIsEditable)  # Remove edit flag
        self.setup_table.setItem(row, 0, id_item)

        # Col 1: Type (Read only)
        type_item = QTableWidgetItem(GlobalTypeHandler.getDisplayName(config.data_type))
        type_item.setFlags(type_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
        self.setup_table.setItem(row, 1, type_item)

        # Col 2: Value
        val_item = QTableWidgetItem()
        if config.data_type is bool:
            val_item.setFlags(val_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        if config.data_type is QRect:
            val_item.setToolTip("Format: x, y, width, height | Right click to open action menu")
        elif config.data_type is QPoint:
            val_item.setToolTip("Format: x, y | Right click to open action menu")
        else:
            val_item.setToolTip(config.pick_hint)

        self.setup_table.setItem(row, 2, val_item)
        val_item.setData(Qt.ItemDataRole.UserRole, config)

        # Unblock signals, lol updating variable display unblocks
        self._updateVariableDisplay(val_item)

        if config.data_type in PICKABLE_TYPES:
            self.overlay.render_geometry.append(config)

    @staticmethod
    def _formatLogParts(packet: LogPacket):
        html_parts = []
        for item in packet.parts:
            if hasattr(item, 'to_html'):
                # Smart objects that know how to format themselves
                html_parts.append(item.to_html())
            else:
                # Fallback: Use global casting
                html_parts.append(GlobalTypeHandler.format(item))

        # Join them with comma separated spaces
        return ", ".join(html_parts)

    def log(self, payload):
        """Thread-safe logging helper"""
        if isinstance(payload, LogPacket):
            timestamp = datetime.now().strftime("%H:%M:%S")
            text = self._formatLogParts(payload)
            task_id = f"Task {payload.task_id}" if payload.task_id != -1 else "SYSTEM"
            if payload.level is LogLevel.ERROR:
                color_html = "red"
            elif payload.level is LogLevel.WARN:
                color_html = "orange"
            elif payload.task_id == -1:
                color_html = "#00ff00" # Green
            else:
                color_html = ""

            self.console.append(f'[{timestamp}] <span style="color: {color_html};">[{task_id}] {text}</span>')
        elif isinstance(payload, LogErrorPacket):
            trace_id = uuid.uuid4().hex

            self.console.traceback_storage[trace_id] = payload.traceback

            link_href = f"#id_{trace_id}"

            log_msg = (
                f'<b style="color:darkred">CRITICAL ERROR in Task {payload.task_id}: {payload.message}</b> '
                f'<a href="{link_href}" style="color:red; text-decoration: underline;">[View Traceback]</a>'
            )

            self.console.append(log_msg)
        elif isinstance(payload, str):
            self.console.append(payload)

        # Auto scroll to bottom
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def toggleOverlay(self):
        if self.btn_overlay.isChecked():
            self.btn_overlay.setStyleSheet("background-color: #d29922; color: #fff;")  # Yellow
            self.overlay.show()
        else:
            self.btn_overlay.setStyleSheet("")
            self.overlay.hide()

    def _startCaptureOverlay(self, item, config: VariableConfig):
        """Begins the picking process"""
        self._pending_capture_item = item
        self.hide()
        var_type = config.data_type
        pick_hint = config.pick_hint
        capture_mode = var_type
        if var_type is QRect:
            capture_mode = CaptureMode.REGION
        elif var_type is QPoint:
            capture_mode = CaptureMode.POINT

        self.overlay.startCapture(capture_mode, pick_hint)

    def _updateVariableDisplay(self, val_item: QTableWidgetItem):
        """Update the widget item's display based on the config value"""
        config: VariableConfig = val_item.data(Qt.ItemDataRole.UserRole)
        self.setup_table.blockSignals(True)
        try:
            if config.data_type is bool:
                val_item.setCheckState(Qt.CheckState.Checked if config.value else Qt.CheckState.Unchecked)
            else:
                val_item.setText(GlobalTypeHandler.format(config.value))
        finally:
            self.setup_table.blockSignals(False)

    def afterCaptureEnded(self, result=None):
        """Should be called after picking completed or exited"""
        value_item = self._pending_capture_item
        self._pending_capture_item = None
        if result:
            value_item.data(Qt.ItemDataRole.UserRole).value = result # Update config data
            self._updateVariableDisplay(value_item)  # Update local UI

        # Hide the UI again
        self.overlay.setClickThrough(True)
        self.toggleOverlay()
        self.show()

    def onStartClicked(self):
        if not self.running:
            # Case 1: Starting from scratch
            self.startMacroVisuals()
            self.start_signal.emit()
        elif not self.paused:
            # Case 2: Currently Running -> User wants to PAUSE
            self.pauseMacroVisuals()
            self.pause_signal.emit()
        else:
            # Case 3: Currently Paused -> User wants to RESUME
            self.resumeMacroVisuals()
            self.start_signal.emit()

    def startMacroVisuals(self):
        self.running = True
        self.paused = False
        self._updateStartBtnAndStatus("PAUSE [F6]","RUNNING", 0)

    def pauseMacroVisuals(self):
        self.paused = True
        self._updateStartBtnAndStatus("RESUME","PAUSED", 100)
        self.progress.setValue(100)

    def resumeMacroVisuals(self):
        self.paused = False
        self._updateStartBtnAndStatus("HARD PAUSE [F6]","RUNNING", 0)

    def stopMacroVisuals(self):
        self.running = False
        self.paused = False
        self._updateStartBtnAndStatus("START [F6]","IDLE", 100)
        self.progress.setValue(0)
        self.stop_signal.emit()

    def _updateStartBtnAndStatus(self, text: str, status_text: str, max_range: int):
        self.btn_start.setText(text)
        _set_btn_state(self.btn_start, "paused" if ("PAUSE" in text) else "")
        self.status_label.setText(f"STATUS: {status_text}")
        self.progress.setRange(0, max_range)
        _set_btn_state(self.progress, "paused" if status_text == "PAUSED" else "")

    def closeEvent(self, event: QCloseEvent):
        # 1. Emit stop signal to kill any running macros
        self.stop_signal.emit()
        self.overlay.destroy()

        # 2. TODO Save settings/variables to a JSON file here

        # 3. Accept the event to let the window close
        event.accept()


class LogWidget(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.setOpenExternalLinks(False)
        self.setPlaceholderText("System initialized. Waiting for tasks...")
        self.anchorClicked.connect(self._onLinkClicked)
        self.traceback_storage = {}

    def _onLinkClicked(self, url: QUrl):
        # 1. Check if it's our custom scheme
        url_str = url.toString()
        if url_str.startswith("#id_"):
            # Strip the "#id_" part to get the clean UUID
            trace_id = url_str.replace("#id_", "")

            trace_text = self.traceback_storage.get(trace_id, "Traceback not found.")

            # Show the dialog
            dialog = TracebackDialog(trace_text, self)
            dialog.exec()
            return

        if url.scheme() in ["http", "https"]:
            QDesktopServices.openUrl(url)

class TracebackDialog(QDialog):
    def __init__(self, traceback_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Error Traceback")
        self.resize(700, 500)  # Set a nice big default size

        layout = QVBoxLayout(self)

        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlainText(traceback_text)

        # Set a Monospace Font (Critical for code readability)
        font = QFont("Courier New", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_area.setFont(font)

        # Disable line wrapping so long lines don't look messy
        self.text_area.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        layout.addWidget(self.text_area)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)  # Close when clicked

        copy_btn = buttons.addButton("Copy", QDialogButtonBox.ButtonRole.ActionRole)
        copy_btn.clicked.connect(self.copyToClipboard)

        layout.addWidget(buttons)

    def copyToClipboard(self):
        self.text_area.selectAll()
        self.text_area.copy()
        # Deselect to look clean
        cursor = self.text_area.textCursor()
        cursor.clearSelection()
        self.text_area.setTextCursor(cursor)

# --- ENTRY POINT (For testing visual look) ---
if __name__ == "__main__":
    debug_vars = {}
    window = MainWindow()

    def _addDummyVariable(key: Hashable, data_type: Pickable | object, default_val: object = None,
                    pick_hint: str = None):
        config = VariableConfig(data_type, default_val, pick_hint)
        debug_vars[key] = config
        window.addSetupItem(key, config)

    # Add dummy data to show off the table
    _addDummyVariable("farm_location", int, 1)
    _addDummyVariable("loop_delay", CaptureMode.REGION, None, "Burger")
    _addDummyVariable("enable_combat", bool, True)

    window.show()
    sys.exit(window.app.exec())
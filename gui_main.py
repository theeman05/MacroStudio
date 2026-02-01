import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QTextEdit, QSplitter, QProgressBar, QStatusBar
)
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtCore import Qt, pyqtSignal
from functools import partial
from typing import cast, Hashable

# --- THEME & STYLING (QSS) ---
# I'm NGL, I just used AI for this lmaooo
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

/* DYNAMIC STATES */
QPushButton#btn_start[state="paused"] {
    background-color: #d29922;
    border: 1px solid #b08800;
}
QPushButton#btn_start[state="paused"]:hover {
    background-color: #eac54f; /* Lighter Orange for Hover */
    border-color: #d29922;
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
    color: #00ff00; /* Hacker Green for logs */
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


class MainWindow(QMainWindow):
    # Signals to talk to your Engine
    start_signal = pyqtSignal()
    stop_signal = pyqtSignal()
    pause_signal = pyqtSignal()
    variable_edited = pyqtSignal(str, str) # var_id, new value string
    request_capture_signal = pyqtSignal(int, object, object, str) # Column number, var_id, var_type, display_str

    def __init__(self, overlay):
        super().__init__()
        self.setWindowTitle("Macro Engine v1.0")
        self.resize(1000, 700)

        self.overlay = overlay
        self.paused = False
        self.running = False

        # Apply the Theme
        self.setStyleSheet(DARK_THEME)

        # Main Layout Container
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # Build UI components
        self._setup_header()
        self._setup_controls()
        self._setup_split_view()
        self._setup_statusbar()

        # Do connections
        # TODO: Make table items editable?
        # self.setup_table.itemChanged.connect(self._on_table_changed)

    def _setup_header(self):
        """Top bar with Title and Overlay Toggle"""
        header_layout = QHBoxLayout()

        title = QLabel("MACRO // CONTROLLER")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #888;")

        self.btn_overlay = QPushButton("Toggle Overlay")
        self.btn_overlay.setCheckable(True)
        self.btn_overlay.setChecked(True)
        self.toggle_overlay()
        self.btn_overlay.clicked.connect(self.toggle_overlay)

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

    def _setup_controls(self):
        """The main action buttons"""
        control_layout = QHBoxLayout()

        self.btn_start = QPushButton("START ENGINE")
        self.btn_start.setObjectName("btn_start")  # ID for CSS
        self.btn_start.setMinimumHeight(40)
        self.btn_start.clicked.connect(self.on_start_click)

        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.clicked.connect(self.stop_macro_visuals)

        control_layout.addWidget(self.btn_start, 3)
        control_layout.addWidget(self.btn_stop, 2)

        self.main_layout.addLayout(control_layout)

    def _setup_split_view(self):
        """Splitter between Setup List and Console"""
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. SETUP TABLE
        self.setup_table = QTableWidget()
        labels = ["Variable ID", "Type", "Value", "Action"]
        self.setup_table.setColumnCount(len(labels))
        self.setup_table.setHorizontalHeaderLabels(labels)

        header = self.setup_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID fits content
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Type fits content
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Value takes space
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # Action is fixed size
        self.setup_table.setColumnWidth(3, 80)  # 80px for the button

        # 2. CONSOLE
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("System initialized. Waiting for tasks...")

        splitter.addWidget(self.setup_table)
        splitter.addWidget(self.console)
        splitter.setStretchFactor(0, 3)  # Table takes 75% height
        splitter.setStretchFactor(1, 1)  # Console takes 25%

        self.main_layout.addWidget(splitter)

    def _setup_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.status_label = QLabel("STATUS: READY")
        self.status_label.setStyleSheet("font-weight: bold; margin-right: 15px;")

        self.progress = QProgressBar()
        self.progress.setFixedWidth(200)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("QProgressBar::chunk { background-color: #2ea043; }")

        self.status.addPermanentWidget(self.status_label)
        self.status.addPermanentWidget(self.progress)

    def _on_table_changed(self, item):
        """
        Triggered when ANY cell is changed (by user or code).
        """
        # 1. We only care if the user edited the "Value" column (Column 2)
        if item.column() != 2:
            return

        # 2. Get the Row index
        row = item.row()

        # 3. Retrieve the Variable ID from Column 0 (which should be read-only)
        id_item = self.setup_table.item(row, 0)
        variable_id = id_item.text()

        # 4. Get the new Value
        new_value = item.text()

        # 5. Send it to the Engine
        print(f"DEBUG: GUI changed {variable_id} -> {new_value}")
        self.variable_edited.emit(variable_id, new_value)

    # --- FUNCTIONALITY HOOKS ---

    def add_setup_item(self, var_id: Hashable, var_type, var_desc, default_val: str=""):
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
        type_item = QTableWidgetItem(str(var_type))
        type_item.setFlags(type_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
        self.setup_table.setItem(row, 1, type_item)

        # Col 2: Value
        self.setup_table.setItem(row, 2, QTableWidgetItem(str(default_val)))

        # Col 3: The "Pick" Button
        # We only add a button if the type requires Mouse Input
        btn = QPushButton("Pick")
        btn.setObjectName("btn_pick")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # LOGIC: Use partial to freeze the var_id and type into the function call
        btn.clicked.connect(partial(self.on_pick_click, row, var_id, var_type, var_desc))

        # INSERT: Add widget to the cell
        self.setup_table.setCellWidget(row, 3, btn)

        # Unblock signals
        self.setup_table.blockSignals(False)

    def log(self, message: str):
        """Thread-safe logging helper"""
        self.console.append(f">> {message}")
        # Auto scroll to bottom
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def toggle_overlay(self):
        if self.btn_overlay.isChecked():
            self.btn_overlay.setStyleSheet("background-color: #d29922; color: #fff;")  # Yellow
            self.overlay.show()
        else:
            self.btn_overlay.setStyleSheet("")
            self.overlay.hide()

    def on_pick_click(self, row, var_id, var_type, var_desc):
        """Emits signal to Engine to start the picking process"""
        self.request_capture_signal.emit(row, var_id, var_type, var_desc)

    def update_variable_value(self, row: int, new_value):
        """Helper for the Engine to call after capture is done"""
        self.setup_table.item(row, 2).setText(new_value is not None and str(new_value) or "")
        pick_btn = cast(QPushButton, self.setup_table.cellWidget(row, 3))
        pick_btn.setText("Pick")
        _set_btn_state(pick_btn, "")

    def on_start_click(self):
        if not self.running:
            # Case 1: Starting from scratch
            self.start_macro_visuals()
            self.start_signal.emit()
        elif not self.paused:
            # Case 2: Currently Running -> User wants to PAUSE
            self.pause_macro_visuals()
            self.pause_signal.emit()
        else:
            # Case 3: Currently Paused -> User wants to RESUME
            self.resume_macro_visuals()
            self.start_signal.emit()

    def start_macro_visuals(self):
        self.running = True
        self.paused = False
        self._updateStartBtnAndStatus("PAUSE","RUNNING", "Starting...", 0)

    def pause_macro_visuals(self):
        self.paused = True
        self._updateStartBtnAndStatus("RESUME","PAUSED", "Macro Paused.", 100)

    def resume_macro_visuals(self):
        self.paused = False
        self._updateStartBtnAndStatus("PAUSE","RUNNING", "Resuming...", 0)

    def stop_macro_visuals(self):
        self.running = False
        self.paused = False
        self._updateStartBtnAndStatus("START ENGINE","STOPPED", "Stopping...", 100)
        self.progress.setValue(0)
        self.stop_signal.emit()

    def _updateStartBtnAndStatus(self, text: str, status_text: str, log_text: str, max_range: int):
        self.btn_start.setText(text)
        _set_btn_state(self.btn_start, "paused" if text == "PAUSE" else "")
        self.status_label.setText(f"STATUS: {status_text}")
        self.progress.setRange(0, max_range)
        self.log(log_text)

    def closeEvent(self, event: QCloseEvent):
        # 1. Emit stop signal to kill any running macros
        self.stop_signal.emit()
        self.overlay.destroy()

        # 2. TODO Save settings/variables to a JSON file here

        # 3. Accept the event to let the window close
        event.accept()


# --- ENTRY POINT (For testing visual look) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow(app)

    # Add dummy data to show off the table
    window.add_setup_item("farm_location", "ClickMode.SET_POS", "(1920, 1080)")
    window.add_setup_item("loop_delay", "ClickMode.NUMBER", "5.2")
    window.add_setup_item("enable_combat", "ClickMode.BOOL", "True")

    window.show()
    sys.exit(app.exec())
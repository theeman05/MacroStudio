import uuid, sys
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QSplitter, QProgressBar, QStatusBar, QMenu, QTextBrowser,
    QDialog, QPlainTextEdit, QDialogButtonBox, QStyledItemDelegate
)
from PySide6.QtGui import QCloseEvent, QBrush, QColor, QFont, QDesktopServices, QAction
from PySide6.QtCore import Qt, Signal, QTimer, QUrl, QEvent
from pynput import keyboard

from .capture_type_registry import GlobalCaptureRegistry
from .type_handler import GlobalTypeHandler
from .overlay import TransparentOverlay
from .types_and_enums import LogPacket, LogLevel, LogErrorPacket
from .variable_config import VariableConfig
from .theme_manager import ThemeManager


EMPTY_VALUE_STR = "<Empty>"

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

def _updateTypeItem(type_item: QTableWidgetItem, value_item: QTableWidgetItem, config: VariableConfig):
    capture_mode = GlobalCaptureRegistry.getModeFromType(config.data_type)
    if capture_mode:
        tip = f"{GlobalCaptureRegistry.get(capture_mode).tip} | Right click to open action menu and capture"
    else:
        tip = config.hint or "Manually edit this value."

    type_item.setText(GlobalTypeHandler.getDisplayName(config.data_type))
    value_item.setToolTip(tip)

    # Make foreground look nice for capturable items
    if capture_mode: type_item.setForeground(QBrush(QColor("#aaddff")))  # Light Blue

class MainWindow(QMainWindow):
    # Signals to talk to your Engine
    start_signal = Signal()
    stop_signal = Signal(bool)
    pause_signal = Signal()
    hotkey_signal = Signal(str)

    def __init__(self, name):
        self.app = QApplication(sys.argv)
        super().__init__()
        self.setWindowTitle("Macro Engine v1.0")
        self.resize(700, 700)

        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        self.overlay = TransparentOverlay(self)

        self.paused = False
        self.running = False
        self._pending_capture_item = None

        # Apply the Theme
        ThemeManager.applyTheme(self)

        # Main Layout Container
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # Build UI components
        self._setupHeader(name)
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

    def _setupHeader(self, name):
        """Top bar with Title and Overlay Toggle"""
        header_layout = QHBoxLayout()

        title = QLabel(f"MACRO // {name}")
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
        self.setup_table.setItemDelegateForColumn(2, SmartDelegate(self.setup_table))

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

    def _getVarConfig(self, item: QTableWidgetItem):
        return self.setup_table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)

    def _onTableChanged(self, item):
        """
        Triggered when ANY cell is changed (by user or code).
        """
        # We only care if the user edited the "Value" column (Column 2)
        # Also Return if it's been marked as empty and the text is already the empty str
        if item.column() != 2 or (item.data(Qt.ItemDataRole.UserRole) and item.text() == EMPTY_VALUE_STR):
            return

        var_config = self._getVarConfig(item)
        if var_config is None:
            return # This wasn't a value cell (maybe it was a header?)

        if var_config.data_type is bool:
            var_config.value = item.checkState() == Qt.CheckState.Checked
        else:
            success = True
            try:
                var_config.value = GlobalTypeHandler.fromString(var_config.data_type, item.text())
            except (ValueError, TypeError):
                success = False

            if not success:
                self._updateVariableDisplay(item, var_config)
                _flashError(item)
            elif GlobalCaptureRegistry.containsType(var_config.data_type) and var_config.value:
                self.overlay.update()

    def _onItemHovered(self, item):
        config = self._getVarConfig(item)
        prev_highlighted = self.overlay.highlighted_config
        self.overlay.highlighted_config = config if (config and GlobalCaptureRegistry.containsType(config.data_type)) else None
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

        config = self._getVarConfig(item)
        if not config: return

        capture_mode = GlobalCaptureRegistry.getModeFromType(config.data_type)
        if capture_mode:
            menu = QMenu()
            capture_action = menu.addAction("Capture Data")

            # Use functools.partial to pass the specific config object to your capture tool
            action = menu.exec(self.setup_table.viewport().mapToGlobal(position))

            if action == capture_action:
                self._pending_capture_item = item
                self.hide()
                GlobalCaptureRegistry.get(capture_mode).capture_handler(self, config)


    def _updateValueText(self, item: QTableWidgetItem, config: VariableConfig):
        if config.data_type is bool:
            item.setText("")
            item.setData(Qt.ItemDataRole.UserRole, False)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setData(Qt.ItemDataRole.CheckStateRole, Qt.CheckState.Checked if config.value else Qt.CheckState.Unchecked)
            return
        else:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            item.setData(Qt.ItemDataRole.CheckStateRole, None)

        font = item.font()
        # Make the value look different based on if it's empty or not
        if config.value is None:
            item.setData(Qt.ItemDataRole.UserRole, True)
            item.setText(EMPTY_VALUE_STR)
            font.setItalic(True)
            item.setFont(font)
            item.setForeground(QBrush(QColor("gray")))
        else:
            item.setData(Qt.ItemDataRole.UserRole, False)
            item.setText(GlobalTypeHandler.toString(config.value))
            font.setItalic(False)
            item.setFont(font)
            item.setForeground(self.palette().text())

    # --- FUNCTIONALITY HOOKS ---
    def addSetupItem(self, name: str, config: VariableConfig):
        """ Adds a new row WITHOUT triggering the 'itemChanged' signal."""
        # Block signals so adding rows doesn't trigger "on_table_changed"
        self.setup_table.blockSignals(True)

        row = self.setup_table.rowCount()
        config.row = row
        self.setup_table.insertRow(row)

        # Col 0: ID (Read only)
        id_item = QTableWidgetItem(name)
        id_item.setFlags(id_item.flags() ^ Qt.ItemFlag.ItemIsEditable)  # Toggle edit flag off
        id_item.setData(Qt.ItemDataRole.UserRole, config)
        self.setup_table.setItem(row, 0, id_item)

        # Refreshable stuff:

        # Col 1: Type (Read only)
        type_item = QTableWidgetItem()
        type_item.setFlags(type_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
        self.setup_table.setItem(row, 1, type_item)

        # Col 2: Value
        val_item = QTableWidgetItem()
        self.setup_table.setItem(row, 2, val_item)

        # Refresh the view to update properties
        self.refreshSetupItemView(config)

    def refreshSetupItemView(self, config: VariableConfig):
        row = config.row
        if row is None:
            self.log(LogPacket(("Error while refreshing view for", config, "row could not be found."),
                               task_id=-1, level=LogLevel.ERROR))
            return

        # Update data_type, hint, value
        self.setup_table.blockSignals(True)
        try:
            value_item = self.setup_table.item(row, 2)
            self._updateValueText(value_item, config)
            _updateTypeItem(self.setup_table.item(row, 1), value_item, config)

            # Remove or add to render geom
            if GlobalCaptureRegistry.containsType(config.data_type):
                self.overlay.render_geometry.add(config)
            elif config in self.overlay.render_geometry:
                self.overlay.render_geometry.remove(config)
                if self.overlay.highlighted_config == config:
                    self.overlay.highlighted_config = None
                self.overlay.update()
        finally:
            self.setup_table.blockSignals(False)

    @staticmethod
    def _formatLogParts(packet: LogPacket):
        html_parts = []
        for item in packet.parts:
            if hasattr(item, 'to_html'):
                # Smart objects that know how to format themselves
                html_parts.append(item.to_html())
            else:
                # Fallback: Use global casting
                html_parts.append(GlobalTypeHandler.toString(item))

        # Join them with spaces like python print
        return " ".join(html_parts)

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

    def _updateVariableDisplay(self, val_item: QTableWidgetItem, config: VariableConfig):
        """Update the widget item's display based on the config value"""
        self.setup_table.blockSignals(True)
        try:
            self._updateValueText(val_item, config)
        finally:
            self.setup_table.blockSignals(False)

    def afterCaptureEnded(self, result=None):
        """Should be called after picking completed or exited"""
        value_item = self._pending_capture_item
        self._pending_capture_item = None
        if result:
            config = self._getVarConfig(value_item)
            config.value = result # Update config data
            self._updateVariableDisplay(value_item, config)  # Update local UI

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
        self._updateStartBtnAndStatus("HARD PAUSE [F6]","RUNNING", 0)

    def pauseMacroVisuals(self):
        self.paused = True
        self._updateStartBtnAndStatus("RESUME [F6]","PAUSED", 100)
        self.progress.setValue(100)

    def resumeMacroVisuals(self):
        self.paused = False
        self._updateStartBtnAndStatus("HARD PAUSE [F6]","RUNNING", 0)

    def stopMacroVisuals(self):
        self.running = False
        self.paused = False
        self._updateStartBtnAndStatus("START [F6]","IDLE", 100)
        self.progress.setValue(0)
        self.stop_signal.emit(False)

    def _updateStartBtnAndStatus(self, text: str, status_text: str, max_range: int):
        self.btn_start.setText(text)
        _set_btn_state(self.btn_start, "paused" if ("PAUSE" in text) else "")
        self.status_label.setText(f"STATUS: {status_text}")
        self.progress.setRange(0, max_range)
        _set_btn_state(self.progress, "paused" if status_text == "PAUSED" else "")

    def closeEvent(self, event: QCloseEvent):
        # 1. Emit stop signal to kill any running macros
        self.stop_signal.emit(True)
        self.overlay.destroy()

        # 2. TODO Save settings/variables to a JSON file here

        # 3. Accept the event to let the window close
        event.accept()

class SmartDelegate(QStyledItemDelegate):
    def editorEvent(self, event, model, option, index):
        # Handle left mouse clicks for booleans
        if event.type() == QEvent.Type.MouseButtonRelease:
            # Check if this item is actually a checkbox
            current_state = index.data(Qt.ItemDataRole.CheckStateRole)
            if current_state is not None:
                new_state = Qt.CheckState.Unchecked if current_state == Qt.CheckState.Checked else Qt.CheckState.Checked
                model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)

                # Return True so Qt stops processing the event
                return True

        return super().editorEvent(event, model, option, index)

    def setEditorData(self, editor, index):
        # This function runs right before the user starts typing

        # Check your existing UserRole
        is_empty = index.data(Qt.ItemDataRole.UserRole)

        if is_empty:
            # If it's technically empty, start with a BLANK textbox instead of showing "<Empty>"
            editor.setText("")
        else:
            # Otherwise, show the existing text normally
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        # This runs when user finishes typing (presses Enter)
        new_text = editor.text()

        if new_text == "":
            # User cleared the box -> Mark as Empty
            model.setData(index, True, Qt.ItemDataRole.UserRole)  # Update flag
        else:
            # User typed something -> Mark as Not Empty
            model.setData(index, False, Qt.ItemDataRole.UserRole)
            # Try to save the actual text
            model.setData(index, new_text, Qt.ItemDataRole.DisplayRole)

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

    def contextMenuEvent(self, event):
        # Get the standard right-click menu (Copy, Select All, etc.)
        # We start with this so we don't lose the default features.
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        clear_action = QAction("Clear Console", self)
        clear_action.triggered.connect(self.clear)
        menu.addAction(clear_action)
        menu.exec(event.globalPos())

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

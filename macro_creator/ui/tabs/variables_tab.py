from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu, QStyledItemDelegate
)
from PySide6.QtGui import QBrush, QColor
from PySide6.QtCore import Qt, QTimer, QEvent

from macro_creator.core.capture_type_registry import GlobalCaptureRegistry
from macro_creator.core.type_handler import GlobalTypeHandler
from macro_creator.core.variable_config import VariableConfig
from macro_creator.ui.shared import EMPTY_VALUE_STR, updateItemPlaceholder


# --- Helper Functions ---
def _flashError(item):
    original_background = item.background()
    red_brush = QBrush(QColor("#FFCDD2"))
    item.setBackground(red_brush)
    QTimer.singleShot(250, lambda: item.setBackground(original_background))


def _updateTypeItem(type_item: QTableWidgetItem, value_item: QTableWidgetItem, config: VariableConfig):
    capture_mode = GlobalCaptureRegistry.getModeFromType(config.data_type)
    if capture_mode:
        tip = f"{GlobalCaptureRegistry.get(capture_mode).tip} | Right click to capture"
    else:
        tip = config.hint or "Manually edit this value."

    type_item.setText(GlobalTypeHandler.getDisplayName(config.data_type))
    value_item.setToolTip(tip)

    if capture_mode:
        type_item.setForeground(QBrush(QColor("#1158c7")))


class SmartDelegate(QStyledItemDelegate):
    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            current_state = index.data(Qt.ItemDataRole.CheckStateRole)
            if current_state is not None:
                new_state = Qt.CheckState.Unchecked if current_state == Qt.CheckState.Checked else Qt.CheckState.Checked
                model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
                return True
        return super().editorEvent(event, model, option, index)

    def setEditorData(self, editor, index):
        is_empty = index.data(Qt.ItemDataRole.UserRole)
        if is_empty:
            editor.setText("")
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        new_text = editor.text()
        if new_text == "":
            model.setData(index, True, Qt.ItemDataRole.UserRole)
        else:
            model.setData(index, False, Qt.ItemDataRole.UserRole)
            model.setData(index, new_text, Qt.ItemDataRole.DisplayRole)


class VariablesTab(QWidget):
    def __init__(self, overlay_ref):
        super().__init__()
        self.overlay = overlay_ref
        self._pending_capture_item = None

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.setup_table = QTableWidget()
        labels = ["Variable ID", "Type", "Value"]
        self.setup_table.setColumnCount(len(labels))
        self.setup_table.setHorizontalHeaderLabels(labels)
        self.setup_table.setItemDelegateForColumn(2, SmartDelegate(self.setup_table))

        header = self.setup_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        # Context Menu & Events
        self.setup_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setup_table.customContextMenuRequested.connect(self._openMenu)
        self.setup_table.setMouseTracking(True)
        self.setup_table.itemEntered.connect(self._onItemHovered)
        self.setup_table.itemChanged.connect(self._onTableChanged)

        self.layout.addWidget(self.setup_table)

    def leaveEvent(self, event):
        # Clear highlights when mouse leaves the tab
        if self.overlay.highlighted_config:
            self.overlay.highlighted_config = None
            self.overlay.update()
        super().leaveEvent(event)

    def addVariable(self, name: str, config: VariableConfig):
        """Adds a new row WITHOUT triggering the 'itemChanged' signal."""
        self.setup_table.blockSignals(True)
        row = self.setup_table.rowCount()
        config.row = row
        self.setup_table.insertRow(row)

        # Col 0: ID
        id_item = QTableWidgetItem(name)
        id_item.setFlags(id_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
        id_item.setData(Qt.ItemDataRole.UserRole, config)
        self.setup_table.setItem(row, 0, id_item)

        # Col 1: Type
        type_item = QTableWidgetItem()
        type_item.setFlags(type_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
        self.setup_table.setItem(row, 1, type_item)

        # Col 2: Value
        val_item = QTableWidgetItem()
        self.setup_table.setItem(row, 2, val_item)

        self.refreshVariable(config)
        self.setup_table.blockSignals(False)

    def refreshVariable(self, config: VariableConfig):
        row = config.row
        if row is None: return

        self.setup_table.blockSignals(True)
        try:
            value_item = self.setup_table.item(row, 2)
            self._updateValueText(value_item, config)
            _updateTypeItem(self.setup_table.item(row, 1), value_item, config)

            # Update Overlay Geometry
            if GlobalCaptureRegistry.containsType(config.data_type):
                self.overlay.render_geometry.add(config)
            elif config in self.overlay.render_geometry:
                self.overlay.render_geometry.remove(config)
                self.overlay.update()
        finally:
            self.setup_table.blockSignals(False)

    def _getVarConfig(self, item: QTableWidgetItem):
        return self.setup_table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)

    def _updateValueText(self, item: QTableWidgetItem, config: VariableConfig):
        if config.data_type is bool:
            item.setText("")
            item.setData(Qt.ItemDataRole.UserRole, False)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setData(Qt.ItemDataRole.CheckStateRole,
                         Qt.CheckState.Checked if config.value else Qt.CheckState.Unchecked)
            return

        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        item.setData(Qt.ItemDataRole.CheckStateRole, None)

        is_empty = config.value is None
        item.setData(Qt.ItemDataRole.UserRole, is_empty)
        updateItemPlaceholder(self, item, None if is_empty else GlobalTypeHandler.toString(config.value))

    def _onTableChanged(self, item):
        if item.column() != 2 or (item.data(Qt.ItemDataRole.UserRole) and item.text() == EMPTY_VALUE_STR):
            return

        var_config = self._getVarConfig(item)
        if not var_config: return

        if var_config.data_type is bool:
            var_config.value = item.checkState() == Qt.CheckState.Checked
        else:
            success = True
            try:
                var_config.value = GlobalTypeHandler.fromString(var_config.data_type, item.text())
            except (ValueError, TypeError):
                success = False

            if not success:
                self.refreshVariable(var_config)
                _flashError(item)
            elif GlobalCaptureRegistry.containsType(var_config.data_type) and var_config.value:
                self.overlay.update()

    def _onItemHovered(self, item):
        config = self._getVarConfig(item)
        prev = self.overlay.highlighted_config
        self.overlay.highlighted_config = config if (
                    config and GlobalCaptureRegistry.containsType(config.data_type)) else None
        if prev != self.overlay.highlighted_config:
            self.overlay.update()

    def _openMenu(self, position):
        item = self.setup_table.itemAt(position)
        if not item: return
        config = self._getVarConfig(item)
        if not config: return

        capture_mode = GlobalCaptureRegistry.getModeFromType(config.data_type)
        if capture_mode:
            menu = QMenu()
            capture_action = menu.addAction("Capture Data")
            action = menu.exec(self.setup_table.viewport().mapToGlobal(position))

            if action == capture_action:
                self._pending_capture_item = item
                # Hide the MAIN WINDOW (the parent of this tab)
                self.window().hide()
                GlobalCaptureRegistry.get(capture_mode).capture_handler(self, config)

    def afterCaptureEnded(self, result):
        value_item = self._pending_capture_item
        self._pending_capture_item = None
        if result:
            config = self._getVarConfig(value_item)
            config.value = result
            self.refreshVariable(config)
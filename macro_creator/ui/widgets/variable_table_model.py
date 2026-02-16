from typing import TYPE_CHECKING, Union
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, QTimer
from PySide6.QtGui import QBrush, QColor

from macro_creator.core.capture_type_registry import GlobalCaptureRegistry
from macro_creator.core.type_handler import GlobalTypeHandler
from macro_creator.ui.shared import EMPTY_VALUE_STR, SELECTED_COLOR

if TYPE_CHECKING:
    from macro_creator.core.data import VariableStore, VariableConfig


# Yeah, let's consider this a widget
class VariableTableModel(QAbstractTableModel):
    def __init__(self, variable_store: "VariableStore"):
        super().__init__()
        self.store = variable_store
        self._keys_cache = list(self.store.keys())
        self._flashing_index = None

        self.columns = ["Variable ID", "Type", "Value"]

        self.store.varAdded.connect(self._refreshData)
        self.store.varRemoved.connect(self._refreshData)
        self.store.varChanged.connect(self._emitLayoutChanged)

    def _refreshData(self):
        self.layoutAboutToBeChanged.emit()
        self._keys_cache = list(self.store.keys())
        self.layoutChanged.emit()

    def _emitLayoutChanged(self):
        self.layoutChanged.emit()

    def rowCount(self, parent=QModelIndex()):
        return len(self._keys_cache)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def headerData(self, section, orientation, /, role = ...):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.columns[section]
        return None

    def data(self, index, /, role = ...):
        if not index.isValid():
            return None

         # Get the variable for this row
        var_name, config = self.getNameAndConfig(index.row())

        match role:
            case Qt.ItemDataRole.BackgroundRole:
                if self._flashing_index and index == self._flashing_index:
                    return QBrush(QColor("#FFCDD2"))
            case Qt.ItemDataRole.ForegroundRole:
                if index.column() == 1 and GlobalCaptureRegistry.containsType(config.data_type):
                    return QBrush(QColor(SELECTED_COLOR))
                elif index.column() == 2 and config.value is None:
                    return QBrush(QColor("gray"))
            case Qt.ItemDataRole.DisplayRole:
                if index.column() == 0:
                    return var_name
                elif index.column() == 1:
                    return GlobalTypeHandler.getDisplayName(config.data_type)
                elif index.column() == 2:
                    if config.data_type is bool: return ""
                    return GlobalTypeHandler.toString(config.value) or EMPTY_VALUE_STR
            case Qt.ItemDataRole.EditRole:
                if index.column() == 0:
                    return var_name
                elif index.column() == 2:
                    if config.data_type is bool: return ""
                    return GlobalTypeHandler.toString(config.value) or ""
            case Qt.ItemDataRole.CheckStateRole:
                if index.column() == 2 and config.data_type is bool:
                    return Qt.CheckState.Checked if config.value else Qt.CheckState.Unchecked
            case Qt.ItemDataRole.ToolTipRole:
                if index.column() == 2:
                    capture_mode = GlobalCaptureRegistry.getModeFromType(config.data_type)
                    if capture_mode:
                        return f"{GlobalCaptureRegistry.get(capture_mode).tip} | Right click to capture"
                    return config.hint or "Manually edit this value."

        return None

    def setData(self, index, value, /, role = ...):
        """Triggered automatically when the user finishes editing a cell."""
        valid_edit_roles = (Qt.ItemDataRole.EditRole, Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.CheckStateRole)
        if not index.isValid() or role not in valid_edit_roles:
            return False

        old_name, config = self.getNameAndConfig(index.row())

        if index.column() == 2:
            if role != Qt.ItemDataRole.CheckStateRole:
                val_str = str(value)
                config = self.store[old_name]
                if not config:
                    return False

                parsed_value = None
                if str(value).strip() != "":
                    try:
                        parsed_value = GlobalTypeHandler.fromString(config.data_type, val_str)
                    except (ValueError, TypeError):
                        self.triggerFlash(index)
                        return False
            else:
                parsed_value = value == Qt.CheckState.Checked

            self.store.updateValue(old_name, parsed_value)
            return True

        return False

    def flags(self, index, /):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        config = self.getConfigAtRow(index.row())

        # Add other columns here if needed
        if index.column() == 2:
            if config.data_type is bool:
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            else:
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def triggerFlash(self, index):
        """Called when validation fails to start the flash effect."""
        self._flashing_index = index
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.BackgroundRole])
        QTimer.singleShot(250, self._clearFlash)

    def _clearFlash(self):
        """Clears the flash and redraws the cell back to normal."""
        if self._flashing_index:
            old_index = self._flashing_index
            self._flashing_index = None
            self.dataChanged.emit(old_index, old_index, [Qt.ItemDataRole.BackgroundRole])

    def getNameAndConfig(self, row: int):
        """Returns the name and full config object for the given row."""
        if row < 0 or row >= self.rowCount():
            return None, None

        var_name = self._keys_cache[row]
        config = self.store[var_name]
        return var_name, config

    def getConfigAtRow(self, row: int) -> Union["VariableConfig", None]:
        """Returns the full config object for the given row."""
        return self.getNameAndConfig(row)[1]
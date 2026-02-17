from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QTimer, Signal, QAbstractListModel, Qt, QModelIndex
from PySide6.QtWidgets import QStackedWidget, QComboBox, QLineEdit, QWidget, QHBoxLayout, QMenu

from macro_studio.core.types_and_enums import CaptureMode
from macro_studio.core.controllers.type_handler import GlobalTypeHandler
from macro_studio.ui.shared import flashError, createIconLabel
from .action_bindings import SneakyWidget, SneakyComboEditor

if TYPE_CHECKING:
    from macro_studio.core.data import VariableStore


_CURRENT_LOL_ID = "CURRENT5t3c31lcu3fy&!5V729oe"
_CURRENT_DISP_STR = "Current Position"


class MousePosComboBoxModel(QAbstractListModel):
    def __init__(self, store: "VariableStore"):
        super().__init__()
        self.store = store
        items = [(_CURRENT_DISP_STR, _CURRENT_LOL_ID)]
        for name, config in store.items():
            if config.data_type is QPoint:
                items.append((name, name))

        self._items = items

        store.varAdded.connect(self.tryAddItem)
        store.varRemoved.connect(self.tryRemoveItem)
        store.varChanged.connect(self._onVarUpdated)

    def rowCount(self, parent=None):
        return len(self._items)

    def data(self, index, role=...):
        if not index.isValid():
            return None

        display_name, underlying_data = self._items[index.row()]

        match role:
            case Qt.ItemDataRole.DisplayRole:
                return display_name
            case Qt.ItemDataRole.UserRole:
                return underlying_data

        return None

    def tryAddItem(self, display_name, underlying_data):
        if underlying_data.data_type is not QPoint: return
        new_row_index = len(self._items)
        self.beginInsertRows(QModelIndex(), new_row_index, new_row_index)
        self._items.append((display_name, display_name))
        self.endInsertRows()

    def tryRemoveItem(self, display_name, config):
        if config.data_type is not QPoint: return
        for row, (name, _) in enumerate(self._items):
            if name == display_name:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._items.pop(row)
                self.endRemoveRows()
                return

    def _onVarUpdated(self, display_name):
        data = self.store[display_name]
        for row, (name, _) in enumerate(self._items):
            if name == display_name:
                if not data.data_type is QPoint:
                    # Item is no longer capturable, remove it
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._items.pop(row)
                    self.endRemoveRows()
                return

        # We didn't have it in our list; Try to add it
        self.tryAddItem(display_name, data)

class ComboAndLineEditor(QStackedWidget):
    def __init__(self, parent, mouse_combo_model):
        super().__init__(parent)

        # Variables at index 0
        self.variable_combo = QComboBox(self)
        self.variable_combo.setModel(mouse_combo_model)
        self.addWidget(self.variable_combo)

        # Manual Edit at index 1
        self.manual_edit = QLineEdit(self)
        self.addWidget(self.manual_edit)

    def isShowCombo(self):
        return self.currentIndex() == 0

    def setFocus(self, /):
        if self.isShowCombo():
            self.variable_combo.setFocus()
        else:
            self.manual_edit.setFocus()
            self.manual_edit.selectAll()

    def resetDefault(self):
        self.setCurrentIndex(0)
        self.variable_combo.setCurrentIndex(0)

class SneakyComboAndLineEditor(SneakyWidget):
    def __init__(self, parent, prev_value, overlay, mouse_combo_model):
        self.combo_line_edit = ComboAndLineEditor(parent, mouse_combo_model)
        self.overlay = overlay
        super().__init__(self.combo_line_edit, value=prev_value, parent=parent)

        self.combo_line_edit.variable_combo.installEventFilter(self)
        self.combo_line_edit.manual_edit.installEventFilter(self)
        self.combo_line_edit.variable_combo.activated.connect(lambda: self.finishEditing(self.combo_line_edit.variable_combo.currentData()))
        self.combo_line_edit.manual_edit.editingFinished.connect(self.validateThenFinish)
        self.setToolTip("Right click to for more options")
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._openMenu)

    def _openMenu(self, position):
        menu = QMenu()
        select_action = menu.addAction("Select Variable")
        capture_action = menu.addAction("Capture Data")

        action = menu.exec(self.mapToGlobal(position))

        if action == select_action:
            self.combo_line_edit.setCurrentIndex(0)
            self.startCapture(True)
        elif action == capture_action:
            result = self.overlay.captureData(CaptureMode.POINT)
            if result:
                self.combo_line_edit.setCurrentIndex(1)
                self.finishEditing(result)

    def enterEvent(self, event, /):
        if self.value and self.value != _CURRENT_LOL_ID:
            self.overlay.trySetHighlighted(self.value)
        super().enterEvent(event)

    def leaveEvent(self, event, /):
        # Remove from overlay
        self.overlay.removeHighlightedData()
        super().leaveEvent(event)

    def validateThenFinish(self):
        text = self.combo_line_edit.manual_edit.text()
        if not text:
            self.finishEditing(_CURRENT_LOL_ID)
            return

        try:
            coords = GlobalTypeHandler.fromString(QPoint, text)
            self.finishEditing(coords)
        except (ValueError, TypeError):
            flashError(self.combo_line_edit.manual_edit)

    def startCapture(self, use_current=False):
        if self.value is None or isinstance(self.value, str) or use_current:
            self.combo_line_edit.setCurrentIndex(0)
        else:
            self.combo_line_edit.manual_edit.setText(GlobalTypeHandler.toString(self.value) or "")
            self.combo_line_edit.setCurrentIndex(1)
        super().startCapture()
        if self.combo_line_edit.isShowCombo():
            self.can_finish = False
            self.combo_line_edit.variable_combo.showPopup()
            QTimer.singleShot(200, self._setCanFinishTrue)

    def setValue(self, new_value):
        if new_value is None or new_value == _CURRENT_LOL_ID:
            self.combo_line_edit.resetDefault()
            new_value = _CURRENT_LOL_ID

        super().setValue(new_value)

    def getDisplayStr(self):
        if self.value is None or isinstance(self.value, str):
            return self.value if self.value != _CURRENT_LOL_ID else _CURRENT_DISP_STR

        val_str = GlobalTypeHandler.toString(self.value)

        return val_str or "Define Coordinates"

class DualMouseEditor(QWidget):
    valueChanged = Signal(object)

    def __init__(self, parent, prev_data, overlay, mouse_combo_model):
        super().__init__(parent=parent)
        dual_layout = QHBoxLayout(self)
        dual_layout.setContentsMargins(0, 0, 0, 0)
        dual_layout.setSpacing(5)

        prev_data = prev_data or (None, None)
        self.value = prev_data

        self.mouse_fun_sneaky = SneakyComboEditor(self, prev_data[0])
        dual_layout.addWidget(self.mouse_fun_sneaky)

        dual_layout.addWidget(createIconLabel("ph.crosshair-simple"))

        other_data = prev_data[1]
        if other_data and isinstance(other_data, str): # Try to convert it back to QP
            try:
                other_data = GlobalTypeHandler.fromString(QPoint, other_data)
            except (ValueError, TypeError):
                other_data = other_data

        self.other_sneaky = SneakyComboAndLineEditor(self, other_data, overlay, mouse_combo_model)
        dual_layout.addWidget(self.other_sneaky)

        self.mouse_fun_sneaky.valueChanged.connect(lambda new_val: self.captureNewValues(new_val, self.other_sneaky.value))
        self.other_sneaky.valueChanged.connect(lambda new_val: self.captureNewValues(self.mouse_fun_sneaky.value, new_val))

    def captureNewValues(self, val1, val2):
        new_val = (val1, val2)
        self.valueChanged.emit(new_val)
        self.value = new_val

    def setValue(self, new_value):
        if new_value is None: new_value = (None, None)
        self.mouse_fun_sneaky.setValue(new_value[0])
        self.other_sneaky.setValue(new_value[1])
        self.value = new_value
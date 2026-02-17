from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout,
    QHeaderView, QMenu, QStyledItemDelegate, QTableView, QLineEdit
)
from PySide6.QtCore import Qt, QEvent, QTimer

from macro_creator.core.controllers.capture_type_registry import GlobalCaptureRegistry
from macro_creator.ui.widgets.variable_table_model import VariableTableModel

if TYPE_CHECKING:
    from macro_creator.core.data import VariableStore


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
        super().setEditorData(editor, index)

        if isinstance(editor, QLineEdit):
            QTimer.singleShot(0, editor.selectAll)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QLineEdit):
            model.setData(index, editor.text().strip(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)

class VariablesTab(QWidget):
    def __init__(self, var_store: "VariableStore", overlay_ref):
        super().__init__()
        self.overlay = overlay_ref

        layout = QVBoxLayout(self)

        self.table_view = QTableView()
        self.model = VariableTableModel(var_store)
        self.table_view.setModel(self.model)

        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setItemDelegateForColumn(2, SmartDelegate(self.table_view))

        for var_name in var_store:
            self._onVarChanged(var_name)

        # Context Menu & Events
        self.table_view.setMouseTracking(True)
        self.table_view.entered.connect(self._onItemHovered)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._openMenu)
        var_store.varChanged.connect(self._onVarChanged)
        var_store.varAdded.connect(self._onVarChanged)
        var_store.varRemoved.connect(self._onVarRemoved)

        layout.addWidget(self.table_view)

    def leaveEvent(self, event):
        self.overlay.removeHighlightedData()
        super().leaveEvent(event)

    def _onVarRemoved(self, _, config):
        if config in self.overlay.render_geometry:
            self.overlay.render_geometry.remove(config)
            self.overlay.update()

    def _onVarChanged(self, var_name):
        config = self.model.store[var_name]
        if GlobalCaptureRegistry.containsType(config.data_type):
            self.overlay.render_geometry.add(config)
            self.overlay.update()
        else:
            self._onVarRemoved(None, config)

    def _onItemHovered(self, index):
        if not index.isValid(): return
        self.overlay.trySetHighlighted(self.model.getNameAndConfig(index.row())[0])

    def _openMenu(self, position):
        index = self.table_view.indexAt(position)

        if not index.isValid():
            return

        var_name, config = self.model.getNameAndConfig(index.row())
        if not config:
            return

        capture_mode = GlobalCaptureRegistry.getModeFromType(config.data_type)

        if capture_mode:
            menu = QMenu()
            capture_action = menu.addAction("Capture Data")

            action = menu.exec(self.table_view.viewport().mapToGlobal(position))

            if action == capture_action:
                result = GlobalCaptureRegistry.get(capture_mode).capture_method(self.overlay, config)
                try:
                    self.model.store.updateValue(var_name, result)
                except KeyError:
                    print(f"Somehow the key isn't in the store? {var_name}")
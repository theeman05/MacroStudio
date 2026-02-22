from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QHeaderView, QMenu, QStyledItemDelegate, QTableView, QLineEdit, QHBoxLayout, QGridLayout, QDialog
)
from PySide6.QtCore import Qt, QEvent, QTimer

from macro_studio.core.controllers.capture_type_registry import GlobalCaptureRegistry
from macro_studio.ui.shared import HoverButton
from macro_studio.ui.widgets.var_tab.variable_table_model import VariableTableModel
from macro_studio.ui.widgets.var_tab.create_variable_dialog import VarCreateOverlay
from macro_studio.ui.widgets.var_tab.delete_confirmation_overlay import DeleteConfirmationOverlay


if TYPE_CHECKING:
    from macro_studio.core.data import VariableStore


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
        self.var_store = var_store

        layout = QGridLayout(self)

        special_bar_layout = QHBoxLayout()
        special_bar_layout.setContentsMargins(5,5,5,5)
        special_bar_layout.setSpacing(5)

        add_var_btn = HoverButton("ph.plus-circle-fill", tooltip="Create New Variable", size=35)
        del_var_btn = HoverButton("ph.trash-fill", hover_color="#f44336", tooltip="Delete Selected Variables", size=35)

        special_bar_layout.addWidget(add_var_btn)
        special_bar_layout.addWidget(del_var_btn)

        self.table_view = QTableView()
        self.model = VariableTableModel(var_store)
        self.table_view.setModel(self.model)
        self.create_overlay = VarCreateOverlay(var_store)
        self.delete_overlay = DeleteConfirmationOverlay()

        self.table_view.setAlternatingRowColors(True)
        self.table_view.setShowGrid(False)
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
        add_var_btn.clicked.connect(self.showVariableCreator)
        del_var_btn.clicked.connect(self.showDeleteConfirmation)
        self.delete_overlay.deleteConfirmed.connect(self.deleteSelectedVars)

        layout.addWidget(self.table_view, 0, 0)
        layout.addLayout(special_bar_layout, 0, 0, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.create_overlay, 0, 0)
        layout.addWidget(self.delete_overlay, 0, 0)

    def leaveEvent(self, event):
        self.overlay.removeHighlightedData()
        super().leaveEvent(event)

    def showVariableCreator(self):
        self.create_overlay.show()

    def showDeleteConfirmation(self):
        selected_ct = len(set(index.row() for index in self.table_view.selectedIndexes()))
        if selected_ct == 0: return
        self.delete_overlay.showOverlay(selected_ct)

    def deleteSelectedVars(self):
        rows = sorted({index.row() for index in self.table_view.selectedIndexes()}, reverse=True)
        for row in rows:
            self.var_store.remove(self.model.getNameAndConfig(row)[0])

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
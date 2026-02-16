from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,QListWidgetItem)
from PySide6.QtCore import QSize

from macro_creator.core.data.timeline_handler import (
    TimelineModel, TimelineData, AddStepCommand, MoveStepsCommand, ChangeStepCommand, RemoveStepCommand)
from macro_creator.ui.widgets.recorder import (
    ActionType, PaletteItemWidget, DraggableListWidget, RecorderToolbar, TimelineItemWidget, DroppableTimelineWidget,
    TaskHeaderWidget, MousePosComboBoxModel)

if TYPE_CHECKING:
    from macro_creator.core.data.profile import Profile

NUM_MATCH_REGEX = r"([\d\.]+)"

def getStepDuration(timeline_data: TimelineData):
    if timeline_data.action_type != ActionType.DELAY: return None
    return timeline_data.value or 0


class RecorderTab(QWidget):
    MIN_SIZE = (900, 800)
    def __init__(self, overlay, profile: "Profile"):
        super().__init__()

        self.overlay = overlay
        self.tasks = profile.tasks
        self.timeline_model = TimelineModel()
        self.mouse_combo_model = MousePosComboBoxModel(profile.vars)
        self.undo_stack = QUndoStack(self)
        self.header_widget = TaskHeaderWidget(profile.tasks)

        layout_widget = QWidget()
        self.layout = QHBoxLayout(layout_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.total_duration = 0
        self.index_on_save = 0
        self.palette_drag_action = None

        self._setupPalette()

        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)  # Remove margin for full-width toolbar
        self.content_layout.setSpacing(0)

        self.toolbar = RecorderToolbar()

        self.content_layout.addWidget(self.toolbar)

        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(20, 0, 20, 20)

        self.timeline_list = DroppableTimelineWidget(self)
        list_layout.addWidget(self.timeline_list)

        self.content_layout.addWidget(list_container)

        v_layout = QVBoxLayout(self)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)

        # Finish Setup
        v_layout.addWidget(self.header_widget)
        v_layout.addWidget(layout_widget)
        self.layout.addWidget(self.sidebar)
        self.layout.addWidget(self.content_area)

        # Connect signals
        # self.toolbar.record_clicked.connect(self.on_toggle_record)
        self.toolbar.chk_select_all.toggled.connect(self.toggleSelectAll)
        self.toolbar.btn_save.clicked.connect(self.saveActiveTask)
        self.tasks.activeStepSet.connect(self.displayActiveTask)
        self.timeline_list.itemSelectionChanged.connect(self.onTimelineSelectionChanged)
        self.toolbar.btn_trash_selected.pressed.connect(self.userDeleteSelectedItems)
        self.toolbar.btn_undo.pressed.connect(self.undo_stack.undo)
        self.toolbar.btn_redo.pressed.connect(self.undo_stack.redo)
        self.undo_stack.indexChanged.connect(self._updateLabels)
        self.timeline_model.stepAdded.connect(self.onStepAdded)
        self.timeline_model.stepValueChanged.connect(self.onStepChanged)
        self.timeline_model.stepRemoved.connect(self.onStepRemoved)
        self.timeline_model.stepMoved.connect(self.onStepMoved)
        self.header_widget.saveRequested.connect(self.saveActiveTask)

        self.displayActiveTask()

    def _updateLabels(self):
        self.toolbar.btn_undo.setEnabled(self.undo_stack.canUndo())
        self.toolbar.btn_redo.setEnabled(self.undo_stack.canRedo())
        self.toolbar.btn_undo.setToolTip(f"Undo {self.undo_stack.undoText()}")
        self.toolbar.btn_redo.setToolTip(f"Redo {self.undo_stack.redoText()}")
        has_changes = self.undo_stack.index() != self.index_on_save
        self.toolbar.btn_save.setEnabled(has_changes)
        self.header_widget.setModified(has_changes)

    def displayActiveTask(self):
        active_task = self.tasks.getActiveTask()
        self.undo_stack.clear()
        self.timeline_list.clear()
        self.total_duration = 0
        self.index_on_save = 0
        self.addToTimer(0)
        self._updateLabels()
        self.timeline_model.importTimeline(active_task.steps if active_task else [])

    def saveActiveTask(self):
        change_idx = self.undo_stack.index()
        if self.undo_stack.isClean() or change_idx == self.index_on_save: return
        serial_steps = []
        for i in range(self.timeline_model.count()):
            item = self.timeline_list.item(i)
            if not item:
                print("ERROR WHILE SAVING")
                return
            widget = self.timeline_list.itemWidget(item)
            self._tryUpdatePartnerData(widget)
            serial_steps.append(widget.timeline_data.toDict())

        self.index_on_save = change_idx
        self.tasks.saveStepsToActive(serial_steps)
        self._updateLabels()

    def getItemRow(self, item):
        return self.timeline_list.row(item)

    def _tryUpdatePartnerData(self, widget):
        # Attempts to update the partner index data for the widget. Should be called before commands.
        if widget.partner_item:
            widget.timeline_data.partner_idx = self.getItemRow(widget.partner_item)

    # --- User Actions (Create Commands) ---
    def userAddsStep(self, insert_at, data: TimelineData, try_insert_pair=1, dupe_lol=False):
        if insert_at is None: insert_at = self.timeline_model.count()
        self.undo_stack.beginMacro(f"{"Add" if not dupe_lol else "Duplicate"} {data.action_type.value.title()}")
        try:
            self.undo_stack.push(AddStepCommand(self.timeline_model, insert_at, data))

            if try_insert_pair and data.detail:
                # Might need to add before pushing? Depends on if clone data or not when command created
                data.partner_idx = insert_at + 1
                # Push the partner to the stack
                self.undo_stack.push(AddStepCommand(self.timeline_model, data.partner_idx, TimelineData(
                    action_type=data.action_type,
                    value=data.value,
                    detail=data.detail+1,
                    partner_idx=insert_at
                )))
        finally:
            self.undo_stack.endMacro()

    def userDuplicatesStep(self, widget, detail, source_item):
        start_idx = self.getItemRow(source_item) + 1
        insert_pair = 0

        # Always do upper first
        if widget.partner_item: detail = insert_pair = 1

        self.userAddsStep(start_idx, TimelineData(
            action_type=widget.action_type,
            value=widget.action_widget.value,
            detail=detail
        ), try_insert_pair=insert_pair, dupe_lol=True)

    def userDeletesStep(self, item):
        index = self.getItemRow(item)
        widget = self.timeline_list.itemWidget(item)
        self._tryUpdatePartnerData(widget)
        cmd = RemoveStepCommand(model=self.timeline_model,index=index)
        self.undo_stack.push(cmd)

    def userDeleteSelectedItems(self):
        selected_items = self.timeline_list.selectedItems()
        if not selected_items: return
        # Delete from the bottom up because row shift
        rows = [self.getItemRow(item) for item in selected_items]
        rows.sort(reverse=True)

        self.undo_stack.beginMacro(f"Delete {len(selected_items)} Step{'s' if len(selected_items) > 1 else ''}")
        try:
            for item in selected_items:
                self.userDeletesStep(item)
        finally:
            self.undo_stack.endMacro()

    def userChangesStep(self, item, new_value):
        index = self.getItemRow(item)
        self.undo_stack.push(ChangeStepCommand(model=self.timeline_model,index=index,new_value=new_value))

    def userMovesStep(self, new_index):
        selection = self.timeline_list.selectedItems()
        if not selection: return

        selected_indices = []
        adjusted_target = new_index

        for item in selection:
            self._tryUpdatePartnerData(self.timeline_list.itemWidget(item))
            row = self.getItemRow(item)
            selected_indices.append(row)
            if row < new_index:
                adjusted_target -= 1

        sorted_indices = sorted(selected_indices)

        # Simulate the final resting positions of the items
        simulated_new_positions = list(range(adjusted_target, adjusted_target + len(sorted_indices)))

        # If the original indices perfectly match the simulated block, nothing changed!
        if sorted_indices == simulated_new_positions:
            return

        self.undo_stack.push(MoveStepsCommand(
            model=self.timeline_model,
            sorted_indices=sorted_indices,
            adjusted_target=adjusted_target
        ))

    # --- View Updates (React to Signals) ---
    def onStepAdded(self, index, data: TimelineData):
        item = QListWidgetItem()
        item.setSizeHint(QSize(100, 48))

        if index is None:
            self.timeline_list.addItem(item)
        else:
            self.timeline_list.insertItem(index, item)

        # Create the custom widget and link to item
        widget = TimelineItemWidget(self.overlay, self.mouse_combo_model, data)
        self.timeline_list.setItemWidget(item, widget)

        if duration := getStepDuration(data): self.addToTimer(duration)

        self.timeline_list.tryLinkWithIdx(item, widget, data.partner_idx)

        # Connect Signals
        widget.btn_del.pressed.connect(lambda: self.userDeletesStep(item))
        widget.btn_dup.pressed.connect(lambda: self.userDuplicatesStep(widget, data.detail, item))
        widget.action_widget.valueChanged.connect(lambda new_value: self.userChangesStep(item, new_value))

    def onStepMoved(self, old_index, new_index):
        item = self.timeline_list.item(old_index)
        old_widget = self.timeline_list.itemWidget(item)
        widget_data = old_widget.timeline_data
        if duration := getStepDuration(widget_data): self.total_duration -= duration

        taken_item = self.timeline_list.takeItem(old_index)
        if taken_item: del taken_item

        self.onStepAdded(new_index, widget_data)

    def onStepChanged(self, index, new_value):
        item = self.timeline_list.item(index)
        if item:
            widget = self.timeline_list.itemWidget(item)
            timeline_data = widget.timeline_data
            if timeline_data.value != new_value:
                old_duration = getStepDuration(timeline_data)
                widget.action_widget.setValue(new_value)

                partner_item = widget.partner_item
                if widget.partner_item:
                    partner_widget = self.timeline_list.itemWidget(partner_item)
                    partner_widget.timeline_data.value = new_value
                    partner_widget.action_widget.setValue(new_value)

                if old_duration is not None:
                    self.addToTimer((new_value or 0) - old_duration)
            else:
                self.timeline_list.tryLinkWithIdx(item, widget, timeline_data.partner_idx)

    def onStepRemoved(self, index):
        item = self.timeline_list.item(index)
        widget = self.timeline_list.itemWidget(item)
        self.timeline_list.tryUnlinkPartners(widget)
        if duration:= getStepDuration(widget.timeline_data): self.addToTimer(-duration)

        take_item = self.timeline_list.takeItem(index)
        if take_item: del take_item

        self.timeline_list.tryUpdateHoveredWidget()

    # --- Other Stuff ---
    def _setupPalette(self):
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(285)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(15, 20, 15, 20)

        self.palette_list = DraggableListWidget(self)
        for action_type in ActionType:
            item = QListWidgetItem(self.palette_list)
            item.setSizeHint(QSize(200, 50))

            widget = PaletteItemWidget(action_type)
            self.palette_list.setItemWidget(item, widget)

        lbl_add = QLabel("ADD")
        lbl_add.setObjectName("header_label")

        self.sidebar_layout.addWidget(lbl_add)
        self.sidebar_layout.addWidget(self.palette_list)

    def addToTimer(self, addition: int):
        if addition: self.total_duration += addition
        self.toolbar.updateTimer(self.total_duration)

    def toggleSelectAll(self, is_checked):
        if self.timeline_list.count() == 0 and is_checked:
            self.toolbar.chk_select_all.blockSignals(True)
            self.toolbar.chk_select_all.setChecked(False)
            self.toolbar.chk_select_all.blockSignals(False)

        if is_checked:
            self.timeline_list.selectAll()
        else:
            self.timeline_list.clearSelection()

    def onTimelineSelectionChanged(self):
        selected_items = self.timeline_list.selectedItems()

        if not selected_items:
            self.toolbar.trash_container.hide()
            self.toolbar.timer_container.show()
            self.toolbar.chk_select_all.setChecked(False)
            return

        selected_ct = len(selected_items)
        self.toolbar.lbl_select_ct.setText(f"{selected_ct} Selected")
        selected_all = selected_ct == self.timeline_list.count()

        if selected_all:
            if not self.toolbar.chk_select_all.isChecked():
                self.toolbar.chk_select_all.setChecked(True)
        elif self.toolbar.chk_select_all.isChecked():
            self.toolbar.chk_select_all.blockSignals(True)
            self.toolbar.chk_select_all.setChecked(False)
            self.toolbar.chk_select_all.blockSignals(False)

        self.toolbar.timer_container.hide()
        self.toolbar.trash_container.show()
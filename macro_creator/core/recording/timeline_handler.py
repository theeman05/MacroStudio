import bisect
from dataclasses import dataclass
from enum import Enum
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand
from pynput.mouse import Button

from macro_creator.core.controllers.type_handler import GlobalTypeHandler


class ActionType(str, Enum):
    DELAY = "DELAY"
    KEYBOARD = "KEYBOARD FUNCTION"
    MOUSE = "MOUSE FUNCTION"
    TEXT = "TEXT FUNCTION"

class MouseFunction(str, Enum):
    LEFT_CLICK = "Left Click"
    RIGHT_CLICK = "Right Click"
    SCROLL_CLICK = "Scroll Click"
    SCROLL_UP = "Scroll Up"
    SCROLL_DOWN = "Scroll Down"
    SCROLL_LEFT = "Scroll Left"
    SCROLL_RIGHT = "Scroll Right"
    MOUSE_4 = "Mouse Button 4"
    MOUSE_5 = "Mouse Button 5"

MOUSE_ACTION_MAP = {
    MouseFunction.LEFT_CLICK: Button.left,
    MouseFunction.RIGHT_CLICK: Button.right,
    MouseFunction.SCROLL_CLICK: Button.middle,
    MouseFunction.MOUSE_4: Button.x1, # Often the "Back" thumb button
    MouseFunction.MOUSE_5: Button.x2, # Often the "Forward" thumb button
}

BUTTON_TO_FUNCTION_MAP = {v: k for k, v in MOUSE_ACTION_MAP.items()}

@dataclass
class TimelineData:
    action_type: ActionType
    value: object=None
    detail: int=None # 1 means press, 2 means release
    partner_idx: int | None=None

    def toDict(self):
        master = {"action_type": self.action_type.name}
        GlobalTypeHandler.setIfEvals("value", self._getSerialValue(), master)
        GlobalTypeHandler.setIfEvals("detail", self.detail, master)
        GlobalTypeHandler.setIfEvals("partner_idx", self.partner_idx, master, strict_eval=True)

        return master

    def _getSerialValue(self):
        # Yeah, this isn't a great way to do it, but oh well.
        if self.value and isinstance(self.value, tuple):
            return self.value[0], GlobalTypeHandler.toString(self.value[1])
        return self.value

class TimelineModel(QObject):
    stepAdded = Signal(int, object) # (index, value)
    stepMoved = Signal(int, int) # (old_index, new_index)
    stepRemoved = Signal(int) # (index)
    stepValueChanged = Signal(int, object) # (index, new_value)

    def __init__(self):
        super().__init__()
        self._steps: list[TimelineData] = []

    def insertStep(self, index: int, data):
        """Inserts value and notifies listeners."""
        self._steps.insert(index, data)
        self.stepAdded.emit(index, data)

    def removeStep(self, index: int):
        """Removes value and notifies listeners."""
        self._steps.pop(index)
        self.stepRemoved.emit(index)

    def moveStep(self, old_index: int, new_index: int):
        """Moves value and notifies listeners."""
        self._steps.insert(new_index, self._steps.pop(old_index))
        self.stepMoved.emit(old_index, new_index)

    def moveSteps(self, selected_indices: list[int], target_index: int):
        """Batch moves multiple steps and properly triggers UI updates."""
        if not selected_indices:
            return

        selected_indices = sorted(selected_indices)

        items_to_move = [self._steps[i] for i in selected_indices]

        adjusted_target = target_index
        for row in selected_indices:
            if row < target_index:
                adjusted_target -= 1


        for row in sorted(selected_indices, reverse=True):
            self.removeStep(row)

        for i, item in enumerate(items_to_move):
            self.insertStep(adjusted_target + i, item)

    def updateStep(self, index: int, new_value):
        """Notifies listeners then updates value at index."""
        self.stepValueChanged.emit(index, new_value)
        self._steps[index].value = new_value

    def importTimeline(self, steps):
        """Deserializes the steps so changes may be made."""
        new_steps = []
        self._steps = new_steps
        for i, step_data in enumerate(steps):
            step = TimelineData(**step_data)
            step.action_type = ActionType[step_data['action_type']]
            new_steps.append(step)
            self.stepAdded.emit(i, step)

    def getStep(self, index: int):
        return self._steps[index]

    def count(self):
        return len(self._steps)

# -----------------------------------------------------------------------------
# THE COMMANDS (Undo/Redo Logic)
# -----------------------------------------------------------------------------
class AddStepCommand(QUndoCommand):
    def __init__(self, model: TimelineModel, index, data: TimelineData):
        super().__init__(f"Add {data.action_type.value.title()}")
        self.model = model
        self.index = index
        self.data = data

    def redo(self):
        self.model.insertStep(self.index, self.data)

    def undo(self):
        self.model.removeStep(self.index)

class _MoveData:
    def __init__(self, offset, item):
        self.item = item
        self.og_p_idx = item.partner_idx
        if self.og_p_idx:
            self.offset = offset
            self.new_p_idx = None

    def undoPartner(self):
        self.item.partner_idx = self.og_p_idx

    def redoPartner(self):
        if self.og_p_idx is not None:
            self.item.partner_idx = self.new_p_idx

class MoveStepsCommand(QUndoCommand):
    def __init__(self, model, sorted_indices: list[int], adjusted_target: int):
        len_steps = len(sorted_indices)
        description = f"Move {len_steps} Step{"s" if len_steps > 1 else ""}"
        super().__init__(description)
        self.model = model

        self.sorted_indices = sorted_indices

        self.move_dict: dict[int, _MoveData] = {}
        self.adjusted_target = adjusted_target

        for i, row in enumerate(sorted_indices):
            self.move_dict[row] = _MoveData(offset=i,item=self.model.getStep(row))

        for row in sorted_indices:
            data = self.move_dict[row]
            og_p_idx = data.og_p_idx

            if og_p_idx is not None:
                if og_p_idx in self.move_dict:
                    # Scenario A: The partner was ALSO selected and moved.
                    # Let the higher partner handle. Yes, the lower one won't have a partner_idx, but it doesn't matter.
                    new_partner_idx = (adjusted_target + self.move_dict[og_p_idx].offset) if og_p_idx < row else None
                else:
                    # Scenario B: The partner stayed behind.
                    # Use Binary Search to find how many extracted items were above it
                    extracted_above = bisect.bisect_left(sorted_indices, og_p_idx)
                    new_partner_idx = og_p_idx - extracted_above

                    # Calculate if it shifted DOWN when the items were inserted at the new target
                    if adjusted_target <= new_partner_idx:
                        new_partner_idx += len_steps

                    new_partner_idx = new_partner_idx
                data.new_p_idx = new_partner_idx

    def redo(self):
        for row in reversed(self.sorted_indices):
            self.model.removeStep(row)

        # We need to sever the link first and re-insert because the partner may not exist at the right spot yet

        for i, row in enumerate(self.sorted_indices):
            data = self.move_dict[row]

            # Temporarily sever the link
            if data.og_p_idx is not None: data.item.partner_idx = None

            insert_spot = self.adjusted_target + i
            self.model.insertStep(insert_spot, data.item)

        for i, row in enumerate(self.sorted_indices):
            data = self.move_dict[row]

            if data.og_p_idx is not None:
                insert_spot = self.adjusted_target + i
                data.redoPartner()
                self.model.updateStep(insert_spot, data.item.value)

    def undo(self):
        last_inserted_index = self.adjusted_target + len(self.sorted_indices) - 1

        for i in range(last_inserted_index, self.adjusted_target - 1, -1):
            self.model.removeStep(i)

        for row in self.sorted_indices:
            data = self.move_dict[row]

            if data.og_p_idx is not None: data.item.partner_idx = None

            self.model.insertStep(row, data.item)

        for row in self.sorted_indices:
            data = self.move_dict[row]

            if data.og_p_idx is not None:
                data.undoPartner()
                self.model.updateStep(row, data.item.value)

class ChangeStepCommand(QUndoCommand):
    def __init__(self, model: TimelineModel, index, new_value):
        super().__init__("Change")
        self.model = model
        self.index = index

        step = model.getStep(index)

        self.old_value = step.value
        self.new_value = new_value

    def redo(self):
        self.model.updateStep(self.index, self.new_value)

    def undo(self):
        self.model.updateStep(self.index, self.old_value)

class RemoveStepCommand(QUndoCommand):
    def __init__(self, model: TimelineModel, index):
        data = model.getStep(index)
        super().__init__(f"Remove {data.action_type.value.title()}")
        self.model = model
        self.index = index
        self.data = data
        self.prev_partner = data.partner_idx

    def redo(self):
        self.data.partner_idx = None
        self.model.removeStep(self.index)

    def undo(self):
        self.data.partner_idx = self.prev_partner
        self.model.insertStep(self.index, self.data)
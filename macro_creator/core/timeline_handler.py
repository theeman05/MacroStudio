from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand

class ActionType(str, Enum):
    DELAY = "DELAY"
    KEYBOARD = "KEYBOARD FUNCTION"
    MOUSE = "MOUSE FUNCTION"
    TEXT = "TEXT FUNCTION"

@dataclass
class TimelineData:
    action_type: ActionType
    value: object=None
    detail: int=None # 1 means press, 2 means release
    partner_idx: int | None=None


class TimelineModel(QObject):
    stepAdded = Signal(int, object) # (index, value)
    stepMoved = Signal(int, int) # (old_index, new_index)
    stepRemoved = Signal(int) # (index)
    stepChanged = Signal(int, object) # (index, new_value)

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

    def updateStep(self, index: int, new_value):
        """Notifies listeners then updates value at index."""
        self.stepChanged.emit(index, new_value)
        self._steps[index].value = new_value

    def importTimeline(self, steps):
        """Loads and copies the steps so changes may be made."""
        new_steps = []
        self._steps = new_steps
        for i, step in enumerate(steps):
            new_step = step.copy()
            new_steps.append(new_step)
            self.stepAdded.emit(i, new_step)

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


class MoveStepCommand(QUndoCommand):
    def __init__(self, model: TimelineModel, old_index, new_index):
        super().__init__("Move Step")
        self.model = model

        self.old_index = old_index
        self.new_index = new_index

    def redo(self):
        self.model.moveStep(self.old_index, self.new_index)

    def undo(self):
        self.model.moveStep(self.new_index, self.old_index)


class ChangeStepCommand(QUndoCommand):
    def __init__(self, model: TimelineModel, index, new_value):
        super().__init__(f"Change to '{new_value}'")
        self.model = model
        self.index = index

        step = model.getStep(index)

        # Maybe copy?
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
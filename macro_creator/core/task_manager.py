from dataclasses import dataclass, field
from PySide6.QtCore import Signal, QObject


@dataclass
class TaskModel:
    name: str
    steps: list = field(default_factory=list)
    auto_loop: bool=False

    def toDict(self):
        return {
            "name": self.name,
            "steps": self.steps,
            "auto_loop": self.auto_loop
        }


# --- Usage in your App ---

class TaskManager(QObject):
    activeStepSet = Signal()

    def __init__(self, /):
        super().__init__()
        self.tasks: list[TaskModel] = []
        self._active_idx = -1

    def createTask(self, name, set_as_active=False):
        """Creates a new task and adds it to the end of the list. Assumes the name is unique."""
        new_task = TaskModel(name=name)
        self.tasks.append(new_task)  # Adds to end (Newest)
        idx = len(self.tasks) - 1
        if set_as_active:
            self.setActiveTask(idx)

        return new_task

    def popTask(self, task_idx: int=None):
        if task_idx is None:
            task_idx = self._active_idx

        self.tasks.pop(task_idx)
        task_len = len(self.tasks)
        if self._active_idx >= task_len:
            self.setActiveTask(task_len - 1)

    def removeTask(self, task_name: str):
        task_idx = self.getTaskIdx(task_name)
        if task_idx != -1:
            self.popTask(task_idx)

        return task_idx

    def setActiveTask(self, task_idx: int):
        if task_idx >= len(self.tasks) or (task_idx < 0 and self.tasks):
            raise IndexError()

        if task_idx != self._active_idx:
            self._active_idx = task_idx
            self.activeStepSet.emit()

    def getActiveTask(self):
        return self.tasks[self._active_idx] if self.tasks else None

    def getTaskIdx(self, task_name: str):
        for i, task in enumerate(self.tasks):
            if task.name == task_name:
                return i
        return -1
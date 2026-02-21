import re
from dataclasses import dataclass
from PySide6.QtCore import Signal

from .base_store import BaseStore
from macro_studio.core.controllers.type_handler import GlobalTypeHandler
from macro_studio.core.utils import FileIO, global_logger


@dataclass
class TaskModel:
    name: str
    steps: list=None
    repeat: bool=False
    disabled: bool=False

    def __post_init__(self):
        if self.steps is None: self.steps = []

    def toDict(self):
        serial = {"name": self.name}
        GlobalTypeHandler.setIfEvals("repeat", self.repeat, serial)
        GlobalTypeHandler.setIfEvals("steps", self.steps, serial)
        GlobalTypeHandler.setIfEvals("disabled", self.disabled, serial)
        return serial

class TaskStore(BaseStore):
    activeStepSet = Signal()
    taskAdded = Signal(TaskModel)
    taskRemoved = Signal(str) # (task name)
    taskSaved = Signal(TaskModel)

    def __init__(self):
        super().__init__("tasks")
        self.tasks: list[TaskModel] = []
        self._active_idx = -1

    def createTask(self, name_or_model: str | TaskModel, set_as_active=False):
        """Creates a new task and adds it to the end of the list. Assumes the name is unique."""
        new_task = TaskModel(name=name_or_model) if isinstance(name_or_model, str) else name_or_model
        self.tasks.append(new_task)
        idx = len(self.tasks) - 1
        if set_as_active:
            self.setActiveTask(idx)

        self.taskAdded.emit(new_task)

        return new_task

    def popTask(self, task_idx: int=None):
        if task_idx is None:
            task_idx = self._active_idx

        if task_idx < 0 or task_idx >= len(self.tasks):
            return None

        task = self.tasks.pop(task_idx)
        self.taskRemoved.emit(task.name)

        if not self.tasks: # Out of tasks
            self._active_idx = -1
            self.activeStepSet.emit()
        elif task_idx < self._active_idx: # Task above active deleted
            self._active_idx -= 1
        elif task_idx == self._active_idx: # Deleted currently active task
            new_idx = max(0, self._active_idx - 1)
            self._active_idx = -1
            self.setActiveTask(new_idx)

        return task

    def _silentCreateTask(self, task):
        self._active_idx = 0  # Silently set the task so we don't reload anything
        self.createTask(task)

    def saveStepsToActive(self, serialized_steps):
        task = self.getActiveTask()
        if task:
            task.steps = serialized_steps
        else:
            task = TaskModel(name="New Task", steps=serialized_steps)
            self._silentCreateTask(task)
        self.taskSaved.emit(task)

    def setActiveTask(self, task_idx: int):
        if task_idx < -1 or task_idx >= len(self.tasks):
            raise IndexError("Task index out of bounds.")

        if task_idx != self._active_idx:
            self._active_idx = task_idx
            self.activeStepSet.emit()

    def duplicate_task(self, task_name: str=None):
        set_as_active = task_name is None
        ref_task_idx = self.getTaskIdx(task_name) if task_name is not None else self._active_idx
        if ref_task_idx == -1: return None
        ref_task = self.tasks[ref_task_idx]
        new_name = self.generateUniqueName(task_name)
        return self.createTask(TaskModel(new_name, steps=ref_task.steps, repeat=ref_task.repeat), set_as_active=set_as_active)

    def getActiveTask(self):
        return self.tasks[self._active_idx] if self.tasks else None

    def getActiveTaskIdx(self):
        return self._active_idx

    def getTaskIdx(self, task_name: str):
        for i, task in enumerate(self.tasks):
            if task.name == task_name:
                return i
        return -1

    def validateRename(self, new_name, current_name):
        """
        Validates a name change.
        Returns: (is_valid, result_string_or_error_message)
        """
        clean_name = new_name.strip()

        if not clean_name:
            return False, "Task name cannot be empty"

        if clean_name == current_name:
            return True, clean_name

        if self.getTaskIdx(clean_name) != -1:
            return False, f"Task '{clean_name}' already exists"

        return True, clean_name

    def generateUniqueName(self, base_name):
        """
        Generates a unique name based off base_name.
        If base is present, returns a name like base_name (1), base_name (2), etc.
        """
        existing_names = {task.name for task in self.tasks}

        # Smart Strip: Check if base_name already ends in "(digits)"
        match_existing = re.match(r"^(.*?)\s\(\d+\)$", base_name)

        if match_existing:
            # User passed "Task (1)", so our core name is just "Task"
            core_name = match_existing.group(1)
        else:
            # User passed "Task", so that is our core name
            core_name = base_name

        i = 1
        while base_name in existing_names:
            base_name = f"{core_name} ({i})"
            i += 1

        return base_name

    def exportActiveTask(self, filepath):
        active_task = self.getActiveTask()
        return FileIO.exportData(active_task.toDict(), filepath) if active_task else False

    def importTask(self, filepath):
        data = FileIO.importData(filepath)
        if not data: return False
        original_name = data.get("name", "Imported Task")
        safe_name = self.generateUniqueName(original_name)
        data["name"] = safe_name
        task_model = TaskModel(**data)
        self.tasks.append(task_model)

        global_logger.log(f"Imported task '{original_name}' as '{safe_name}'.")

        return True

    def serialize(self):
        serial_data = []
        for task_model in self.tasks:
            serial_data.append(task_model.toDict())

        return serial_data

    def deserialize(self, data):
        if not data: return
        for task_data in data:
            task_model = TaskModel(**task_data)
            self.tasks.append(task_model)

        if self.tasks: self.setActiveTask(0)

    def __iter__(self):
        return iter(self.tasks)

    def __len__(self):
        return len(self.tasks)
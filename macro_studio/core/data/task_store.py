import json, re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, QObject

from macro_studio.core.registries.type_handler import GlobalTypeHandler
from macro_studio.core.utils import FileIO, global_logger

if TYPE_CHECKING:
    from .database_manager import DatabaseManager


@dataclass
class TaskModel:
    name: str
    steps: list=None
    repeat: bool=False # REMOVE
    disabled: bool=False # REMOVE
    created_at: str | datetime = None
    id: int = None

    def __post_init__(self):
        if self.steps is None: self.steps = []

    def toDict(self):
        serial = {"name": self.name}
        GlobalTypeHandler.setIfEvals("steps", self.steps, serial)
        GlobalTypeHandler.setIfEvals("created_at", self.created_at, serial)
        return serial

    def dumpSteps(self) -> str | None:
        if not self.steps: return None
        return json.dumps(self.steps, default=str)

class TaskStore(QObject):
    """Tasks are globalized, available for all profiles"""
    activeStepSet = Signal()
    taskAdded = Signal(TaskModel)
    taskRemoved = Signal(str) # (task name)
    taskSaved = Signal(TaskModel)
    taskRenamed = Signal(str, str) # (old name, new name)

    def __init__(self, db: "DatabaseManager", profile_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.tasks: list[TaskModel] = []
        self._profile_id = profile_id
        self._active_idx = -1

    def createTask(self, name_or_model: str | TaskModel, set_as_active=False):
        """Creates a new task and adds it to the end of the list. Assumes the name is unique."""
        new_task = TaskModel(name=name_or_model) if isinstance(name_or_model, str) else name_or_model
        self.tasks.append(new_task)

        steps_json = new_task.dumpSteps()
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                  INSERT INTO tasks (name, steps)
                  VALUES (?, ?)
                  RETURNING id, created_at
            """, (new_task.name, steps_json))

            row = cursor.fetchone()
            new_task.created_at = row["created_at"]
            new_task.id = row["id"]

            conn.commit()

        if set_as_active:
            self.setActiveTask(len(self.tasks) - 1)

        self.taskAdded.emit(new_task)

        return new_task

    def popTask(self, task_idx: int=None):
        if task_idx is None:
            task_idx = self._active_idx

        if task_idx < 0 or task_idx >= len(self.tasks):
            return None

        task = self.tasks.pop(task_idx)
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM tasks WHERE profile_id = ? AND name = ?",
                         (self._profile_id, task.name))
            conn.commit()

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

    def updateTaskName(self, task, new_name):
        old_name = task.name
        if old_name != new_name:
            task.name = new_name
            with self.db.get_connection() as conn:
                conn.execute("UPDATE tasks SET name = ? WHERE profile_id = ? AND name = ?", (new_name, self._profile_id, old_name))
                conn.commit()
            self.taskRenamed.emit(old_name, new_name)

    def _silentCreateTask(self, task):
        self._active_idx = 0  # Silently set the task so we don't reload anything
        self.createTask(task)

    def saveStepsToActive(self, json_steps):
        task = self.getActiveTask()
        if task:
            task.steps = json_steps
        else:
            task = TaskModel(name="New Task", steps=json_steps)
            self._silentCreateTask(task)

        steps_json = task.dumpSteps()
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                UPDATE tasks SET steps = ? WHERE profile_id = ? AND name = ?
                RETURNING id, created_at
             """,(steps_json, self._profile_id, task.name))

            row = cursor.fetchone()
            task.created_at = row["created_at"]
            task.id = row["id"]

            conn.commit()

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
        self.createTask(task_model)

        global_logger.log(f"Imported task '{original_name}' as '{safe_name}'.")

        return True

    def load(self):
        self.tasks.clear()

        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM tasks WHERE profile_id = ? ORDER BY created_at", (self._profile_id,))
            for row in rows:
                j_steps = row["steps"]
                self.tasks.append(TaskModel(
                    name=row["name"],
                    steps=json.loads(j_steps) if j_steps else None,
                    created_at = row["created_at"],
                    id = row["id"]
                ))

        if self.tasks: self.setActiveTask(0)

    def __iter__(self):
        return iter(self.tasks)

    def __len__(self):
        return len(self.tasks)
import json, re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Dict

from PySide6.QtCore import Signal, QObject

from macro_studio.core.registries.type_handler import GlobalTypeHandler
from macro_studio.core.utils import FileIO, global_logger

if TYPE_CHECKING:
    from .profile import Profile


@dataclass
class TaskModel:
    name: str
    steps: list = None
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
    taskRemoved = Signal(object)  # (removed task)
    taskSaved = Signal(TaskModel)
    taskRenamed = Signal(str, str)  # (old name, new name)

    def __init__(self, profile: "Profile", parent=None):
        super().__init__(parent)
        self.profile = profile
        self.db = profile.db
        self._profile_id = profile.id
        self.tasks: Dict[int, TaskModel] = {}
        self._active_id: int | None = None

    def createTask(self, name_or_model: str | TaskModel, set_as_active=False):
        """Creates a new task, saves to DB to get ID, then adds to store."""
        new_task = TaskModel(name=name_or_model) if isinstance(name_or_model, str) else name_or_model

        steps_json = new_task.dumpSteps()

        # Insert into DB first to generate the ID
        with self.db.getConn() as conn:
            cursor = conn.execute("""
                                  INSERT INTO tasks (name, steps)
                                  VALUES (?, ?)
                                  RETURNING id, created_at
                                  """, (new_task.name, steps_json))

            row = cursor.fetchone()
            new_task.created_at = row["created_at"]
            new_task.id = row["id"]

            conn.commit()

        self.tasks[new_task.id] = new_task
        self.profile.createRelationship(new_task.id)

        if set_as_active:
            self.setActiveId(new_task.id)

        self.taskAdded.emit(new_task)

        return new_task

    def popTask(self, task_id: int = None):
        """Removes a task by ID."""
        if task_id is None:
            task_id = self._active_id

        if task_id is None or task_id not in self.tasks:
            return None

        # Remove from Dict
        task = self.tasks.pop(task_id)

        # Remove from DB
        with self.db.getConn() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ? AND name = ?",
                         (task.id, task.name))
            conn.commit()

        self.taskRemoved.emit(task)

        # Handle Active ID switching
        if not self.tasks:
            # No tasks left
            self.setActiveId(-1)
        elif task_id == self._active_id:
            # We deleted the active task, select some other task
            self.setActiveId(next(iter(self.tasks), -1))

        return task

    def updateTaskName(self, task, new_name):
        old_name = task.name
        if old_name != new_name:
            task.name = new_name
            with self.db.getConn() as conn:
                conn.execute("UPDATE tasks SET name = ? WHERE id = ? AND name = ?",
                             (new_name, task.id, old_name))
                conn.commit()
            self.taskRenamed.emit(old_name, new_name)

    def _silentCreateTask(self, task):
        new_task = self.createTask(task, set_as_active=False)
        self._active_id = new_task.id

    def saveStepsToActive(self, json_steps):
        task = self.getActiveTask()
        if task:
            task.steps = json_steps
        else:
            task = TaskModel(name="New Task", steps=json_steps)
            # This will create DB entry and set active ID
            self._silentCreateTask(task)
            # Re-fetch active because _silentCreateTask might have changed it
            task = self.getActiveTask()

        steps_json = task.dumpSteps()
        with self.db.getConn() as conn:
            cursor = conn.execute("""
                                  UPDATE tasks SET steps = ? WHERE id= ? AND name = ?
                                  RETURNING id, created_at
                                  """, (steps_json, task.id, task.name))

            # Update timestamps if needed
            row = cursor.fetchone()
            if row:
                task.created_at = row["created_at"]

            conn.commit()

        self.taskSaved.emit(task)

    def setActiveId(self, task_id: int):
        if task_id not in self.tasks:
            # Fallback or error
            if not self.tasks:
                self._active_id = None
                return
            raise KeyError(f"Task ID {task_id} not found in store.")

        if task_id != self._active_id:
            self._active_id = task_id
            self.activeStepSet.emit()

    def duplicateTask(self, task_name: str = None):
        """Duplicates a task. If task_name is None, duplicates active."""
        if task_name is None:
            target_task = self.getActiveTask()
        else:
            target_task = self.getTaskByName(task_name)

        if not target_task:
            return None

        new_name = self.generateUniqueName(target_task.name)
        new_model = TaskModel(new_name, steps=target_task.steps)

        # Determine if we should set as active (original logic: if task_name passed as None, set active)
        set_as_active = (task_name is None)
        return self.createTask(new_model, set_as_active=set_as_active)

    def getActiveTask(self):
        if self._active_id is not None and self._active_id in self.tasks:
            return self.tasks[self._active_id]
        return None

    def getTaskById(self, task_id: int):
        return self.tasks.get(task_id)

    def getActiveId(self):
        return self._active_id

    def getTaskByName(self, task_name: str):
        for task in self.tasks.values():
            if task.name == task_name:
                return task
        return None

    def validateRename(self, new_name, current_name):
        clean_name = new_name.strip()

        if not clean_name:
            return False, "Task name cannot be empty"

        if clean_name == current_name:
            return True, clean_name

        if self.getTaskByName(clean_name) is not None:
            return False, f"Task '{clean_name}' already exists"

        return True, clean_name

    def generateUniqueName(self, base_name):
        existing_names = {task.name for task in self.tasks.values()}

        match_existing = re.match(r"^(.*?)\s\(\d+\)$", base_name)
        if match_existing:
            core_name = match_existing.group(1)
        else:
            core_name = base_name

        i = 1
        test_name = base_name
        # If base_name exists, start appending numbers
        if base_name in existing_names:
            while True:
                test_name = f"{core_name} ({i})"
                if test_name not in existing_names:
                    break
                i += 1

        return test_name

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
        self._active_id = None

        with self.db.getConn() as conn:
            # We still order by created_at to maintain a logical list order
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at")
            first_id = None

            for row in rows:
                t_id = row["id"]
                if first_id is None:
                    first_id = t_id

                j_steps = row["steps"]
                self.tasks[t_id] = TaskModel(
                    name=row["name"],
                    steps=json.loads(j_steps) if j_steps else None,
                    created_at=row["created_at"],
                    id=t_id
                )

        if self.tasks and first_id is not None:
            self.setActiveId(first_id)

    def __iter__(self):
        return iter(self.tasks.values())

    def __len__(self):
        return len(self.tasks)
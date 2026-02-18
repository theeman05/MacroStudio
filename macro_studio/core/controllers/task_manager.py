from typing import TYPE_CHECKING

from macro_studio.core.execution.manual_task_wrapper import ManualTaskWrapper
from .task_controller import TaskController

if TYPE_CHECKING:
    from macro_studio.core.data import Profile, TaskModel
    from macro_studio.core.types_and_enums import TaskFunc


class ManualTaskController(TaskController):
    def __init__(self, scheduler, var_store, task_model: "TaskModel", cid: int):
        self._wrapper = ManualTaskWrapper(var_store, task_model)
        super().__init__(scheduler=scheduler,
                         task_func=self._wrapper.runTask,
                         task_id=cid,
                         unique_name=task_model.name,
                         auto_loop=task_model.auto_loop)

    def updateModel(self, task_model: "TaskModel"):
        self._wrapper.updateModel(task_model)

class TaskManager:
    def __init__(self, scheduler, profile: "Profile"):
        super().__init__()

        self.profile = profile
        self.scheduler = scheduler
        self.controllers: dict[str | int, TaskController] = {}
        self.next_cid = 0

        tasks = profile.tasks
        tasks.taskAdded.connect(self._onManualTaskAdded)
        tasks.taskRemoved.connect(self._onManualTaskRemoved)
        tasks.taskSaved.connect(self._onManualTaskSaved)
        tasks.taskLoopChanged.connect(self._onManualTaskLoopChange)

        self._onProfileLoaded()

    def createController(self, task_func: "TaskFunc", auto_loop: bool):
        c_id = self.next_cid
        controller = TaskController(self.scheduler, task_func, c_id, auto_loop=auto_loop)
        self._registerController(controller)
        return controller

    def getEnabledControllers(self):
        return [controller for controller in self.controllers.values() if controller.isEnabled()]

    def _onProfileLoaded(self):
        for cid in self.controllers:
            if isinstance(cid, str): self._onManualTaskRemoved(cid)

        for task_model in self.profile.tasks:
            self._onManualTaskAdded(task_model)

    def _registerController(self, controller: TaskController):
        self.next_cid += 1
        self.controllers[controller.getName()] = controller

    def _onManualTaskAdded(self, task_model: "TaskModel"):
        self._registerController(ManualTaskController(self.scheduler, self.profile.vars, task_model, self.next_cid))

    def _onManualTaskRemoved(self, task_name: str):
        if task_name in self.controllers:
            controller = self.controllers.pop(task_name)
            controller.stop()
            del controller

    def _onManualTaskSaved(self, task_model: "TaskModel"):
        controller = self.controllers.get(task_model.name)
        if isinstance(controller, ManualTaskController):
            controller.updateModel(task_model)
        elif controller is None:
            print(f"Warning: Tried to save '{task_model.name}', but no controller was found in the registry.")
        else:
            print(f"Warning: '{task_model.name}' is a {type(controller).__name__}, not a ManualTaskController.")

    def _onManualTaskLoopChange(self, task_name, auto_loop):
        controller = self.controllers.get(task_name)
        if isinstance(controller, ManualTaskController):
            controller.updateAutoLoop(auto_loop)
        elif controller is None:
            print(f"Warning: Tried to save '{task_name}', but no controller was found in the registry.")
        else:
            print(f"Warning: '{task_name}' is a {type(controller).__name__}, not a ManualTaskController.")
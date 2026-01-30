import inspect
from types_and_enums import TaskFunc
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from engine import MacroCreator

def _tryWrapFun(func):
    """If the function isn't a generator, wraps it into a generator function"""
    if inspect.isgeneratorfunction(func):
        yield from func()
    else:
        func()
        yield

class TaskController:
    def __init__(self, macro_creator: "MacroCreator", task_func: TaskFunc, task_id: int):
        self._creator = macro_creator
        self.id = task_id
        self.func = task_func
        self.wake_time = 0
        self._generator: Generator | None = None
        self._paused = False

    def pause(self):
        """Prevents the task from running its next step. Execution continues until task finishes."""
        self._paused = True

    def resume(self):
        """Allows the task to continue from where it left off. If the task finished already, does nothing."""
        self._paused = False

    def stop(self):
        """Stops a task, entirely, allowing execution to finish"""
        self._paused = False
        self._generator = None

    def restart(self):
        """Kills the current instance of the task and starts a fresh one."""
        self._generator = _tryWrapFun(self.func)
        self._paused = False
        self._creator.scheduleController(self, self._generator, 0)

    def isPaused(self):
        return self._paused

    def getGenerator(self):
        return self._generator

    def __lt__(self, other):
        return (self.wake_time, self.id) < (other.wake_time, other.id)
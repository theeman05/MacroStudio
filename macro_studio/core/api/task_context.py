from typing import TYPE_CHECKING, Hashable
from macro_studio.core.types_and_enums import LogLevel

if TYPE_CHECKING:
    from macro_studio.core.controllers.task_controller import TaskController

class TaskContext:
    def __init__(self, controller: "TaskController"):
        self._controller = controller

    # --- Properties ---
    @property
    def auto_loop(self):
        return self._controller.auto_loop

    @auto_loop.setter
    def auto_loop(self, value: bool):
        self._controller.auto_loop = value

    # --- Methods ---
    def getName(self):
        return self._controller.getName()

    def setEnabled(self, enabled: bool):
        self._controller.setEnabled(enabled)

    def isEnabled(self):
        return self._controller.isEnabled()

    def restart(self, wake_time: float = None):
        self._controller.restart(wake_time)

    def pause(self, interrupt: bool = False):
        return self._controller.pause(interrupt)

    def resume(self):
        return self._controller.resume()

    def stop(self):
        self._controller.stop()

    def sleep(self, duration: float = 0.01):
        self._controller.sleep(duration)

    def waitForResume(self):
        self._controller.waitForResume()

    def log(self, *args, level: LogLevel = LogLevel.INFO):
        self._controller.log(*args, level=level)

    def logError(self, error_msg: str, trace: str = ""):
        self._controller.logError(error_msg, trace)

    def getVar(self, key: Hashable):
        return self._controller.getVar(key)
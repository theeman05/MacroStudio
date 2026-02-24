from functools import wraps
from typing import TYPE_CHECKING, Hashable

from macro_studio.core.types_and_enums import LogLevel, TaskDeletedError

if TYPE_CHECKING:
    from macro_studio.core.controllers.task_controller import TaskController


def require_active_task(func):
    """Decorator: Checks if the task is still alive before running the method."""

    @wraps(func)
    def wrapper(self: "TaskContext", *args, **kwargs):
        is_valid = self.isValid()

        if not is_valid:
            raise TaskDeletedError(
                f"Handle Error: Task '{self._controller.name}' has been deleted and cannot be accessed."
            )

        return func(self, *args, **kwargs)

    return wrapper


class TaskContext:
    def __init__(self, controller: "TaskController"):
        self._controller = controller

    # --- Properties ---
    @property
    def repeat(self):
        return self._controller.repeat

    @repeat.setter
    def repeat(self, value: bool):
        self._controller.repeat = value

    @property
    def is_paused(self) -> bool:
        """Read-only property. Returns True if the task is currently paused or interrupted."""
        return self._controller.isPaused()

    @property
    def is_running(self) -> bool:
        """Read-only property. Returns True if the task is running."""
        return self._controller.isRunning()

    @property
    def is_alive(self) -> bool:
        """
        Checks if the task is currently active or armed for execution.

        Returns:
            True if the task has not reached a terminal graveyard state
            (e.g., Stopped, Finished, or Crashed). This local state remains
            True even if the master engine's global worker is currently paused
            or completely offline.
        """
        return self._controller.isAlive()

    # --- Methods ---
    def getName(self):
        return self._controller.name

    def isEnabled(self):
        return self._controller.isEnabled()

    def isValid(self) -> bool:
        """Safe method to check status without raising an error."""
        return self._controller.isValid()

    @require_active_task
    def setEnabled(self, enabled: bool):
        self._controller.setEnabled(enabled)

    @require_active_task
    def restart(self):
        """Kills the current instance of the task and starts a fresh one at the next work cycle."""
        self._controller.restart()

    @require_active_task
    def pause(self, interrupt: bool = False):
        """
        If not paused already, halts the task from running its next step.
        Args:
            interrupt: Controls how the pause is handled.

                * ``True``: Interrupts the task to **release keys** and **clean up resources** safely.
                * ``False`` (Default): **Freezes** the task in place (keys remain held down).
         Returns:
             ``True`` if paused successfully, ``False`` if the engine has stopped abruptly.
        """
        return self._controller.pause(interrupt)

    @require_active_task
    def resume(self):
        """
        If the engine is running and task was previously paused, resumes from where it left off.
        If the task finished already, does nothing.
        Returns:
            The duration paused for in seconds or ``None`` if not paused.
        """
        return self._controller.resume()

    @require_active_task
    def stop(self):
        """Attempts to stop a task on its next cycle."""
        self._controller.stop()

    def log(self, *args, level: LogLevel = LogLevel.INFO):
        """
        Sends a structured log packet to the ui.
        Args:
            args: The objects to be printed in the log. If mode is not ERROR, will cast the args automatically.
            level: The log level to display at.
        """
        self._controller.log(*args, level=level)

    def logError(self, error_msg: str, trace: str = ""):
        """Sends a specialized LogErrorPacket object to the ui."""
        self._controller.logError(error_msg, trace)

    def getVar(self, key: Hashable):
        """
        Get the value for a setup variable.
        Args:
            key: The key that the variable should be stored under.
        Returns:
            The value for a setup variable if present or None.
        """
        return self._controller.getVar(key)
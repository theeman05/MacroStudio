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
        Returns True as long as the task hasn't been explicitly killed,
        regardless of what the master worker is doing.
        """
        return self._controller.isAlive()

    # --- Methods ---
    def getName(self):
        return self._controller.getName()

    def setEnabled(self, enabled: bool):
        self._controller.setEnabled(enabled)

    def isEnabled(self):
        return self._controller.isEnabled()

    def restart(self):
        """Kills the current instance of the task and starts a fresh one at the next work cycle."""
        self._controller.restart()

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

    def resume(self):
        """
        If the engine is running and task was previously paused, resumes from where it left off.
        If the task finished already, does nothing.
        Returns:
            The duration paused for in seconds or ``None`` if not paused.
        """
        return self._controller.resume()

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
import sys
from typing import Hashable

from macro_studio.core.types_and_enums import TaskFunc, LogLevel, CaptureMode
from macro_studio.core.data import Profile
from macro_studio.core.utils import global_logger
from macro_studio.ui.main_window import MainWindow
from macro_studio.core.controllers.task_manager import TaskManager


class MacroStudio:
    def __init__(self, macro_name: str):
        self._profile = Profile(macro_name)
        self._closing = False
        self._manager = TaskManager(self, self._profile)
        self._profile_name = macro_name

        # Setup UI stuff
        self.ui = MainWindow(self._profile)
        self.app = self.ui.app
        self.overlay = self.ui.overlay

        # Connect Listeners
        self.ui.start_signal.connect(self.startMacroExecution)
        self.ui.pause_signal.connect(self.pauseMacroExecution)
        self.ui.stop_signal.connect(self._handleStopSignal)
        self._manager.finished_signal.connect(lambda: self.cancelMacroExecution(True))

    def addVar(self, key: Hashable, data_type: CaptureMode | type, default_val: object=None, pick_hint: str=None):
        """
        Add a setup step to gather variables.

        If the key is present already and value types differ, overwrites the previous variable.
        Args:
            key: The key to store the variable under.
            data_type: The value type of the variable.
            default_val: The default value of this step.
            pick_hint: The hint to display while the variable is being picked or hovered over
        """
        self._profile.vars.add(key, data_type, default_val, pick_hint)

    def getVar(self, key: Hashable):
        """
        Get the value for a setup variable.
        Args:
            key: The key that the variable should be stored under.
        Returns:
            The value for a setup variable if present or None.
        """
        var_config = self._profile.vars.get(key)
        return var_config and var_config.value or None

    def addRunTask(self, task_func: TaskFunc, auto_loop=False):
        """
        Add a task function to run when executing macros.
        Args:
            task_func: The function.
            auto_loop: If the controller should restart itself upon finishing.
        Returns:
            The task controller handle.
        """
        return self._manager.createController(task_func, auto_loop)

    def isRunningMacros(self):
        """
        Returns:
            True if the app is running any macros, false otherwise.
        """
        return self._manager.worker.running

    def startMacroExecution(self):
        """Begins macro execution. If the engine is paused, resumes execution."""
        if self.isRunningMacros():
            if self.isPaused():
                self.resumeMacroExecution()
            return

        self.ui.startMacroVisuals()
        self._manager.startWorker()

    @property
    def loop_delay(self):
        """
        Returns:
            The loop delay (in seconds) for auto looping tasks.
        """
        return self._manager.loop_delay

    @loop_delay.setter
    def loop_delay(self, delay: float):
        """
        Sets the loop delay for auto looping tasks.
        Args:
            delay: The delay in seconds.
        """
        self._manager.loop_delay = delay

    def _handleStopSignal(self, killed: bool):
        self.cancelMacroExecution()
        # Save vars on program killed
        if killed: self._profile.save()

    def cancelMacroExecution(self, completed=False):
        """Cancel currently executing macros."""
        if not self.isRunningMacros():
            self.ui.stopMacroVisuals()
            return
        self.ui.startMacroVisuals()
        success = self._manager.stopWorker()
        if success:
            global_logger.log("Globally Cancelled Execution" if not completed else "Macro Finished. All tasks completed.")
            self.ui.stopMacroVisuals()

    def pauseMacroExecution(self, interrupt: bool=True):
        """
        Pauses the currently running task.

        Args:
            interrupt: Controls the mechanism used to pause.

                * ``True`` (Default): **Interrupt & Cleanup.** Raises a ``TaskInterruptedException`` inside the task.
                  This breaks the current step immediately (e.g., cuts short a ``taskSleep``), runs any
                  ``try/finally`` cleanup blocks to **release keys** and reset state, and then suspends.
                * ``False``: **Freeze.** Suspends the generator execution at the exact current line.
                  No cleanup logic is triggered; held keys remain held and local variables are preserved exactly as-is.
        Returns:
            ``True`` if the pause command was issued successfully; ``False`` if the engine could not be stopped.
        """
        if not self.isRunningMacros():
            global_logger.log("Cannot pause: Worker is already stopped.", level=LogLevel.WARN)
            self.ui.stopMacroVisuals()
            return False

        self.ui.startMacroVisuals()
        success = self._manager.pauseWorker(interrupt)
        if success:
            if self.isRunningMacros():
                self.ui.pauseMacroVisuals()
                if interrupt:
                    global_logger.log(
                        "Global Interrupt Active: Running tasks interrupted and cleaned up. (Current wait timers cancelled).")
                else:
                    global_logger.log("Global Pause Active")
            else:
                # Interrupt killed running tasks
                self.ui.stopMacroVisuals()

        return success

    def isPaused(self):
        return self._manager.worker.isPaused()

    def resumeMacroExecution(self):
        """
        If previously paused, resumes macro execution.
        Returns:
            The duration paused for in seconds or ``None`` if not paused.
        """
        elapsed = self._manager.resumeWorker()
        if elapsed is not None:
            global_logger.log(f"Resumed Execution After {elapsed:.2f} Seconds.")
            self.ui.resumeMacroVisuals()

        return elapsed

    def launch(self):
        self.ui.show()
        self.app.exit()
        sys.exit(self.app.exec())
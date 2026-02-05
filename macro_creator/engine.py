import sys
from typing import Hashable, List, Dict
from .task_controller import TaskController
from .types_and_enums import TaskFunc, Pickable
from .gui_main import MainWindow
from .macro_worker import MacroWorker
from .variable_config import VariableConfig


class MacroCreator:
    def __init__(self):
        self._task_controllers: List[TaskController] = []
        self._setup_vars: Dict[Hashable, VariableConfig] = {}
        self._closing = False
        self._worker = MacroWorker()

        # Setup UI stuff
        self.ui = MainWindow()
        self.app = self.ui.app
        self.overlay = self.ui.overlay

        # Connect Listeners
        self.ui.start_signal.connect(self.startMacroExecution)
        self.ui.pause_signal.connect(self.pauseMacroExecution)
        self.ui.stop_signal.connect(self.cancelMacroExecution)
        self._worker.finished_signal.connect(lambda: self.cancelMacroExecution(True))

    def addVariable(self, key: Hashable, data_type: Pickable | type, default_val: object=None, pick_hint: str=None):
        """
        Add a setup step to gather variables. If key is already present, overwrites the previous variable.
        :param key: The key to store the variable under.
        :param data_type: The data type of the variable.
        :param default_val: The default value of this step.
        :param pick_hint: The hint to display while the variable is being picked or hovered over
        """
        config = VariableConfig(data_type, default_val, pick_hint)
        self._setup_vars[key] = config
        self.ui.addSetupItem(key, config)

    def getVar(self, key: Hashable):
        """
        Get the value for a setup variable.
        :param key: The key that the variable should be stored under.
        :return: The value for a setup variable if present.
        """
        var_config = self._setup_vars.get(key)
        return var_config and var_config.value or None

    def addRunTask(self, task_func: TaskFunc) -> TaskController:
        """
        Add a task function to run when executing macros.
        :param task_func: The function.
        :return: The task controller handle.
        """
        controller = TaskController(self._worker, task_func, len(self._task_controllers))
        self._task_controllers.append(controller)
        return controller

    def isRunningMacros(self):
        """Check if the creator is running any macros."""
        return self._worker.running

    def startMacroExecution(self):
        """Begin executing macros. If we were paused, resumes execution."""
        if self._worker.running:
            if self.isPaused():
                self.resumeMacroExecution()
            return

        self._worker.pause_state.clear()
        self._worker.running = True
        self._worker.reloadControllers(self._task_controllers)
        self.ui.startMacroVisuals()
        self.ui.log("Starting Macro...")
        self._worker.start()

    def cancelMacroExecution(self, completed=False):
        """Cancel currently executing macros."""
        if not self.isRunningMacros(): return
        self.ui.log("Globally Cancelled Execution" if not completed else "[SUCCESS] Macro Finished. All tasks completed successfully.")
        self._worker.stop()
        self.ui.stopMacroVisuals()

    def pauseMacroExecution(self, hard: bool=True):
        """
        If the engine was running, pauses macro execution.
        :param hard:
            hard=True (default): Interrupts the task to release keys and clean up resources safely.
            hard=False: Freezes the task in place (keys remain held down).
        :return: True if paused successfully, false if the engine has stopped
        """
        if not self._worker.running:
            self.ui.log("[WARNING] Cannot pause: Worker is already stopped.")
            self.ui.stopMacroVisuals()
            return False

        still_running = self._worker.pause(hard)
        if still_running:
            self.ui.pauseMacroVisuals()
            if hard:
                self.ui.log("Global Hard Pause active. Running tasks interrupted and cleaned up. (Current wait timers cancelled).")
            else:
                self.ui.log("Global Pause active")
        else:
            self.ui.stopMacroVisuals()
            self.ui.log("[FAILURE] System terminated all active tasks during hard pause attempt.")
        return still_running

    def isPaused(self):
        return self._worker.isPaused()

    def isHardPaused(self):
        """:return: Whether the current pause state is hard or not."""
        return self._worker.pause_state.is_hard

    def resumeMacroExecution(self):
        """
        If previously paused, resumes macro execution
        :return: The duration paused for in seconds or None if not paused.
        """
        elapsed = self._worker.resume() if self.isRunningMacros() else None
        if elapsed is not None:
            self.ui.log(f"Resumed Execution After {elapsed} Seconds.")
            self.ui.resumeMacroVisuals()

        return elapsed

    def launch(self):
        self.ui.show()
        self.app.exit()
        sys.exit(self.app.exec())

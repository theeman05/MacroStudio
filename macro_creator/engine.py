import os
import sys
from typing import Hashable

from .task_controller import TaskController
from .types_and_enums import TaskFunc, LogLevel, LogPacket, CaptureMode
from .gui_main import MainWindow
from .macro_worker import MacroWorker
from .variable_config import VariableConfig
from .profile_manager import ProfileManager
from .capture_type_registry import GlobalCaptureRegistry

class MacroCreator:
    def __init__(self, macro_name: str):
        self._task_controllers: list[TaskController] = []
        self._setup_vars: dict[str, VariableConfig] = ProfileManager.loadVariables(_getVariableFilepath(macro_name))
        self._closing = False
        self._worker = MacroWorker(self)
        self._profile_name = macro_name

        # Setup UI stuff
        self.ui = MainWindow(macro_name)
        self.app = self.ui.app
        self.overlay = self.ui.overlay

        # Add loaded variables to the ui
        for key_str, config in self._setup_vars.items():
            self.ui.addSetupItem(key_str, config)

        # Connect Listeners
        self.ui.start_signal.connect(self.startMacroExecution)
        self.ui.pause_signal.connect(self.pauseMacroExecution)
        self.ui.stop_signal.connect(self._handleStopSignal)
        self._worker.finished_signal.connect(lambda: self.cancelMacroExecution(True))
        self._worker.log_signal.connect(lambda packet: self.ui.log(packet))

    def addVariable(self, key: Hashable, data_type: CaptureMode | type, default_val: object=None, pick_hint: str=None):
        """
        Add a setup step to gather variables.

        If the key is present already and data types differ, overwrites the previous variable.
        Args:
            key: The key to store the variable under.
            data_type: The data type of the variable.
            default_val: The default value of this step.
            pick_hint: The hint to display while the variable is being picked or hovered over
        """
        key_str = VariableConfig.keyToStr(key)
        if key_str not in self._setup_vars:
            config = VariableConfig(data_type, default_val, pick_hint)
            self._setup_vars[key_str] = config
            self.ui.addSetupItem(key_str, config)
        else:
            config = self._setup_vars[key_str]
            has_changes = False
            if config.hint != pick_hint and pick_hint is not None:
                config.hint = pick_hint
                has_changes = True

            data_type = GlobalCaptureRegistry.get(data_type).type_class if GlobalCaptureRegistry.containsMode(data_type) else data_type

            # If data types differ, or there's no value for config, overwrite the previous value and data type
            if (data_type is not config.data_type) or (config.value is None and default_val != config.value):
                has_changes = True
                config.data_type = data_type
                config.value = default_val

            if has_changes: self.ui.refreshSetupItemView(config)

    def getVar(self, key: Hashable):
        """
        Get the value for a setup variable.
        Args:
            key: The key that the variable should be stored under.
        Returns:
            The value for a setup variable if present or None.
        """
        var_config = self._setup_vars.get(VariableConfig.keyToStr(key))
        return var_config and var_config.value or None

    def addRunTask(self, task_func: TaskFunc) -> TaskController:
        """
        Add a task function to run when executing macros.
        Args:
            task_func: The function.

        Returns:
            The task controller handle.
        """
        controller = TaskController(self._worker, task_func, len(self._task_controllers))
        self._task_controllers.append(controller)
        return controller

    def isRunningMacros(self):
        """
        Returns:
            True if the creator is running any macros, false otherwise.
        """
        return self._worker.running

    def startMacroExecution(self):
        """Begins macro execution. If the engine is paused, resumes execution."""
        if self._worker.running:
            if self.isPaused():
                self.resumeMacroExecution()
            return

        self._worker.pause_state.clear()
        self._worker.running = True
        self._worker.reloadControllers(self._task_controllers)
        self.ui.startMacroVisuals()
        self._log("Starting Macro...")
        self._worker.start()

    def _handleStopSignal(self, killed: bool):
        self.cancelMacroExecution()
        # Save vars on program killed
        if killed: ProfileManager.saveVariables(_getVariableFilepath(self._profile_name), self._setup_vars)

    def cancelMacroExecution(self, completed=False):
        """Cancel currently executing macros."""
        if not self.isRunningMacros(): return
        self._log("Globally Cancelled Execution" if not completed else "Macro Finished. All tasks completed.")
        self._worker.stop()
        self.ui.stopMacroVisuals()

    def pauseMacroExecution(self, hard: bool=True):
        """
        If the engine was running, pauses macro execution.
        Args:
            hard: Controls how the pause is handled.

                * ``True`` (Default): Interrupts the task to **release keys** and **clean up resources** safely.
                * ``False``: **Freezes** the task in place (keys remain held down).
         Returns:
             ``True`` if paused successfully, ``False`` if the engine has stopped abruptly.
        """
        if not self._worker.running:
            self._log("Cannot pause: Worker is already stopped.", level=LogLevel.WARN)
            self.ui.stopMacroVisuals()
            return False

        still_running = self._worker.pause(hard)
        if still_running:
            self.ui.pauseMacroVisuals()
            if hard:
                self._log("Global Hard Pause active. Running tasks interrupted and cleaned up. (Current wait timers cancelled).")
            else:
                self._log("Global Pause active")
        else:
            self.ui.stopMacroVisuals()
        return still_running

    def isPaused(self):
        return self._worker.isPaused()

    def resumeMacroExecution(self):
        """
        If previously paused, resumes macro execution.
        Returns:
            The duration paused for in seconds or ``None`` if not paused.
        """
        elapsed = self._worker.resume() if self.isRunningMacros() else None
        if elapsed is not None:
            self.ui.log(f"Resumed Execution After {elapsed} Seconds.")
            self.ui.resumeMacroVisuals()

        return elapsed

    def _log(self, *args, level: LogLevel = LogLevel.INFO):
        """
        Sends a structured log packet to the ui.
        Args:
            args: The objects to be printed in the log. If mode is not ERROR, will cast the args automatically.
            level: The log level to display at.
        """
        payload = LogPacket(parts=args, level=level, task_id=-1)
        self.ui.log(payload)

    def launch(self):
        self.ui.show()
        self.app.exit()
        sys.exit(self.app.exec())

def _getVariableFilepath(macro_name: str) -> str:
    base_dir = os.path.join(os.getcwd(), "data", "variables")

    os.makedirs(base_dir, exist_ok=True)

    safe_name = "".join(c for c in macro_name if c.isalnum() or c in (' ', '_', '-')).strip()
    safe_name = safe_name.replace(" ", "_").lower()

    return os.path.join(base_dir, f"{safe_name}.json")
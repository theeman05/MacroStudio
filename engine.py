import sys, time
from dataclasses import dataclass
from typing import Hashable, List
from task_controller import TaskController
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRect
from types_and_enums import TaskFunc, Pickable
from gui_main import MainWindow
from overlay import TransparentOverlay
from macro_worker import MacroWorker

@dataclass
class TaskState:
    og_func: TaskFunc
    generation: int= 0
    paused: bool= False

class MacroCreator:
    def __init__(self):
        self._task_controllers: List[TaskController] = []
        self._setup_vars = {}
        self._closing = False
        self._pending_capture_data = None
        self._worker = MacroWorker()

        # Setup UI stuff
        self.ui = MainWindow()
        self.app = self.ui.app
        self.overlay = self.ui.overlay

        # Connect Listeners
        self.ui.start_signal.connect(self.startMacroExecution)
        self.ui.pause_signal.connect(self.pauseMacroExecution)
        self.ui.stop_signal.connect(self.cancelMacroExecution)
        self.ui.request_capture_signal.connect(self._startMouseCapture)
        self._worker.finished_signal.connect(lambda: self.cancelMacroExecution(True))
        self.overlay.capture_complete_signal.connect(self._onCaptureComplete)
        self.overlay.capture_cancelled_signal.connect(self._onCaptureComplete)

    def _startMouseCapture(self, row, var_id, mode, var_display_text):
        self._pending_capture_data = (row, var_id)
        self.ui.hide()
        self.overlay.render_geometry = self._setup_vars
        self.overlay.startCapture(mode, var_display_text)

    def _onCaptureComplete(self, result=None):
        row, var = self._pending_capture_data
        self._pending_capture_data = None

        if result:
            if isinstance(result, QRect):
                val_str = f"(x:{result.x()}, y:{result.y()}, w:{result.width()}, l:{result.height()})"
            else:
                val_str = f"({result.x()}, {result.y()})"
            self._setup_vars[var] = result
        else:
            val_str = self._setup_vars.get(var)

        # 2. Save and Update UI
        self.ui.updateVariableValue(row, val_str)

        # 3. Restore State
        self.overlay.setClickThrough(True)
        self.ui.toggleOverlay()
        self.ui.show()

    def addVariable(self, key: Hashable, val_type: Pickable | object, default_val: object=None, display_str: str=None):
        """
        Add a setup step to gather variables. If key is already present, overwrites the previous step.
        :param key: The key to store the variable under.
        :param val_type: The type of the variable.
        :param default_val: The default value of this step.
        :param display_str: The string to display while the variable is being chosen (if applicable)
        """
        self.ui.addSetupItem(key, val_type, default_val, display_str)
        if default_val is not None:
            self._setup_vars[key] = default_val

    def getVar(self, key: Hashable):
        """
        Get the value for a setup variable.
        :param key: The key that the variable should be stored under.
        :return: The value for a setup variable if present.
        """
        return self._setup_vars.get(key)

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

        self._worker.paused_at = 0
        self._worker.running = True
        self._worker.reloadControllers(self._task_controllers)
        self.ui.startMacroVisuals()
        self.ui.log("Starting...")
        self._worker.start()

    def cancelMacroExecution(self, completed=False):
        """Cancel currently executing macros."""
        if not self.isRunningMacros(): return
        self.ui.log("Cancelled Execution" if not completed else "Macro Completed Successfully")
        self._worker.stop()
        self.ui.stopMacroVisuals()

    def pauseMacroExecution(self):
        if self.isRunningMacros() and not self._worker.paused_at:
            self._worker.pause()
            self.ui.pauseMacroVisuals()
            self.ui.log("Paused Execution")

    def isPaused(self):
        return self._worker.paused_at

    def resumeMacroExecution(self):
        paused_at = self._worker.paused_at
        if self.isRunningMacros() and self._worker.paused_at:
            self.ui.log(f"Resumed Execution After {time.time() - paused_at} Seconds.")
            self._worker.resume()
            self.ui.resumeMacroVisuals()

    def mainLoop(self):
        self.ui.show()
        self.app.exit()
        sys.exit(self.app.exec())

import sys
import time, heapq
from dataclasses import dataclass
from typing import Hashable, List, Generator
from task_controller import TaskController
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRect, QTimer
from pynput import keyboard
from types_and_enums import CaptureMode, TaskFunc, SetupVariable, SetupVariables
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
        self._task_heap: List[(Generator,TaskController)] = []
        self._setup_vars: SetupVariables = {}
        self._running = False
        self._paused = False
        self._closing = False
        self._pending_capture_data = None
        self._worker = MacroWorker()

        # Setup UI stuff
        self.app = QApplication(sys.argv)
        self.overlay = TransparentOverlay(self.app)
        self.ui = MainWindow(self.overlay)

        # Connect Listeners
        self.ui.start_signal.connect(self.startMacroExecution)
        self.ui.pause_signal.connect(self.pauseMacroExecution)
        self.ui.stop_signal.connect(self.cancelMacroExecution)
        self.ui.request_capture_signal.connect(self._startMouseCapture)
        self._worker.finished_signal.connect(self.cancelMacroExecution)
        self.overlay.capture_complete_signal.connect(self.on_capture_complete)
        self.overlay.capture_cancelled_signal.connect(self.on_capture_complete)
        self.listener = keyboard.GlobalHotKeys({
            '<f10>': self.cancelMacroExecution
        })
        self.listener.start()

    def _startMouseCapture(self, row, var_id, mode, var_display_text):
        self._pending_capture_data = (row, var_id)
        self.ui.hide()
        self.overlay.render_geometry = self._setup_vars
        self.overlay.startCapture(mode, var_display_text)

    def on_capture_complete(self, result=None):
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
        self.ui.update_variable_value(row, val_str)

        # 3. Restore State
        self.overlay.setClickThrough(True)
        self.ui.toggle_overlay()
        self.ui.show()

    def addSetupStep(self, key: Hashable, mode: CaptureMode, display_str: str):
        """
        Add a setup step to gather variables. If key is already present, overwrites the previous step.
        :param key: The key to store the variable under.
        :param mode: The mode of user input.
        :param display_str: The string to display while the step is running.
        """
        self.ui.add_setup_item(key, mode, display_str)

    def finishSetup(self, setup_vars: SetupVariables=None):
        """
        If setup_vars is present sets our setup vars to them, or clears the current dict of vars if not.
        :param setup_vars: Variables to set.
        """
        if setup_vars:
            self._setup_vars = setup_vars
        else:
            self._setup_vars.clear()

    def getVar(self, key: Hashable) -> SetupVariable | None:
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
        controller = TaskController(self, task_func, len(self._task_controllers))
        self._task_controllers.append(controller)
        return controller

    def isRunningMacros(self):
        """Check if the creator is running any macros."""
        return self._running

    def scheduleController(self, controller: TaskController, version: int, wake_time: float):
        """Schedule a controller to run at the wake time assuming macros are running."""
        if self.isRunningMacros():
            controller.wake_time = wake_time
            heapq.heappush(self._task_heap, (controller, version))

    def startMacroExecution(self):
        """Begin executing macros. If we were paused, resumes execution."""
        if self._running or self._worker.running:
            if self._paused:
                self.resumeMacroExecution()
            return

        self._running = True

        # Restart state of controllers and push them to our queue
        for controller in self._task_controllers:
            controller.restart()

        self.ui.start_macro_visuals()
        self._worker.paused = False
        self._worker.running = True
        self._worker.run()

    def cancelMacroExecution(self):
        """Cancel currently executing macros."""
        if not self._running: return
        self._running = self._paused = False
        prev_heap = self._task_heap
        if not self._closing:
            self.ui.stop_macro_visuals()
        self._task_heap = []
        # Cleanup previous tasks that were going to run
        for controller, _ in prev_heap:
            controller.stop()

    def pauseMacroExecution(self):
        if self._running and not self._paused:
            for controller, _ in self._task_heap:
                controller.pause()
            self._paused = True
            self.ui.pause_macro_visuals()

    def resumeMacroExecution(self):
        prev_heap = self._task_heap
        if self._running and self._paused and prev_heap:
            # Discard old heap since tasks will be re-added upon resuming
            self._task_heap = []
            # Resume items in the heap
            for controller, _ in prev_heap:
                controller.resume()
            self._paused = False
            self.ui.resume_macro_visuals()

    # Checks active tasks, runs them if their wait time is over, and schedules the next check
    def _runScheduler(self):
        if not self._running: return

        current_time = time.time()
        # Process all tasks that are ready 'right now'
        while self._task_heap:
            # Peek time and task ID
            task_controller, prev_version = self._task_heap[0]
            # If generations differ, it should be removed from the heap, so we don't want to wait until awake
            if self._paused or task_controller.wake_time > current_time and prev_version == task_controller.getGeneration():
                break

            # Pop Task
            task_controller, version = heapq.heappop(self._task_heap)

            # If generations differ, drop it
            if version != task_controller.getGeneration():
                continue  # Discard old task if generations differ

            if task_controller.isPaused():
                # If the controller is paused, go back to it again after a little to see if it's unpaused
                self.scheduleController(task_controller, version, current_time + 0.1)
                continue

            try:
                # Run the task using next
                wait_duration = next(task_controller)
                if wait_duration is None: wait_duration = 0

                # Push it back with new time
                self.scheduleController(task_controller, version, current_time + float(wait_duration))
            except StopIteration:
                task_controller.stop()
            except Exception as e:
                print(f"Error: {e}")
                task_controller.stop()
                self.cancelMacroExecution()
                return

        if self._task_heap or self._paused:
            if not self._paused:
                next_event_time = self._task_heap[0][0].wake_time
                delay_sec = next_event_time - time.time()
            else:
                # We're paused, wait a little and check again
                delay_sec = .01

            # Convert to ms, ensure at least 1ms, max 50ms
            delay_ms = int(max(1, min(delay_sec * 1000, 50)))

            # Schedule next tick, but clamp it to 50ms max so we can cancel properly
            QTimer.singleShot(delay_ms, self._runScheduler)
        else:
            self.ui.log("Macro completed successfully!")
            self.cancelMacroExecution()
            self.ui.stop_macro_visuals()

    def isPaused(self):
        return self._paused

    def mainLoop(self):
        try:
            self.ui.show()
        except KeyboardInterrupt:
            pass

        self._closing = True
        self.cancelMacroExecution()
        self.app.exit()
        sys.exit(self.app.exec())
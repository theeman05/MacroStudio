import time, heapq
import tkinter as tk
from collections import OrderedDict
from PyQt5.QtCore import QPoint, QRect
from dataclasses import dataclass
from typing import Hashable, List, Generator, Dict
from types_and_enums import ClickMode, SetupStep, TaskFunc
from task_controller import TaskController
from gui import TKApp

@dataclass
class TaskState:
    og_func: TaskFunc
    generation: int= 0
    is_paused: bool= False

def macroWait(duration: float):
    """
    Yields control back to the scheduler for 'duration' seconds.
    Call "yield from" on this method to yield correctly
    Usage in task: yield from self.macroWait(2.0)
    """
    yield duration

class MacroCreator:
    def __init__(self):
        self.setup_steps = OrderedDict()
        self._task_controllers: List[TaskController] = []
        self._task_heap: List[(Generator,TaskController)] = []
        self.setup_vars: Dict[Hashable, QRect | QPoint] = {}
        self._root_tk = tk.Tk()
        self._tk_app = TKApp(self, self._root_tk)
        self._is_running = False

    def addSetupStep(self, key: Hashable, mode: ClickMode, display_str: str):
        self.setup_steps[key] = SetupStep(display_str, mode)

    def finishSetup(self, setup_vars=None):
        if setup_vars:
            self.setup_vars = setup_vars
        else:
            self.setup_vars.clear()

    def addRunTask(self, task_func: TaskFunc) -> TaskController:
        """
        Add a task to run when executing macros.
        :return: The task controller
        """
        controller = TaskController(self, task_func, len(self._task_controllers))
        self._task_controllers.append(controller)
        return controller

    def isRunningMacros(self):
        return self._is_running

    def scheduleController(self, controller: TaskController, generator: Generator, wake_time: float):
        """Schedule a controller to run at the wake time with the given generator assuming macros are running"""
        if self.isRunningMacros():
            controller.wake_time = wake_time
            heapq.heappush(self._task_heap, (controller, generator))

    def startMacroExecution(self):
        if self._is_running: return
        self._is_running = True

        # Restart state of controllers and push them to our queue
        for controller in self._task_controllers:
            controller.restart()

        self._runScheduler()

    def cancelMacroExecution(self):
        if not self._is_running: return
        self._is_running = False
        self._task_heap = []

        # Checks active tasks, runs them if their wait time is over, and schedules the next check
    def _runScheduler(self):
        if not self._is_running:
            return

        current_time = time.time()
        # Process all tasks that are ready 'right now'
        while self._task_heap:
            # Peek time and task ID
            task_controller, prev_gen = self._task_heap[0]
            # If generators differ, it should be removed from the heap, so we don't want to wait until awake
            if task_controller.wake_time > current_time and prev_gen == task_controller.getGenerator():
                break

            # Pop Task
            task_controller, gen = heapq.heappop(self._task_heap)

            # If generators differ, drop it
            if gen != task_controller.getGenerator():
                continue  # Discard old task if generations differ

            if task_controller.isPaused():
                # If the controller is paused, go back to it again after a little
                self.scheduleController(task_controller, gen, current_time + 0.1)
                continue

            try:
                # Run the task using next
                wait_duration = next(gen)
                if wait_duration is None: wait_duration = 0

                # Push it back with new time
                self.scheduleController(task_controller, gen, current_time + float(wait_duration))
            except StopIteration:
                pass  # Task finished, don't push back
            except Exception as e:
                print(f"Error: {e}")
                self.cancelMacroExecution()
                return

        if self._task_heap:
            next_event_time = self._task_heap[0][0].wake_time
            delay_sec = next_event_time - time.time()

            # Convert to ms, ensure at least 1ms, max 50ms
            delay_ms = int(max(1, min(delay_sec * 1000, 50)))

            # Schedule next tick, but clamp it to 50ms max so we can cancel properly
            self._root_tk.after(delay_ms, self._runScheduler)
        else:
            self._tk_app.debug_var.set("Macro completed successfully")
            self.cancelMacroExecution()
            self._tk_app.toggleRun(False)

    def mainLoop(self):
        try:
            self._root_tk.mainloop()
        except KeyboardInterrupt:
            pass

        self.cancelMacroExecution()
        self._tk_app.cleanup()
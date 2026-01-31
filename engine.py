import time, heapq
import tkinter as tk
from collections import OrderedDict
from dataclasses import dataclass
from typing import Hashable, List, Generator
from types_and_enums import ClickMode, SetupStep, TaskFunc, SetupVariable, SetupVariables
from task_controller import TaskController
from gui import TKApp

@dataclass
class TaskState:
    og_func: TaskFunc
    generation: int= 0
    paused: bool= False

class MacroCreator:
    def __init__(self):
        self.setup_steps = OrderedDict()
        self._task_controllers: List[TaskController] = []
        self._task_heap: List[(Generator,TaskController)] = []
        self._setup_vars: SetupVariables = {}
        self._root_tk = tk.Tk()
        self._tk_app = TKApp(self, self._root_tk)
        self._running = False
        self._paused = False
        self._closing = False

    def addSetupStep(self, key: Hashable, mode: ClickMode, display_str: str):
        """
        Add a setup step to gather variables. If key is already present, overwrites the previous step.
        :param key: The key to store the variable under.
        :param mode: The mode of user input.
        :param display_str: The string to display while the step is running.
        """
        self.setup_steps[key] = SetupStep(display_str, mode)

    def finishSetup(self, setup_vars: SetupVariables=None):
        """
        If setup_vars is present sets our setup vars to them, or clears the current dict of vars if not.
        :param setup_vars: Variables to set.
        """
        if setup_vars:
            self._setup_vars = setup_vars
        else:
            self._setup_vars.clear()

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
        """Begin executing macros."""
        if self._running: return
        self._running = True

        # Restart state of controllers and push them to our queue
        for controller in self._task_controllers:
            controller.restart()

        self._tk_app.toggleRun(True)
        self._runScheduler()

    def getVar(self, key: Hashable) -> SetupVariable | None:
        """
        Get the value for a setup variable.
        :param key: The key that the variable should be stored under.
        :return: The value for a setup variable if present.
        """
        return self._setup_vars.get(key)

    def cancelMacroExecution(self):
        """Cancel currently executing macros."""
        if not self._running: return
        self._running = self._paused = False
        prev_heap = self._task_heap
        if not self._closing:
            self._tk_app.toggleRun(False)
        self._task_heap = []
        # Cleanup previous tasks that were going to run
        for controller, _ in prev_heap:
            controller.stop()

    def toggleMacroExecution(self):
        """Toggles macro execution."""
        prev_heap = self._task_heap
        if not self._running:
            self._paused = False
            self.startMacroExecution()
        elif self._paused:
            # Discard old heap since tasks will be re-added upon resuming
            self._task_heap = []
            # Resume items in the heap
            for controller, _ in prev_heap:
                controller.resume()
            self._paused = False
        else:
            # Pause items in the heap so they know when to resume
            for controller, _ in prev_heap:
                controller.pause()
            self._paused = True

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
            self._root_tk.after(delay_ms, self._runScheduler)
        else:
            self._tk_app.debug_var.set("Macro completed successfully")
            self.cancelMacroExecution()
            self._tk_app.toggleRun(False)

    def isPaused(self):
        return self._paused

    def mainLoop(self):
        try:
            self._root_tk.mainloop()
        except KeyboardInterrupt:
            pass
        self._closing = True
        self.cancelMacroExecution()
        self._tk_app.cleanup()
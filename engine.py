import time, inspect, heapq
import tkinter as tk
from collections import OrderedDict
from PyQt5.QtCore import QPoint, QRect
from dataclasses import dataclass
from typing import Hashable, Callable, List, Generator, Dict
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

def _tryWrapFun(func):
    """If the function isn't a generator, wraps it into a generator function"""
    if inspect.isgeneratorfunction(func):
        yield from func()
    else:
        func()
        yield

class MacroCreator:
    def __init__(self):
        self.setup_steps = OrderedDict()
        self._run_tasks: List[(Callable[[], Generator | None], Hashable)] = []  # List of generator functions
        self._task_heap = []
        self._task_states: Dict[Hashable, TaskState] = {}
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

    def addRunTask(self, task_func: TaskFunc, task_id:Hashable=None):
        """
        Add a task to run when executing macros.
        task_id: Unique key for the task. If None, it can't be paused by other macros.
        """
        self._run_tasks.append((task_func, task_id))
        # If it has an ID, register it so we can find/reset it later
        if task_id is not None:
            self._task_states[task_id] = TaskState(task_func)

    def isRunningMacros(self):
        return self._is_running

    def startMacroExecution(self):
        if self._is_running: return
        self._is_running = True

        for task_func, task_id in self._run_tasks:
            # Reset previous state of monitor
            if task_id is not None:
                self._task_states[task_id].is_paused = False
                self._task_states[task_id].generation = 0
            gen = _tryWrapFun(task_func)
            # Tuple format: (WakeTime, Generation, TieBreaker, TaskID, Generator)
            heapq.heappush(self._task_heap, (0, 0, id(gen), task_id, gen))

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
            wake_time, cur_gen, _, task_id, _ = self._task_heap[0]
            task_monitor = self._task_states.get(task_id)
            # Safeguard so if generations differ, it will continue and discard old generations
            if wake_time > current_time and (task_monitor is None or task_monitor.generation == cur_gen):
                break

            # Pop Task
            # We now unpack 5 items including 'task_gen'
            _, _, gen_id, _, gen = heapq.heappop(self._task_heap)

            # If this task item belongs to an old generation, it is dead. Drop it.
            if task_monitor:
                if cur_gen != task_monitor.generation:
                    continue  # Discard old task if generations differ

                if task_monitor.is_paused:
                    # Push back with delay, BUT maintain the current 'cur_gen'
                    next_wake = current_time + 0.1
                    heapq.heappush(self._task_heap, (next_wake, cur_gen, gen_id, task_id, gen))
                    continue

            try:
                # Run the task using next
                wait_duration = next(gen)
                if wait_duration is None: wait_duration = 0

                # Push it back with new time
                next_wake = current_time + float(wait_duration)
                heapq.heappush(self._task_heap, (next_wake, cur_gen, gen_id, task_id, gen))
            except StopIteration:
                pass  # Task finished, don't push back
            except Exception as e:
                print(f"Error: {e}")
                self.cancelMacroExecution()
                return

        if self._task_heap:
            next_event_time = self._task_heap[0][0]
            delay_sec = next_event_time - time.time()

            # Convert to ms, ensure at least 1ms, max 50ms
            delay_ms = int(max(1, min(delay_sec * 1000, 50)))

            # Schedule next tick, but clamp it to 50ms max so we can cancel properly
            self._root_tk.after(delay_ms, self._runScheduler)
        else:
            self._tk_app.debug_var.set("Macro completed successfully")
            self.cancelMacroExecution()
            self._tk_app.toggleRun(False)

    def pauseTask(self, task_id: Hashable):
        """Prevents the task from running its next step. Execution continues until task finishes."""
        task_monitor = self._task_states.get(task_id)
        if task_monitor:
            task_monitor.is_paused = True
            print(f"Paused task: {task_id}")

    def stopTask(self, task_id: Hashable):
        """Stops a task, entirely, allowing execution to finish"""
        task_monitor = self._task_states.get(task_id)
        if task_monitor:
            task_monitor.generation = -1
        else:
            print(f"Error: Cannot stop unknown task '{task_id}'")

    def resumeTask(self, task_id: Hashable):
        """Allows the task to continue from where it left off."""
        task_monitor = self._task_states.get(task_id)
        if task_monitor:
            task_monitor.is_paused = False
            print(f"Resumed task: {task_id}")

    def resetTask(self, task_id: Hashable):
        """Kills the current instance of the task and starts a fresh one immediately."""
        if not self.isRunningMacros():
            print("Cannot reset task since macro execution is suspended")

        task_monitor = self._task_states.get(task_id)
        if not task_monitor:
            print(f"Error: Cannot reset unknown task '{task_id}'")
            return

        print(f"HARD RESET: {task_id}")

        # Invalidate the old task by changing the generation number
        task_monitor.generation += 1
        new_gen_num = task_monitor.generation

        # Create the new generator instance
        new_gen = _tryWrapFun(task_monitor.og_func)

        # Schedule it immediately (Wake Time = 0)
        # Tuple format: (WakeTime, Generation, TieBreaker, TaskID, Generator)
        heapq.heappush(self._task_heap, (0, new_gen_num, id(new_gen), task_id, new_gen))

        # Ensure the task isn't paused if it was before
        task_monitor.is_paused = False

    def isTaskPaused(self, task_id):
        task_monitor = self._task_states.get(task_id)
        return False if task_monitor is None else task_monitor.is_paused

    def mainLoop(self):
        try:
            self._root_tk.mainloop()
        except KeyboardInterrupt:
            pass

        self.cancelMacroExecution()
        self._tk_app.cleanup()
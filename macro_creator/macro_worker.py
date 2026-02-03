import time, heapq
from PyQt6.QtCore import QThread, QMutex, QMutexLocker, pyqtSignal
from typing import TYPE_CHECKING, List

from .pause_state import PauseState

if TYPE_CHECKING:
    from .task_controller import TaskController

class MacroWorker(QThread):
    finished_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.pause_state = PauseState()
        self.running = False

        self._mutex = QMutex()
        self._task_heap = []

    def _pushController(self, controller: "TaskController", wake_time: float, cid: int, generation: int):
        """Pushes a controller to the task heap. Assumes we're locked already"""
        heapq.heappush(self._task_heap, (wake_time, cid, generation, controller))

    def scheduleController(self, controller: "TaskController", wake_time: float, cid: int, generation: int):
        """Thread-safe scheduling from outside the worker."""
        with QMutexLocker(self._mutex):
            self._pushController(controller, wake_time, cid, generation)

    def reloadControllers(self, controllers: List["TaskController"]=None):
        """
        Replaces the entire task list in one go.
        :param controllers: controllers to add into the heap. If None, stops the previous controllers.
        """
        with QMutexLocker(self._mutex):
            prev_heap = self._task_heap
            self._task_heap = []
            if controllers:
                for controller in controllers:
                    controller.resetGenerator()
                    self._pushController(controller, *controller.getCompareVariables())
            else:
                # Cleanup previous tasks that were going to run because we're stopping
                for entry in prev_heap:
                    entry[3].stop()

    def run(self):
        completed = False
        while self.running and not self.isPaused():
            should_sleep = True
            delay_ms = 10

            with QMutexLocker(self._mutex):
                if not self.running or self.isPaused():
                    return
                task_heap = self._task_heap
                if task_heap:
                    current_time = time.perf_counter()
                    wake_time, cid, prev_gen, controller = task_heap[0]
                    gens_differ = prev_gen != controller.getGeneration()
                    if wake_time <= current_time or gens_differ:
                        wake_time, cid, generation, controller = heapq.heappop(task_heap)
                        # If generations differ, move to next and discard current
                        if gens_differ: continue
                        should_sleep = False
                    else:
                        # WAIT: Calculate dynamic delay
                        delay_sec = wake_time - current_time
                        delay_ms = int(max(1, min(delay_sec * 1000, 50)))
                else:
                    completed = True

            if completed:
                self.finished_signal.emit()
                return

            if not should_sleep:
                try:
                    # Run the task using next if the task is not paused
                    wait_duration = next(controller) if not controller.isPaused() else .01
                    if wait_duration is None: wait_duration = 0
                    wake_time = current_time + float(wait_duration)
                    # Schedule it to run at the new time
                    controller.wake_time = wake_time
                    self.scheduleController(controller, wake_time, cid, generation)
                except StopIteration:
                    controller.stop()
                except Exception as e:
                    print(f"Error: {e}")
                    controller.stop()
            else:
                self.msleep(delay_ms)

    def resume(self):
        """
        If the worker is running, attempts to resume the worker.
        :return: The duration paused for in seconds or None if not paused.
        """
        elapsed = self.pause_state.clear() if (self.running and not self.isRunning()) else None
        if elapsed is not None:
            with QMutexLocker(self._mutex):
                prev_heap = self._task_heap
                self._task_heap = []
                for wake_time, cid, prev_gen, controller in prev_heap:
                    task_pause_time = controller.paused_at
                    # Add stuff to the wake and paused times so the tasks wake at the correct time.
                    if wake_time:
                        wake_time += elapsed
                        controller.wake_time = wake_time
                    # If a task was paused, we need to add how much time was elapsed since the worker was paused
                    if task_pause_time:
                        controller.paused_at = task_pause_time + elapsed
                    self._pushController(controller, wake_time, cid, prev_gen)

        self.start()
        return elapsed

    def isPaused(self):
        return self.pause_state.active

    def pause(self, hard: bool=True):
        if not self.isPaused():
            self.pause_state.trigger(hard)
            # Wait for loop to exit
            self.wait()

    def stop(self):
        """Safe way to kill the loop"""
        self.running = False
        self.pause_state.clear()
        self.wait()
        self.reloadControllers(None)
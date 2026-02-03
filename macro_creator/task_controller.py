import inspect
import time

from PyQt6.QtCore import QMutex, QMutexLocker
from typing import TYPE_CHECKING, Generator

from .pause_state import PauseState
from .types_and_enums import TaskFunc, MacroAbortException, MacroHardPauseException

if TYPE_CHECKING:
    from .macro_worker import MacroWorker

def _tryWrapFun(func):
    """If the function isn't a generator, wraps it into a generator function"""
    if inspect.isgeneratorfunction(func):
        yield from func()
    else:
        func()
        yield

class TaskController:
    def __init__(self, scheduler: "MacroWorker", task_func: TaskFunc, task_id: int):
        self.func = task_func
        self.pause_state = PauseState()
        self.wake_time = 0

        self._mutex = QMutex()
        self._scheduler = scheduler
        self._id = task_id
        self._generator: Generator | None = None
        self._generation = 0

    def pause(self, hard=False):
        """
        If not paused already, halts the task from running its next step.
        :param hard: If True, will trigger finally clauses, likely discarding remaining task wait time
        """
        if not self.pause_state.active:
            self.pause_state.trigger(hard)

    def _incGen(self):
        with QMutexLocker(self._mutex):
            self._generation += 1

    def resume(self):
        """
        If the engine is running and previously paused, resumes from where it left off.
        If the task finished already, does nothing.
        :return: The duration paused for in seconds or None if not paused.
        """
        elapsed = self.pause_state.clear() if self._scheduler.isRunning() else None
        if elapsed is not None:
            # Increase version to discard previously scheduled generator
            self._incGen()
            # Set the wake time to be how much time was elapsed previously
            new_wake = time.perf_counter() + elapsed
            self.wake_time = new_wake
            # Reschedule this controller to wake when it is supposed to
            self._scheduler.scheduleController(self, *self.getCompareVariables())

        return elapsed

    def resetGenerator(self, create_new: bool=True):
        """Creates a new generator (if create_new is true) and destroys the old one, also resets pause state."""
        generator = self._generator
        self._incGen()
        self.pause_state.clear()
        self.wake_time = 0
        self._generator = create_new and _tryWrapFun(self.func) or None
        if generator:
            generator.close()

    def stop(self):
        """
        Stops a task on its next cycle, allowing execution to finish.
        """
        self.resetGenerator(False)

    def restart(self):
        """If running macros, kills the current instance of the task and starts a fresh one at the next cycle."""
        self.resetGenerator()
        self._scheduler.scheduleController(self, *self.getCompareVariables())

    def isPaused(self):
        """:return: Whether the controller is paused."""
        return self.pause_state.active

    def isRunning(self):
        """Returns if this controller is running currently, or not. If it is paused, it will still be considered as running."""
        return self._generator is not None

    def getGeneration(self):
        """Atomic way to get the current generation"""
        with QMutexLocker(self._mutex):
            return self._generation

    def getCompareVariables(self):
        with QMutexLocker(self._mutex):
            generation = self._generation
        return self.wake_time, self._id, generation

    def sleep(self, duration: float = .01):
        """
        Blocks the current thread with high precision.
        :param duration: Duration to sleep the thread for in seconds.
        :raise MacroAbortException: If stopped.
        :raise MacroHardPauseException: If hard-paused (triggers finally).
        """
        if duration <= 0:
            return

        start_time = time.perf_counter()
        target_time = start_time + duration

        while True:
            # Check for "Hard Pause" (Stop with Cleanup)
            if self.pause_state.is_hard or self._scheduler.pause_state.is_hard:
                raise MacroHardPauseException("Hard Pause triggered")

            if not self.isRunning():
                raise MacroAbortException("Task stopped.")

            # Check for "Soft Pause" (Resumable)
            if self.isPaused() or self._scheduler.isPaused():
                # FREEZE TIME: Calculate how much time was left
                remaining_at_pause = target_time - time.perf_counter()

                # Enter a low-resource loop while waiting for resume
                self._wait_while_paused()

                # RESUME TIME: We are back! Reset target based on NEW current time
                # We add the saved 'remaining' time to right now.
                target_time = time.perf_counter() + remaining_at_pause

                # Restart the loop to re-check status immediately
                continue

            current_time = time.perf_counter()
            remaining = target_time - current_time

            # If time is up, we are done
            if remaining <= 0:
                break

            # Smart Sleep Logic
            if remaining > 0.02:
                # Sleep small chunks so we can react to Pause/Stop signals quickly
                # Sleeping the full 'remaining' would make the method less accurate
                time.sleep(min(remaining - 0.005, 0.1))
            else:
                # Spin-wait for the final millisecond precision
                pass

    def _wait_while_paused(self):
        """Internal helper to loop while paused."""
        while self.isPaused() or self._scheduler.isPaused():
            # Check for Hard Pause/Stop inside the pause loop so we don't get stuck
            if not self.isRunning() or self.pause_state.is_hard or self._scheduler.pause_state.is_hard:
                return  # Break out so the main sleep loop can handle the Exception raise

            time.sleep(0.1)  # Low CPU usage wait

    def __iter__(self):
        return self

    def __next__(self):
        with QMutexLocker(self._mutex):
            return next(self._generator)

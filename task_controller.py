import inspect
import time

from PyQt6.QtCore import QMutex, QMutexLocker

from types_and_enums import TaskFunc, MacroAbortException
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from macro_worker import MacroWorker

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

        self._mutex = QMutex()
        self._scheduler = scheduler
        self._id = task_id
        self._generator: Generator | None = None
        self.paused_at = self.wake_time = 0
        self._generation = 0

    def pause(self):
        """Halts the task from running its next step. Execution continues until task finishes."""
        if not self.paused_at:
            self.paused_at = time.time()

    def _incGen(self):
        with QMutexLocker(self._mutex):
            self._generation += 1

    def resume(self):
        """Allows the task to continue from where it left off. If the task finished already, does nothing."""
        paused_at = self.paused_at
        if paused_at:
            self.paused_at = 0
            prev_wake = self.wake_time
            # Increase version to discard previously scheduled generator
            self._incGen()
            # Set the wake time to be how much time was elapsed previously
            new_wake = max(time.time() + prev_wake - paused_at, 0)
            self.wake_time = new_wake
            # Reschedule this controller to wake when it is supposed to
            self._scheduler.scheduleController(self, *self.getCompareVariables())

    def resetGenerator(self, create_new: bool=True):
        """Creates a new generator (if create_new is true) and destroys the old one"""
        generator = self._generator
        self._incGen()
        self.paused_at = 0
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
        return self.paused_at or self._scheduler.paused_at

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
        :raise MacroAbortException: If creator or this controller is paused.
        """
        start_time = time.perf_counter()
        target_time = start_time + duration

        while True:
            current_time = time.perf_counter()
            remaining = target_time - current_time

            if remaining <= 0:
                break

            if not self._scheduler.isRunning() or self.isPaused():
                raise MacroAbortException()

            # Leave a buffer because Windows sleep is inaccurate.
            # If remaining is lower than 20ms, spins the CPU for the final few milliseconds to be more accurate.
            if remaining > 0.02:
                time.sleep(0.01)

    def __iter__(self):
        return self

    def __next__(self):
        with QMutexLocker(self._mutex):
            return next(self._generator)

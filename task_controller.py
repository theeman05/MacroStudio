import inspect
import time

from types_and_enums import TaskFunc, MacroAbortException
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from engine import MacroCreator

def _tryWrapFun(func):
    """If the function isn't a generator, wraps it into a generator function"""
    if inspect.isgeneratorfunction(func):
        yield from func()
    else:
        func()
        yield

class TaskController:
    def __init__(self, macro_creator: "MacroCreator", task_func: TaskFunc, task_id: int):
        self._creator = macro_creator
        self.id = task_id
        self.func = task_func
        self.wake_time = 0
        self._generation = 0
        self._generator: Generator | None = None
        self._paused_at = None

    def pause(self):
        """Halts the task from running its next step. Execution continues until task finishes."""
        if not self._paused_at:
            self._paused_at = time.time()

    def resume(self):
        """Allows the task to continue from where it left off. If the task finished already, does nothing."""
        paused_at = self._paused_at
        if paused_at:
            # Set the wake time to be how much time was elapsed previously
            prev_wake = self.wake_time
            # Increase version to discard previously scheduled generator
            self._generation += 1
            self._paused_at = None
            # Reschedule this controller to wake when it is supposed to
            self._creator.scheduleController(self, self._generation, max(time.time() + prev_wake - paused_at, 0))

    def stop(self, new_generator: Generator=None):
        """
        Stops a task on its next cycle, allowing execution to finish. Cleans up old generator object.
        :param new_generator: If present, sets the current generator to the passed one.
        """
        self._generation += 1
        generator = self._generator
        self._paused_at = None
        self._generator = new_generator
        if generator:
            generator.close()

    def restart(self):
        """Kills the current instance of the task and starts a fresh one at the next cycle."""
        self.stop(_tryWrapFun(self.func))
        self._creator.scheduleController(self, self._generation, 0)

    def isPaused(self):
        return self._paused_at is not None

    def getGeneration(self):
        return self._generation

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

            if not self._creator.isRunningMacros() or self.isPaused():
                raise MacroAbortException()

            # Leave a buffer because Windows sleep is inaccurate.
            # If remaining is lower than 20ms, spins the CPU for the final few milliseconds to be more accurate.
            if remaining > 0.02:
                time.sleep(0.01)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._generator)

    def __lt__(self, other):
        return (self.wake_time, self.id, self.getGeneration()) < (other.wake_time, other.id, other.getGeneration())

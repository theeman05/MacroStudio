import inspect
import time
from PySide6.QtCore import QMutex, QMutexLocker
from typing import TYPE_CHECKING, Generator, Hashable

from .pause_state import PauseState
from .types_and_enums import TaskFunc, TaskAbortException, TaskInterruptedException, LogLevel

if TYPE_CHECKING:
    from .macro_worker import MacroWorker

class TaskController:
    def __init__(self, scheduler: "MacroWorker", task_func: TaskFunc, task_id: int):
        self.func = task_func
        self.pause_state = PauseState()
        self._wake_time = 0

        self._mutex = QMutex()
        self._scheduler = scheduler
        self._id = task_id
        self._generator: Generator | None = None
        self._generation = 0

    @property
    def wake_time(self):
        with QMutexLocker(self._mutex):
            return self._wake_time

    @wake_time.setter
    def wake_time(self, value):
        with QMutexLocker(self._mutex):
            self._wake_time = value

    @property
    def cid(self):
        return self._id

    def pause(self, interrupt=False):
        """
        If not paused already, halts the task from running its next step.
        Args:
            interrupt: Controls how the pause is handled.

                * ``True``: Interrupts the task to **release keys** and **clean up resources** safely.
                * ``False`` (Default): **Freezes** the task in place (keys remain held down).
         Returns:
             ``True`` if paused successfully, ``False`` if the engine has stopped abruptly.
        """
        if not self.pause_state.active:
            self.pause_state.trigger(interrupt)
            if not interrupt or self.throwInterruptedError():
                return True
            self._scheduler.logControllerAborted(self)
            return False

        return True

    def throwInterruptedError(self):
        """
        Safely attempts to throw a ``TaskInterruptedException`` onto the current generator.
        Returns:
            ``True`` if the task is now hard paused, ``False`` if it was stopped abruptly.
        """
        with QMutexLocker(self._mutex):
            if not self._generator: return False
            try:
                self._generator.throw(TaskInterruptedException)
            except (StopIteration, TaskInterruptedException):
                # If there's nothing left in our generator, the task has been stopped; cleanup
                self._generator = None
                self.pause_state.clear()
                self._generation += 1
                return False

        return True

    def _unsafeGetSortKey(self):
        return self._wake_time, self._id, self._generation

    def resume(self):
        """
        If the engine is running and task was previously paused, resumes from where it left off.
        If the task finished already, does nothing.
        Returns:
            The duration paused for in seconds or ``None`` if not paused.
        """
        was_hard_pause = self.pause_state.interrupted
        elapsed = self.pause_state.clear() if self._scheduler.running else None
        if elapsed is not None:
            # Increase version to discard previously scheduled generator
            # If were hard paused, tries to wake generator immediately
            with QMutexLocker(self._mutex):
                self._generation += 1
                self._wake_time = 0 if was_hard_pause else (self._wake_time + elapsed)
                self._scheduler.moveToActiveAndReschedule(self, *self._unsafeGetSortKey())

        return elapsed

    def _tryWrapFunc(self):
        """If the function isn't a generator, wraps it into a generator function"""
        func = self.func
        sig = inspect.signature(func)
        kwargs = {}

        # Check if they want the 'controller' argument
        if 'controller' in sig.parameters:
            kwargs['controller'] = self  # Inject as the controller

        if inspect.isgeneratorfunction(func):
            yield from func(**kwargs)
        else:
            func(**kwargs)
            yield

    def resetGeneratorAndGetSorKey(self, create_new: bool=True):
        """
        Creates a new generator (if create_new is ``True``) and destroys the old one, also resets pause state.
        Returns:
            The sort key
        """
        self.pause_state.clear()
        with QMutexLocker(self._mutex):
            self._generation += 1
            self._wake_time = 0
            prev_gen = self._generator
            self._generator = self._tryWrapFunc() if create_new else None
            if prev_gen: prev_gen.close()
            return self._unsafeGetSortKey()

    def stop(self):
        """Stops a task on its next cycle. """
        self.resetGeneratorAndGetSorKey(False)

    def restart(self):
        """Kills the current instance of the task and starts a fresh one at the next work cycle."""
        self._scheduler.moveToActiveAndReschedule(self, *self.resetGeneratorAndGetSorKey())

    def isPaused(self):
        return self.pause_state.active

    def isRunning(self):
        """Returns if this controller is running or not. If it is paused, it will still be considered as running."""
        return self._generator is not None

    def getGeneration(self):
        """Atomic way to get the current generation"""
        with QMutexLocker(self._mutex):
            return self._generation

    def delayAndGetSortKey(self, delay: float=None):
        """
        Returns:

            * The comparable variables and optionally delay the wake time.
            * If no delay is provided, resets the wake time to 0.
        """
        with QMutexLocker(self._mutex):
            self._wake_time = 0 if delay is None else (self._wake_time + delay)
            return self._wake_time, self._id, self._generation

    def _waitWhileSoftPaused(self):
        while self.isPaused() or self._scheduler.isPaused():
            # Check for Hard Pause/Stop inside the pause loop so we don't get stuck
            if not self.isRunning() or self.pause_state.interrupted or self._scheduler.pause_state.interrupted:
                return  # Break out so the main sleep loop can handle the Exception raise

            time.sleep(0.1)  # Low CPU usage wait

    def sleep(self, duration: float = .01):
        """
        Blocks the current thread with high precision.
        Args:
            duration: Duration to sleep the thread for in seconds.
        Raises:
            TaskAbortException: If stopped while sleeping.
            TaskInterruptedException: If interrupted while sleeping.
        """
        if duration <= 0:
            return

        start_time = time.perf_counter()
        target_time = start_time + duration

        while True:
            # Check for "Hard Pause" (Stop with Cleanup)
            if self.pause_state.interrupted or self._scheduler.pause_state.interrupted:
                raise TaskInterruptedException("Hard Pause triggered")

            if not self.isRunning():
                raise TaskAbortException("Task stopped.")

            # Check for "Soft Pause" (Resumable)
            if self.isPaused() or self._scheduler.isPaused():
                # FREEZE TIME: Calculate how much time was left
                remaining_at_pause = target_time - time.perf_counter()

                # Enter a low-resource loop while waiting for resume
                self._waitWhileSoftPaused()

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

    def waitForResume(self):
        """
        Blocks the thread **ONLY** if the system or this task is in an interrupted pause.
        If the task is just 'Soft Paused' (logic wait), this returns immediately.
        Raises:
            TaskAbortException: If stopped while waiting.
        """
        while self.isRunning() and (self.pause_state.interrupted or self._scheduler.pause_state.interrupted):
            time.sleep(0.1)  # Low CPU usage wait

        # If one of the two are no longer running, throw abort exception
        if not (self._scheduler.isRunning() and self.isRunning()):
            raise TaskAbortException("Worker stopped while waiting for resume.")

    def log(self, *args, level: LogLevel=LogLevel.INFO):
        """
        Sends a structured log packet to the ui.
        Args:
            args: The objects to be printed in the log. If mode is not ERROR, will cast the args automatically.
            level: The log level to display at.
        """
        self._scheduler.log(*args, level=level, task_id=self._id)

    def logError(self, error_msg, trace=""):
        """Sends a specialized LogErrorPacket object to the ui."""
        self._scheduler.logError(error_msg, trace, self._id)

    def getVar(self, key: Hashable):
        """
        Get the value for a setup variable.
        Args:
            key: The key that the variable should be stored under.
        Returns:
            The value for a setup variable if present or None.
        """
        return self._scheduler.engine.getVar(key)

    def __iter__(self):
        return self

    def __next__(self):
        with QMutexLocker(self._mutex):
            return next(self._generator)

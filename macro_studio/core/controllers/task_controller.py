import inspect, time
from enum import Enum, auto
from PySide6.QtCore import QMutex, QMutexLocker
from typing import TYPE_CHECKING, Generator, Hashable

from macro_studio.core.types_and_enums import TaskFunc, TaskAbortException, TaskInterruptedException, LogLevel
from macro_studio.core.utils import global_logger
from macro_studio.api.task_context import TaskContext

if TYPE_CHECKING:
    from macro_studio.core.execution.task_worker import TaskWorker


class TaskState(Enum):
    RUNNING = auto()       # Actively executing or waiting for a wake cycle
    PAUSED = auto()        # Soft paused (frozen in place, retaining local variables)
    INTERRUPTED = auto()   # Hard paused (generator destroyed, waiting for respawn)
    STOPPED = auto()


class TaskController:
    def __init__(self, scheduler: "TaskWorker", task_func: TaskFunc, task_id: int, auto_loop=False, unique_name: str | int=None, is_enabled=True):
        self.func = task_func
        self.auto_loop = auto_loop
        self.state_change_by_worker = False

        self._state = TaskState.RUNNING if is_enabled else TaskState.STOPPED
        self._pause_timestamp = 0.0
        self._wake_time = 0.0
        self._is_enabled = is_enabled
        self._mutex = QMutex()
        self._scheduler = scheduler
        self._id = task_id
        self._name = unique_name or task_id
        self._generator: Generator | None = None
        self._generation = 0
        self._context = TaskContext(self)

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

    def getName(self):
        return self._name

    def setEnabled(self, enabled: bool):
        if self._is_enabled == enabled: return
        self._is_enabled = enabled
        if enabled:
            self.restart()
        else:
            self.stop()

    def isEnabled(self):
        return self._is_enabled

    def isAlive(self):
        return self._state != TaskState.STOPPED

    def isPaused(self):
        return self._state in (TaskState.PAUSED, TaskState.INTERRUPTED)

    def isRunning(self):
        return self._state == TaskState.RUNNING

    def isInterrupted(self):
        return self._state == TaskState.INTERRUPTED

    def _unsafeResetGenerator(self, new_state: TaskState, wake_time: float=None):
        self._generation += 1
        self._wake_time = wake_time or 0
        self._state = new_state
        self.state_change_by_worker = False
        self._generator = self._tryWrapFunc() if new_state != TaskState.STOPPED else None

    def throwInterruptedError(self, by_worker=False):
        """
        Safely attempts to throw a ``TaskInterruptedException`` onto the current generator.
        Returns:
            ``True`` if the task is still alive, ``False`` otherwise.
        """
        with QMutexLocker(self._mutex):
            if not self._generator: return False
            try:
                self._generator.throw(TaskInterruptedException)
            except (StopIteration, TaskInterruptedException):
                # If there's nothing left in our generator, the interrupt was not handled correctly
                new_state = TaskState.INTERRUPTED if self.auto_loop else TaskState.STOPPED
                self._unsafeResetGenerator(new_state=new_state)
                self.state_change_by_worker = by_worker

        return self.isAlive()

    def _unsafeGetSortKey(self):
        return self._wake_time, self._id, self._generation

    def _tryWrapFunc(self):
        """If the function isn't a generator, wraps it into a generator function"""
        func = self.func
        sig = inspect.signature(func)
        kwargs = {}

        # Check if they want the 'controller' argument
        if 'controller' in sig.parameters:
            kwargs['controller'] = self._context  # Inject the context

        if inspect.isgeneratorfunction(func):
            yield from func(**kwargs)
        else:
            func(**kwargs)
            yield

    def resetGeneratorAndGetSortKey(self, new_state: TaskState = TaskState.RUNNING, wake_time: float = None):
        """
        Creates a new generator (if new state is not stopped) and destroys the old one.
        Returns:
            The sort key
        """
        with QMutexLocker(self._mutex):
            prev_gen = self._generator
            self._unsafeResetGenerator(new_state=new_state, wake_time=wake_time)

            # Close the old generator to trigger its 'finally' cleanup blocks
            if prev_gen:
                prev_gen.close()

            return self._unsafeGetSortKey()

    def stop(self):
        self.resetGeneratorAndGetSortKey(TaskState.STOPPED)

    def restart(self, wake_time: float=None):
        """
        Kills the current instance of the task and starts a fresh one at the next work cycle.
        Args:
            wake_time: The wake time for the task to run at after restarting.
        """
        self._scheduler.moveToActiveAndReschedule(self, self.resetGeneratorAndGetSortKey(wake_time=wake_time))

    def pause(self, interrupt=False):
        """Halts the task and shifts its internal state."""
        self.state_change_by_worker = False

        target_state = TaskState.INTERRUPTED if interrupt else TaskState.PAUSED
        # If it's already interrupted, we don't need to do anything.
        # But if it's soft PAUSED, and demands an INTERRUPT, we must upgrade it.
        if self._state == target_state or self._state == TaskState.INTERRUPTED:
            return True

        self._state = target_state
        self._pause_timestamp = time.perf_counter()

        if not interrupt or self.throwInterruptedError():
            return True

        self._scheduler.logControllerAborted(self)
        return False

    def resume(self):
        """Resumes the task, calculating how long it was frozen."""
        was_hard_pause = self.isInterrupted()

        elapsed = None
        if self._scheduler.is_alive and self.isPaused():
            elapsed = time.perf_counter() - self._pause_timestamp

        self._state = TaskState.RUNNING
        self.state_change_by_worker = False
        self._pause_timestamp = 0.0

        if elapsed is not None:
            with QMutexLocker(self._mutex):
                self._generation += 1
                self._wake_time = 0 if was_hard_pause else (self._wake_time + elapsed)
                self._scheduler.moveToActiveAndReschedule(self, self._unsafeGetSortKey())

        return elapsed

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
        self._state = TaskState.RUNNING
        with QMutexLocker(self._mutex):
            self._wake_time = 0 if delay is None else (self._wake_time + delay)
            return self._wake_time, self._id, self._generation

    def _waitWhileSoftPaused(self):
        while self.isPaused() or self._scheduler.isPaused():
            # Check for Hard Pause/Stop inside the pause loop so we don't get stuck
            if not self.isAlive() or self.isInterrupted() or self._scheduler.pause_state.interrupted:
                return

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
            if self.isInterrupted() or self._scheduler.pause_state.interrupted:
                raise TaskInterruptedException("Hard Pause triggered")

            if not self.isAlive():
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
        while self.isAlive() and (self.isInterrupted() or self._scheduler.pause_state.interrupted):
            time.sleep(0.1)  # Low CPU usage wait

        # If one of the two are no longer alive, throw abort exception
        if not (self._scheduler.isRunning() and self.isAlive()):
            raise TaskAbortException("Worker stopped while waiting for resume.")

    def log(self, *args, level: LogLevel=LogLevel.INFO):
        global_logger.log(*args, level=level, task_name=self._name)

    def logError(self, error_msg, trace=""):
        global_logger.logError(error_msg, trace, self._name)

    def getVar(self, key: Hashable):
        return self._scheduler.engine.getVar(key)

    def setScheduler(self, scheduler: "TaskWorker"):
        """
        Sets the scheduler and destroys the generator forcefully if it exists.
        Args:
            scheduler: The new scheduler to assign to this controller.
        """
        assert scheduler is not None
        self._scheduler = scheduler
        self._mutex = QMutex()
        prev_gen = self._generator
        if prev_gen:
            self._generator = None
            try:
                prev_gen.close()
            except ValueError:
                global_logger.log(f"Task '{self.getName()}' caused a thread deadlock. Execution aborted without safe cleanup.", level=LogLevel.ERROR, task_name=-1)
            del prev_gen
        self._generation = -1
        self.stop()

    def __iter__(self):
        return self

    def __next__(self):
        with QMutexLocker(self._mutex):
            return next(self._generator)
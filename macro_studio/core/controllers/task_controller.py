import inspect, time
from enum import Enum, auto
from PySide6.QtCore import QMutex, QMutexLocker
from typing import TYPE_CHECKING, Generator, Hashable

from macro_studio.core.types_and_enums import TaskInterruptedException, LogLevel
from macro_studio.core.utils import global_logger
from macro_studio.api.task_context import TaskContext

if TYPE_CHECKING:
    from macro_studio.core.execution.task_worker import TaskWorker


class TaskState(Enum):
    RUNNING = auto()        # Actively executing or waiting for a wake cycle
    PAUSED = auto()         # Soft paused (frozen in place, retaining local variables)
    INTERRUPTED = auto()    # Successful hard paused (waiting for resume)
    STOPPED = auto()        # Manual kill by the user
    FINISHED = auto()       # Natural successful completion
    CRASHED = auto()        # Died from an unhandled exception

DEAD_STATES = (TaskState.STOPPED, TaskState.FINISHED, TaskState.CRASHED)

class TaskController:
    def __init__(
            self,
            worker: "TaskWorker",
            task_func,
            task_id: int,
            repeat=False,
            unique_name: str | int = None,
            is_enabled=True,
            task_args: tuple = (),  # Default to empty tuple
            task_kwargs: dict = None  # Default to None for mutable safety
    ):
        self.func = task_func
        self.repeat = repeat
        self.state_change_by_worker = False
        self.context = self._createContext()
        self.worker = worker

        self._state = TaskState.RUNNING if is_enabled else TaskState.STOPPED
        self._pause_timestamp = 0.0
        self._wake_time = 0.0
        self._is_enabled = is_enabled
        self._mutex = QMutex()
        self._id = task_id
        self._name = unique_name or task_id
        self._generator: Generator | None = None
        self._generation = 0
        self._task_args = task_args
        self._task_kwargs = task_kwargs if task_kwargs is not None else {}

    def _createContext(self):
        """
        Factory method to generate the correct API wrapper.
        Can be safely overridden by subclasses.
        """
        return TaskContext(self)

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

    def getState(self):
        return self._state

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
        return self._generator is not None and self._state not in DEAD_STATES

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
        self._generator = self._tryWrapFunc(*self._getArgsAndKwargs(self.func)) if new_state not in DEAD_STATES else None

    def throwInterruptedError(self, by_worker=False):
        """
        Safely attempts to throw a ``TaskInterruptedException`` onto the current generator.
        Returns:
            ``True`` if the task is still alive, ``False`` otherwise.
        """
        with QMutexLocker(self._mutex):
            if not self._generator: return False
            try:
                self._state = TaskState.INTERRUPTED
                self._generator.throw(TaskInterruptedException)
            except (StopIteration, TaskInterruptedException):
                # If there's nothing left in our generator, the interrupt was not handled correctly
                self._unsafeResetGenerator(new_state=TaskState.CRASHED)
            self.state_change_by_worker = by_worker
        return self.isAlive()

    def _unsafeGetSortKey(self):
        return self._wake_time, self._id, self._generation

    def _getArgsAndKwargs(self, func):
        sig = inspect.signature(func)

        # Convert the tuple to a mutable list so we can inject into it
        final_args = list(self._task_args)
        final_kwargs = dict(self._task_kwargs)

        # Intelligently inject the Context Wrapper
        if 'controller' in sig.parameters:
            params = list(sig.parameters.keys())

            # If the scriptwriter put 'controller' as the very first argument
            if params and params[0] == 'controller':
                # Shift all user args to the right by inserting at index 0
                final_args.insert(0, self.context)
            else:
                # Otherwise, safely pass it as a keyword argument
                final_kwargs['controller'] = self.context

        return func, final_args, final_kwargs

    def _tryWrapFunc(self, func, final_args, final_kwargs):
        """If the function isn't a generator, wraps it into a generator function"""
        if inspect.isgeneratorfunction(func):
            yield from func(*final_args, **final_kwargs)
        else:
            func(*final_args, **final_kwargs)
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

    def stop(self, by_worker=False, state=TaskState.STOPPED):
        self.resetGeneratorAndGetSortKey(state)
        self.state_change_by_worker = by_worker

    def restart(self, wake_time: float=None):
        """
        Kills the current instance of the task and starts a fresh one at the next work cycle.
        Args:
            wake_time: The wake time for the task to run at after restarting.
        """
        self.worker.moveToActiveAndReschedule(self, self.resetGeneratorAndGetSortKey(wake_time=wake_time))

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

        self.worker.logControllerAborted(self)
        return False

    def resume(self):
        """Resumes the task, calculating how long it was frozen."""
        was_hard_pause = self.isInterrupted()

        elapsed = None
        if self.worker.is_alive and self.isPaused():
            elapsed = time.perf_counter() - self._pause_timestamp

        self._state = TaskState.RUNNING
        self.state_change_by_worker = False
        self._pause_timestamp = 0.0

        if elapsed is not None:
            with QMutexLocker(self._mutex):
                self._generation += 1
                self._wake_time = 0 if was_hard_pause else (self._wake_time + elapsed)
                self.worker.moveToActiveAndReschedule(self, self._unsafeGetSortKey())

        return elapsed

    def getGeneration(self):
        """Atomic way to get the current generation"""
        with QMutexLocker(self._mutex):
            return self._generation

    def resumeFromWorkerPause(self, delay: float=None):
        """
        Returns:

            * The comparable variables and optionally delay the wake time.
            * If no delay is provided, resets the wake time to 0.
        """
        self._state = TaskState.RUNNING
        with QMutexLocker(self._mutex):
            self._wake_time = 0 if delay is None else (self._wake_time + delay)
            return self._wake_time, self._id, self._generation

    def log(self, *args, level: LogLevel=LogLevel.INFO):
        global_logger.log(*args, level=level, task_name=self._name)

    def logError(self, error_msg, include_trace=True):
        global_logger.logError(error_msg, include_trace, self._name)

    def getVar(self, key: Hashable):
        return self.worker.engine.getVar(key)

    def setScheduler(self, scheduler: "TaskWorker"):
        """
        Sets the scheduler and destroys the generator forcefully if it exists.
        Args:
            scheduler: The new scheduler to assign to this controller.
        """
        assert scheduler is not None
        self.worker = scheduler
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
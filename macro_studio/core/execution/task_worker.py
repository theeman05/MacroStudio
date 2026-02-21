import time, heapq
from PySide6.QtCore import QThread, QMutex, QMutexLocker, Signal
from typing import TYPE_CHECKING, List

from macro_studio.core.types_and_enums import LogLevel
from macro_studio.core.utils import global_logger
from macro_studio.core.execution.pause_state import PauseState
from macro_studio.core.controllers.task_controller import TaskController, TaskState

if TYPE_CHECKING:
    from macro_studio.core.execution.engine import MacroStudio


def _handleTasksOnHard(controller: "TaskController", notified_tasks: set):
    """
    Handles any tasks that have not been notified of a hard pause yet.
    Returns:
        ``True`` if the task is now hard paused, ``False`` otherwise
    """
    was_in_notified = controller in notified_tasks
    notified_tasks.add(controller)
    if not controller.isInterrupted():
        # Throw if not in notified already
        return was_in_notified or controller.throwInterruptedError(True)
    return controller.isAlive()

class TaskWorker(QThread):
    finished_signal = Signal()

    def __init__(self, engine: "MacroStudio", loop_delay: float):
        super().__init__()
        self.pause_state = PauseState()
        self.is_alive = False
        self.engine = engine
        self.loop_delay = loop_delay
        self.last_heartbeat = 0

        self._mutex = QMutex()
        self._task_heap = []
        self._paused_tasks: set[TaskController] = set()

    def _unsafePushController(self, controller: TaskController, wake_time, cid, generation):
        """
        Pushes a controller to the task heap. Assumes we're locked already and the worker is active.
        If wake_time is None, replaces the remaining variables.
        """
        heapq.heappush(self._task_heap, (wake_time, cid, generation, controller))

    def reloadControllers(self, controllers: List[TaskController]=None):
        """
        Replaces the entire task list in one go.
        Args:
            controllers: The controllers to add into the heap. If ``None``, stops the previous controllers.
        """
        with QMutexLocker(self._mutex):
            prev_heap = self._task_heap
            self._task_heap = []
            if controllers:
                # We don't use controller.restart here because that attempts to capture work mutex again.
                for controller in controllers:
                    self._unsafePushController(controller, *controller.resetGeneratorAndGetSortKey())
            else:
                # Cleanup previous tasks that were going to run because we're stopping
                for entry in prev_heap:
                    entry[3].stop(True)

    def moveToActiveAndReschedule(self, controller: TaskController, sort_key):
        """Wakes a controller up and puts it back in the schedule."""
        with QMutexLocker(self._mutex):
            if not self.is_alive: return
            # Schedule only if we're not paused
            if not self.pause_state.active:
                self._paused_tasks.discard(controller)
                self._unsafePushController(controller, *sort_key)
            else:
                # If we're paused, add it to paused list so it will fire up when we resume
                self._paused_tasks.add(controller)

    def _unsafeMoveToPaused(self, controller: TaskController):
        """Moves the controller to paused task list if it's not already there. Assumes we're locked already."""
        if not controller in self._paused_tasks:
            self._paused_tasks.add(controller)

    def _handleInterruptedEnd(self):
        # If our pause state is hard before stopping, we need to send our exception to all
        # tasks that were going to run, or aren't hard paused already.
        notified_tasks = set()
        forcefully_stopped = set()
        stopped_all = False
        with QMutexLocker(self._mutex):
            # Snapshot the collections to protect if a task removes itself from the list/set during the 'throw'
            active_snapshot = list(self._task_heap)
            paused_snapshot = list(self._paused_tasks)
            self._task_heap.clear()  # Clear task heap because hard pause means things resume at their next cycle
            # Controllers in the active snapshot should be added to paused and handled
            for entry in active_snapshot:
                controller = entry[3]
                # Only add to paused when hard pausing successful
                if _handleTasksOnHard(controller, notified_tasks):
                    self._paused_tasks.add(controller)
                else:
                    forcefully_stopped.add(controller)

            # All tasks must have been stopped when hard stopping
            if not self._paused_tasks:
                stopped_all = True

        if not stopped_all:
            # Handle previously paused tasks
            for controller in paused_snapshot:
                _handleTasksOnHard(controller, notified_tasks)

            # Log any forcefully stopped tasks
            for controller in forcefully_stopped:
                self.logControllerAborted(controller)
        else:
            self.is_alive = False
            self.pause_state.clear()
            global_logger.log("System terminated all active tasks during interrupting pause.", level=LogLevel.WARN)

    def handleStoppedEnd(self):
        with QMutexLocker(self._mutex):
            paused_snapshot = list(self._paused_tasks)
            self._task_heap.clear()
            self._paused_tasks.clear()

        for controller in paused_snapshot:
            controller.stop(by_worker=True)

    def _onRunEnd(self):
        # Handle when run loop ends
        if self.pause_state.interrupted:
            self._handleInterruptedEnd()
        elif not self.is_alive:
            self.handleStoppedEnd()

    def run(self):
        completed = False
        while self.is_alive and not self.isPaused():
            self.last_heartbeat = time.perf_counter()

            should_sleep = True
            delay_ms = 10

            with QMutexLocker(self._mutex):
                task_heap = self._task_heap
                if not self.is_alive or self.isPaused():
                    break
                if task_heap:
                    current_time = time.perf_counter()
                    wake_time, cid, prev_gen, controller = task_heap[0]
                    controller_paused = controller.isPaused()
                    # Only check generations while the controller is not paused
                    should_continue = controller_paused or prev_gen != controller.getGeneration()
                    if wake_time <= current_time or should_continue:
                        wake_time, cid, generation, controller = heapq.heappop(task_heap)
                        # If generations differ or controller paused, move to next and discard current
                        if should_continue:
                            if controller_paused: self._unsafeMoveToPaused(controller)
                            continue
                        should_sleep = False
                    else:
                        # WAIT: Calculate dynamic delay
                        delay_sec = wake_time - current_time
                        delay_ms = int(max(1, min(delay_sec * 1000, 50)))
                elif self._paused_tasks:
                    # Garbage Collection: Find tasks that were STOPPED by the user while paused
                    dead_tasks = [c for c in self._paused_tasks if not c.isPaused()]

                    for dead_task in dead_tasks:
                        self._paused_tasks.remove(dead_task)

                    # Lifecycle Check: Are there STILL valid paused tasks waiting?
                    if self._paused_tasks:
                        # DO NOT EXIT! Just sleep and wait for the UI to call resume()
                        delay_ms = 50
                    else:
                        # The heap is empty AND the paused set is empty.
                        completed = True
                else:
                    completed = True

            if completed:
                self.finished_signal.emit()
                return
            elif self.isPaused():
                # Safety check if inside the mutex took a while
                break

            if not should_sleep:
                try:
                    # Run the task using next
                    wait_duration = next(controller)
                    if wait_duration is None: wait_duration = 0
                    new_wake_time = current_time + float(wait_duration)
                    # Schedule it to run at the new time
                    controller.wake_time = new_wake_time
                    # Grab the lock again and push the controller
                    with QMutexLocker(self._mutex):
                        self._unsafePushController(controller, wake_time=new_wake_time, cid=cid, generation=generation)
                except StopIteration:
                    # Controller completed all steps
                    if controller.repeat:
                        # Throttle controller by adding slight delay before restarting
                        controller.restart(time.perf_counter() + self.loop_delay)
                    else:
                        controller.stop(state=TaskState.FINISHED)
                except Exception as e:
                    controller.stop(state=TaskState.CRASHED)
                    controller.logError(f"{str(e)}")
            else:
                self.msleep(delay_ms)

        self._onRunEnd()

    def resume(self):
        """
        If the worker is running, attempts to resume the worker.
        Returns:
            The duration paused for in seconds or ``None`` if not paused.
        """
        was_hard_pause = self.pause_state.interrupted
        elapsed = self.pause_state.clear() if (self.is_alive and not self.isRunning()) else None
        if elapsed is not None:
            elapsed_on_soft = elapsed if was_hard_pause is False else None
            with QMutexLocker(self._mutex):
                # Snapshot paused tasks because we're going to iterate them.
                paused_snapshot = list(self._paused_tasks)
                # Reset the task heap
                self._task_heap = []
                for controller in paused_snapshot:
                    # Only unpause controllers that are paused by the worker, or not paused at all
                    if controller.state_change_by_worker or not controller.isPaused():
                        self._paused_tasks.remove(controller)
                        if controller.isAlive():
                            # Only push living controllers
                            self._unsafePushController(controller, *controller.resumeFromWorkerPause(elapsed_on_soft))

        self.start()
        return elapsed

    def isPaused(self):
        return self.pause_state.active

    @staticmethod
    def logControllerAborted(controller: "TaskController"):
        global_logger.log(f"Task {controller.name} aborted via unhandled Hard Stop.", level=LogLevel.WARN)
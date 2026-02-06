import time, heapq, traceback
from PySide6.QtCore import QThread, QMutex, QMutexLocker, Signal
from typing import TYPE_CHECKING, List

from .types_and_enums import LogLevel, LogPacket, LogErrorPacket
from .pause_state import PauseState

if TYPE_CHECKING:
    from .task_controller import TaskController


def _handleTasksOnHard(controller: "TaskController", notified_tasks: set):
    """
    Handles any tasks that have not been notified of a hard pause yet.
    Returns:
        ``True`` if the task is now hard paused, ``False`` otherwise
    """
    was_in_notified = controller in notified_tasks
    notified_tasks.add(controller)
    if not controller.pause_state.is_hard:
        # Throw if not in notified already
        return was_in_notified or controller.throwHardPauseError()
    return False

class MacroWorker(QThread):
    finished_signal = Signal()
    log_signal = Signal(object) # The log message

    def __init__(self):
        super().__init__()
        self.pause_state = PauseState()
        self.running = False

        self._mutex = QMutex()
        self._task_heap = []
        self._paused_tasks = set()

    def _unsafePushController(self, controller: "TaskController", wake_time, cid, generation):
        """
        Pushes a controller to the task heap. Assumes we're locked already and the worker is active.
        If wake_time is None, replaces the remaining variables.
        """
        heapq.heappush(self._task_heap, (wake_time, cid, generation, controller))

    def reloadControllers(self, controllers: List["TaskController"]=None):
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
                    self._unsafePushController(controller, *controller.resetGeneratorAndGetSorKey())
            else:
                # Cleanup previous tasks that were going to run because we're stopping
                for entry in prev_heap:
                    entry[3].stop()

    def moveToActiveAndReschedule(self, controller: "TaskController", wake_time, cid, generation):
        """Wakes a controller up and puts it back in the schedule."""
        with QMutexLocker(self._mutex):
            if controller in self._paused_tasks:
                self._paused_tasks.remove(controller)

            # Schedule only if we're not paused
            if not self.pause_state.active:
                self._unsafePushController(controller, wake_time=wake_time, cid=cid, generation=generation)

    def _unsafeMoveToPaused(self, controller: "TaskController"):
        """Moves the controller to paused task list if it's not already there. Assumes we're locked already."""
        if not controller in self._paused_tasks:
            self._paused_tasks.add(controller)

    def _onRunEnd(self):
        # Handle when run loop ends due to pausing or stopping.
        if self.pause_state.is_hard:
            # If our pause state is hard before stopping, we need to send our exception to all
            # tasks that were going to run, or aren't hard paused already.
            notified_tasks = set()
            forcefully_stopped = set()
            with QMutexLocker(self._mutex):
                # Snapshot the collections to protect if a task removes itself from the list/set during the 'throw'
                active_snapshot = list(self._task_heap)
                paused_snapshot = list(self._paused_tasks)
                self._task_heap.clear() # Clear task heap because hard pause means things resume at their next cycle

                # Controllers in the active snapshot should be added to paused and handled
                for entry in active_snapshot:
                    controller = entry[3]
                    # Only add to paused when hard pausing successful
                    if _handleTasksOnHard(controller, notified_tasks):
                        self._paused_tasks.add(controller)
                    else:
                        forcefully_stopped.add(controller)

                if not self._paused_tasks:
                    # All tasks must have been stopped when hard stopping, reset state
                    self.running = False
                    self.pause_state.clear()

            if self.running:
                # Handle previously paused tasks
                for controller in paused_snapshot:
                    _handleTasksOnHard(controller, notified_tasks)

                # Log any forcefully stopped tasks
                for controller in forcefully_stopped:
                    self.logControllerAborted(controller)
            else:
                self.log("System terminated all active tasks during hard pause.", level=LogLevel.WARN)


    def run(self):
        completed = False
        while self.running and not self.isPaused():
            should_sleep = True
            delay_ms = 10

            with QMutexLocker(self._mutex):
                task_heap = self._task_heap
                if not self.running or self.isPaused():
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
                    # Controller stopped successfully
                    controller.stop()
                    self.log(f"Task {controller.cid} finished.")
                except Exception as e:
                    controller.stop()
                    self.logError(f"{str(e)}", trace=traceback.format_exc(), task_id=controller.cid)
            else:
                self.msleep(delay_ms)

        self._onRunEnd()

    def resume(self):
        """
        If the worker is running, attempts to resume the worker.
        Returns:
            The duration paused for in seconds or ``None`` if not paused.
        """
        was_hard_pause = self.pause_state.is_hard
        elapsed = self.pause_state.clear() if (self.running and not self.isRunning()) else None
        if elapsed is not None:
            elapsed_on_soft = elapsed if was_hard_pause is False else None
            with QMutexLocker(self._mutex):
                # Snapshot paused tasks because we're going to iterate them.
                paused_snapshot = list(self._paused_tasks)
                # Reset the task heap
                self._task_heap = []
                for controller in paused_snapshot:
                    # Only unpause controllers that aren't manually paused
                    if not controller.pause_state.active:
                        self._paused_tasks.remove(controller)
                        self._unsafePushController(controller, *controller.delayAndGetSortKey(elapsed_on_soft))

        self.start()
        return elapsed

    def isPaused(self):
        return self.pause_state.active

    def pause(self, hard: bool):
        """
        Pauses all task execution.
        Args:
            hard: Controls how the pause is handled.

                * ``True``: Interrupts the task to **release keys** and **clean up resources** safely.
                * ``False``: **Freezes** the task in place (keys remain held down).
         Returns:
             ``True`` if paused successfully, ``False`` if the engine has stopped abruptly.
        """
        if self.running and not self.isPaused():
            self.pause_state.trigger(hard)
            # Wait for loop to exit
            self.wait()
            return self.running
        return True

    def stop(self):
        self.running = False
        self.pause_state.clear()
        self.wait()
        self.reloadControllers(None)

    def log(self, *args, level: LogLevel=LogLevel.INFO, task_id: int=-1):
        """
        Sends a structured log packet to the ui.
        Args:
            args: The objects to be printed in the log. If mode is not ERROR, will cast the args automatically.
            level: The log level to display at.
            task_id: The task id associated with the packet.
        """
        payload = LogPacket(parts=args, level=level, task_id=task_id)
        self.log_signal.emit(payload)

    def logError(self, error_msg, trace="", task_id: int=-1):
        """Sends a specialized LogErrorPacket object to the ui."""
        payload = LogErrorPacket(message=error_msg, traceback=trace, task_id=task_id)
        self.log_signal.emit(payload)

    def logControllerAborted(self, controller: "TaskController"):
        self.log(f"Task {controller.cid} aborted via unhandled Hard Stop.", level=LogLevel.WARN)
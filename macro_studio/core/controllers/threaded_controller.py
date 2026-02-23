import time, threading

from macro_studio.core.types_and_enums import TaskInterruptedException, TaskAbortException
from macro_studio.api.thread_context import ThreadContext
from macro_studio.actions import taskSleep, taskWaitForResume
from .task_controller import TaskController, TaskState


class ThreadedController(TaskController):
    def __init__(
            self,
            scheduler,
            task_func,
            task_id: int,
            repeat=False,
            unique_name: str | int = None,
            is_enabled=True,
            task_args: tuple = (),  # Default to empty tuple
            task_kwargs: dict = None  # Default to None for mutable safety
    ):
        super().__init__(scheduler, task_func, task_id, repeat, unique_name, is_enabled, task_args, task_kwargs)

        self._os_thread = None
        self._resume_event = threading.Event()
        self._resume_event.set()

    def _createContext(self):
        return ThreadContext(self)

    def _unsafeResetGenerator(self, new_state: TaskState, wake_time: float=None):
        is_pause = new_state in (TaskState.PAUSED, TaskState.INTERRUPTED)
        if is_pause: self._resume_event.clear()
        super()._unsafeResetGenerator(new_state=new_state, wake_time=wake_time)
        if not is_pause: self._resume_event.set()

    def _tryWrapFunc(self, func, final_args, final_kwargs):
        """
        THE BRIDGE: Runs on the main worker thread.
        Spawns the OS thread and yields control back to the TaskWorker heap
        while polling the thread's health.
        """
        self._resume_event.set()
        def thread_target():
            """The actual code running inside the OS thread."""
            try:
                func(*final_args, **final_kwargs)
            except TaskAbortException:
                # The user or engine intentionally stopped the task. This is normal!
                pass
            except TaskInterruptedException:
                # The user didn't handle the interrupt, log the aborted controller
                self.worker.logControllerAborted(self)
                self._state = TaskState.CRASHED
            except Exception as e:
                self._state = TaskState.CRASHED
                self.logError(f"{str(e)}")

        # Spawn the thread
        self._os_thread = threading.Thread(target=thread_target, daemon=True)
        self._os_thread.start()
        # Generator Polling Loop (Runs on the Worker Thread)
        while self._os_thread.is_alive():
            # If the OS thread crashed, pull the exception up into the main engine!
            if self._state == TaskState.CRASHED:
                self.stop(state=TaskState.CRASHED)
                break

            try:
                # Short sleep to yield control back to the engine worker
                yield from taskSleep(0.05)
            except TaskInterruptedException:
                # The Engine is Hard Paused.
                # The THREAD should handle its own pausing via controller.sleep(),
                # but WE (the monitor) must sit here and wait for the resume signal.
                yield from taskWaitForResume()

    def pause(self, interrupt=False):
        self._resume_event.clear()
        return super().pause(interrupt=interrupt)

    def resume(self):
        elapsed = super().resume()
        if elapsed is not None:
            self._resume_event.set()
        return elapsed

    def resumeFromWorkerPause(self, delay: float=None):
        key = super().resumeFromWorkerPause(delay=delay)
        self._resume_event.set()
        return key

    def sleep(self, duration: float = .01):
        """
        Blocks the current thread with high precision.
        Args:
            duration: Duration to sleep the thread for in seconds.
        Raises:
            TaskAbortException: If stopped while sleeping.
        """
        if duration <= 0:
            return

        start_time = time.perf_counter()
        target_time = start_time + duration

        while True:
            # Check for Death
            if not self.isAlive():
                raise TaskAbortException("Task stopped.")

            # Check for interrupt
            if self.isInterrupted() or self.worker.isInterrupted():
                self._resume_event.clear()
                raise TaskInterruptedException("Hard pause triggered!")

            # Check for Pause
            if not self._resume_event.is_set():
                # FREEZE TIME: Calculate how much time was left
                remaining_at_pause = target_time - time.perf_counter()

                # Wait while we're paused
                self._resume_event.wait()

                target_time = time.perf_counter() + remaining_at_pause

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
        self._resume_event.wait()

        # If one of the two are no longer alive, throw abort exception
        if not (self.worker.isAlive() and self.isAlive()):
            raise TaskAbortException("Worker stopped while waiting for resume.")
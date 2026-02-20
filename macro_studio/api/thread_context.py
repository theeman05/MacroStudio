from typing import TYPE_CHECKING
from .task_context import TaskContext

if TYPE_CHECKING:
    from macro_studio.core.controllers.threaded_controller import ThreadedController

class ThreadContext(TaskContext):
    _controller: "ThreadedController"

    def sleep(self, duration: float = 0.01):
        """
        Blocks the current thread with high precision.
        Args:
            duration: Duration to sleep the thread for in seconds.
        Raises:
            TaskAbortException: If stopped while sleeping.
            TaskInterruptedException: If interrupted while sleeping.
        """
        self._controller.sleep(duration)

    def waitForResume(self):
        """
        Blocks the thread **ONLY** if the system or this task is in an interrupted pause.
        If the task is just 'Soft Paused' (logic wait), this returns immediately.
        Raises:
            TaskAbortException: If stopped while waiting.
        """
        self._controller.waitForResume()
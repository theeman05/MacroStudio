import time
from PyQt6.QtCore import QThread, pyqtSignal


class MacroWorker(QThread):
    finished_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = True
        self.paused = False
        self._task_heap = []

    def run(self):
        while self.running:
            if not self.paused and self._task_heap:
                # Peek at the next task time
                next_event_time = self._task_heap[0][0].wake_time
                delay_sec = next_event_time - time.time()
            else:
                # Fallback poll rate when paused or empty
                delay_sec = 0.01

            # Clamp logic (Min 1ms, Max 50ms)
            delay_ms = int(max(1, min(delay_sec * 1000, 50)))

            self.msleep(delay_ms)

            if not self.paused:
                self.process_pending_tasks()

        # Emit upon exiting the loop
        self.finished_signal.emit()

    def process_pending_tasks(self):
        # Your heap pop/execute logic here...
        # If you need to click, you can do it here.
        # If you need to update UI, EMIT A SIGNAL:
        # self.log_signal.emit("Clicked button A")
        pass

    def stop(self):
        """Safe way to kill the loop"""
        self.running = False
        self.wait()
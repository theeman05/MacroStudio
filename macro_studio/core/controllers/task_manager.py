import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QMessageBox

from macro_studio.core.execution.manual_task_wrapper import ManualTaskWrapper
from macro_studio.core.execution.task_worker import TaskWorker
from macro_studio.core.types_and_enums import LogLevel
from macro_studio.core.utils import global_logger
from .task_controller import TaskController
from .threaded_controller import ThreadedController

if TYPE_CHECKING:
    from macro_studio.core.data import Profile, TaskModel

DEADLOCK_TIME_MS = 200
WORKER_MONITOR_RATE_MS = 2000
PULSE_DEADLOCK_DURATION_S = 5.0

class ManualTaskController(TaskController):
    def __init__(self, worker, var_store, task_model: "TaskModel", cid: int):
        self._wrapper = ManualTaskWrapper(var_store, task_model)
        super().__init__(worker=worker,
                         task_func=self._wrapper.runTask,
                         task_id=cid,
                         unique_name=task_model.name,
                         auto_loop=task_model.auto_loop)

    def updateModel(self, task_model: "TaskModel"):
        self._wrapper.updateModel(task_model)

    def resetGeneratorAndGetSortKey(self, *args, **kwargs):
        results = super().resetGeneratorAndGetSortKey(**kwargs)
        self._wrapper.resetState()
        return results

class TaskManager(QObject):
    finished_signal = Signal()
    def __init__(self, engine, profile: "Profile"):
        super().__init__()

        self.engine = engine
        self.profile = profile
        self.controllers: dict[str | int, TaskController] = {}
        self.next_cid = 0
        self._loop_delay = 0.001
        self.worker = self._createAndMonitorWorker()

        self.watchdog_timer = QTimer()

        tasks = profile.tasks
        tasks.taskAdded.connect(self._onManualTaskAdded)
        tasks.taskRemoved.connect(self._onManualTaskRemoved)
        tasks.taskSaved.connect(self._onManualTaskSaved)
        tasks.taskLoopChanged.connect(self._onManualTaskLoopChange)
        self.watchdog_timer.timeout.connect(self._checkWorkerHealth)

        self._onProfileLoaded()

    @property
    def loop_delay(self):
        return self.loop_delay

    @loop_delay.setter
    def loop_delay(self, delay: float):
        self.loop_delay = delay
        self.worker.loop_delay = delay

    def createController(self, task_func, enabled: bool, auto_loop: bool, task_args, task_kwargs):
        c_id = self.next_cid
        controller = TaskController(self.worker, task_func, c_id, is_enabled=enabled, auto_loop=auto_loop, task_args=task_args, task_kwargs=task_kwargs)
        self._registerController(controller)
        return controller.context

    def createThreadController(self, fun_in_thread, enabled: bool, auto_loop: bool, args, kwargs):
        c_id = self.next_cid
        controller = ThreadedController(self.worker, fun_in_thread, c_id, is_enabled=enabled, auto_loop=auto_loop, task_args=task_args, task_kwargs=task_kwargs)
        self._registerController(controller)
        return controller.context

    def startWorker(self):
        self.worker.pause_state.clear()
        self.worker.is_alive = True
        self.worker.reloadControllers(self._getEnabledControllers())
        global_logger.log("Starting Macro...")
        self.worker.start()
        self.watchdog_timer.start(WORKER_MONITOR_RATE_MS)

    def stopWorker(self):
        self.worker.is_alive = False
        self.worker.pause_state.clear()
        self.watchdog_timer.stop()
        return self._tryShowKillDialog()

    def pauseWorker(self, interrupt):
        """
        Pauses all task execution.
        Args:
            interrupt: Controls how the pause is handled.

                * ``True``: Interrupts the task to **release keys** and **clean up resources** safely.
                * ``False``: **Freezes** the task in place (keys remain held down).
         Returns:
             ``True`` if paused successfully, ``False`` if could not stop the worker.
        """
        if self.worker.is_alive and not self.worker.isPaused():
            self.watchdog_timer.stop()
            self.worker.pause_state.trigger(interrupt)
            return self._tryShowKillDialog(True)
        return True

    def resumeWorker(self):
        elapsed = self.worker.resume() if self.worker.is_alive else None
        if elapsed is not None: self.watchdog_timer.start(WORKER_MONITOR_RATE_MS)
        return elapsed

    def _checkWorkerHealth(self):
        if not self.worker.isRunning() or self.worker.isPaused():
            return

        current_time = time.perf_counter()
        time_since_last_pulse = current_time - self.worker.last_heartbeat

        if time_since_last_pulse > PULSE_DEADLOCK_DURATION_S:
            global_logger.log(f"Engine Auto-Protect: A task has held the worker for {time_since_last_pulse:.2f} seconds without yielding.", level=LogLevel.WARN)
            # Try to pause the worker so the deadlock thing will come up
            if self.pauseWorker(False):
                if self.worker.is_alive: # Somehow the task pulled through, clear the pause
                    self.worker.pause_state.clear()
                else:
                    self.engine.cancelMacroExecution()

    def _createAndMonitorWorker(self):
        worker = TaskWorker(self.engine, self._loop_delay)
        for controller in self.controllers.values():
            controller.setScheduler(worker)
        worker.finished_signal.connect(self.finished_signal.emit)
        return worker

    def _tryShowKillDialog(self, is_pause=False):
        if not self.worker.wait(DEADLOCK_TIME_MS):
            msg_box = QMessageBox(self.engine.ui)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Potential Task Deadlock Detected")
            msg_box.setText("The task worker is completely unresponsive.")
            msg_box.setInformativeText(f"A task has not yielded for longer than {DEADLOCK_TIME_MS}ms, halting task execution. Do you want to forcefully terminate the worker, or let it continue running?")

            terminate_btn = msg_box.addButton("Force Terminate", QMessageBox.ButtonRole.DestructiveRole)
            _continue_btn = msg_box.addButton("Let it Continue", QMessageBox.ButtonRole.RejectRole)

            msg_box.exec()

            if msg_box.clickedButton() == terminate_btn:
                global_logger.log("User forcefully terminated the worker.", level=LogLevel.ERROR)
                self.worker.terminate()  # The Nuclear Option
                self.worker.wait()  # Wait for the OS to finish burying it
                del self.worker
                self.worker = self._createAndMonitorWorker()
            else:
                self.worker.is_alive = True
                self.worker.pause_state.clear()
                global_logger.log("User chose to let the deadlocked task continue. Watchdog disabled for the remainder of this run", level=LogLevel.WARN)
                return False # We walk away and let it keep spinning
        elif not is_pause:
            # The worker shut down naturally and safely within the timeframe!
            self.worker.reloadControllers(None)
        return True

    def _getEnabledControllers(self):
        return [controller for controller in self.controllers.values() if controller.isEnabled()]

    def _onProfileLoaded(self):
        for cid in self.controllers:
            if isinstance(cid, str): self._onManualTaskRemoved(cid)

        for task_model in self.profile.tasks:
            self._onManualTaskAdded(task_model)

    def _registerController(self, controller: TaskController):
        self.next_cid += 1
        self.controllers[controller.getName()] = controller

    def _onManualTaskAdded(self, task_model: "TaskModel"):
        self._registerController(ManualTaskController(self.worker, self.profile.vars, task_model, self.next_cid))

    def _onManualTaskRemoved(self, task_name: str):
        if task_name in self.controllers:
            controller = self.controllers.pop(task_name)
            controller.stop()
            del controller

    def _onManualTaskSaved(self, task_model: "TaskModel"):
        controller = self.controllers.get(task_model.name)
        if isinstance(controller, ManualTaskController):
            controller.updateModel(task_model)
        elif controller is None:
            print(f"Warning: Tried to save '{task_model.name}', but no controller was found in the registry.")
        else:
            print(f"Warning: '{task_model.name}' is a {type(controller).__name__}, not a ManualTaskController.")

    def _onManualTaskLoopChange(self, task_name, auto_loop):
        controller = self.controllers.get(task_name)
        if controller:
            controller.auto_loop = auto_loop
        else:
            print(f"Warning: Tried to save '{task_name}', but no controller was found in the registry.")
import ctypes, sys, time, inspect, heapq
import tkinter as tk
from collections import OrderedDict
from pynput import mouse, keyboard
from enum import Enum
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QPainter, QPen, QColor
from pynput.keyboard import Key
from dataclasses import dataclass
from typing import Hashable, TypeAlias, Callable, List, Generator, Dict

class ClickMode(Enum):
    IDLE = 0
    SET_BUTTON = 1
    SET_BOUNDS = 2

class TransparentOverlay(QWidget):
    def __init__(self):
        self.q_app = QApplication(sys.argv)
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # Prevents it from showing in the taskbar
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, 2560, 1440)  # Set to screen resolution
        self.show()
        self.set_click_through(True)
        self.render_geometry: dict | None = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(255, 0, 0, 180), 5)
        painter.setPen(pen)

        render_geom_dict = self.render_geometry
        if render_geom_dict:
            for obj in render_geom_dict.values():
                if isinstance(obj, QPoint):
                    painter.drawEllipse(obj, 10, 10)
                elif isinstance(obj, QRect):
                    painter.drawRect(obj)
                else:
                    print(f'UNEXPECTED OBJECT {type(obj)} FOUND')

    def set_click_through(self, enable: bool):
        hwnd = self.winId().__int__()
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)

        if enable:
            new_style = ex_style | 0x80000 | 0x20  # WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            new_style = ex_style & ~0x20  # Remove WS_EX_TRANSPARENT, but keep WS_EX_LAYERED

        ctypes.windll.user32.SetWindowLongW(hwnd, -20, new_style)

    def destroy(self, destroyWindow: bool = True, destroySubWindows: bool = True):
        self.q_app.exit()
        super().destroy(destroyWindow, destroySubWindows)

class TKApp:
    def __init__(self, macro_creator, root):
        self.root = root
        self.root.title("Macro Thing")
        self.root.attributes("-topmost", True)

        self.macro_creator: MacroCreator = macro_creator

        tk.Label(root, text="Enter Min Threshold & Phrase:").pack(pady=(10, 0))
        self.phrase_entry = tk.Entry(root, width=40)
        self.phrase_entry.pack(pady=(0, 10))

        self.select_button = tk.Button(root, text="Begin Setup", command=self.beginSetup)
        self.select_button.pack(pady=5)

        self.run_button = tk.Button(root, text="Run", command=self.toggleRun)
        self.run_button.pack(pady=5)

        self.debug_var = tk.StringVar()

        tk.Label(root, textvariable=self.debug_var).pack(pady=5)

        self.overlayWidget = TransparentOverlay()
        self.setup_handler: _SetupHandler | None = None

        def onPress(key: Key):
            if key == Key.esc:
                setup_handler = self.setup_handler
                if self.macro_creator.isRunningMacros():
                    self.toggleRun(False)
                    self.debug_var.set("ESC Pressed. Stopped run")
                elif setup_handler:
                    self.setup_handler = None
                    setup_handler.exit()
                    self.updateOverlay()
                    self.macro_creator.finishSetup()
                    self.select_button.config(text="Begin Setup")
                    self.debug_var.set("ESC Pressed. Stopped setup")
        keyboard.Listener(on_press=onPress, daemon=True).start()

    def beginSetup(self):
        if self.setup_handler:
            self.setup_handler.exit()

        self.updateOverlay()
        self.setup_handler = _SetupHandler(self.macro_creator.setup_steps, self)

    def updateOverlay(self, render_geometry = None):
        self.overlayWidget.render_geometry = render_geometry
        self.overlayWidget.update()

    def finishSetup(self, setup_results):
        self.setup_handler = None
        self.select_button.config(text="Re-Setup")
        self.debug_var.set("Setup completed, select 'Run' to execute macro")
        self.macro_creator.finishSetup(setup_results)

    def toggleRun(self, should_run = None):
        was_running = self.macro_creator.isRunningMacros()
        should_run = not was_running if should_run is None else should_run
        self.run_button.config(text="Stop" if should_run else "Run")
        if should_run:
            self.debug_var.set("Executing macro")
            self.macro_creator.startMacroExecution()
        elif was_running:
            self.debug_var.set("Macro stopped")
            self.macro_creator.cancelMacroExecution()

    def cleanup(self):
        if self.setup_handler:
            self.setup_handler.exit()
        self.overlayWidget.destroy()

@dataclass
class SetupStep:
    display_str: str
    click_mode: ClickMode

MacroSteps: TypeAlias = OrderedDict[Hashable, SetupStep]

class MacroAbortException(Exception):
    """Exception raised when a macro is stopped by the user or system."""
    def __init__(self, message="Macro execution was aborted"):
        self.message = message
        super().__init__(self.message)

def macroWait(duration: float):
    """
    Yields control back to the scheduler for 'duration' seconds.
    Call "yield from" on this method to yield correctly
    Usage in task: yield from self.macroWait(2.0)
    """
    yield duration

def _wrapStandardFun(func):
    """
    Turns a normal function into a generator function
    """
    func()
    yield

class MacroCreator:
    def __init__(self):
        self.setup_steps = OrderedDict()
        self._run_tasks: List[Callable[[], Generator | None]] = []  # List of generator functions
        self._task_heap = []
        self.setup_vars: Dict[Hashable, QRect | QPoint] = {}
        self._root_tk = tk.Tk()
        self._tk_app = TKApp(self, self._root_tk)
        self._is_running = False

    def addSetupStep(self, key: Hashable, mode: ClickMode, display_str: str):
        self.setup_steps[key] = SetupStep(display_str, mode)

    def finishSetup(self, setup_vars=None):
        if setup_vars:
            self.setup_vars = setup_vars
        else:
            self.setup_vars.clear()

    def addRunTask(self, task_func: Callable[[], Generator | None]):
        self._run_tasks.append(task_func)

    def isRunningMacros(self):
        return self._is_running

    def startMacroExecution(self):
        if self._is_running: return
        self._is_running = True
        for task_func in self._run_tasks:
            if inspect.isgeneratorfunction(task_func):
                gen = task_func()
            else:
                gen = _wrapStandardFun(task_func)

            # Push to heap: (Time, ID, Generator)
            # We use id(gen) as a tie-breaker so Python doesn't compare generators
            heapq.heappush(self._task_heap, (0, id(gen), gen))

            self._runScheduler()

    def cancelMacroExecution(self):
        if not self._is_running: return
        self._is_running = False
        self._task_heap = []

    def _runScheduler(self):
        """
        The heartbeat of the macro. It checks active tasks, runs them if
        their wait time is over, and schedules the next check.
        """
        if not self._is_running:
            return

        current_time = time.time()
        # Process all tasks that are ready 'right now'
        while self._task_heap:
            # 1. Peek at the earliest task (Index 0 is always smallest)
            wake_time, _, _ = self._task_heap[0]

            # 2. If the earliest task is in the future, we are done for this tick.
            if wake_time > current_time:
                break

            # 3. Pop the task (Remove it from heap to run it)
            _, gen_id, gen = heapq.heappop(self._task_heap)

            try:
                # 4. Run the task
                wait_duration = next(gen)
                if wait_duration is None: wait_duration = 0

                # 5. Push it back with new time
                next_wake = current_time + float(wait_duration)
                heapq.heappush(self._task_heap, (next_wake, gen_id, gen))
            except StopIteration:
                pass  # Task finished, don't push back
            except Exception as e:
                print(f"Error: {e}")
                self.cancelMacroExecution()
                return

        if self._task_heap:
            next_event_time = self._task_heap[0][0]
            delay_sec = next_event_time - time.time()

            # Convert to ms, ensure at least 1ms, max 50ms
            delay_ms = int(max(1, min(delay_sec * 1000, 50)))

            # Schedule next tick, but clamp it to 50ms max so we can cancel properly
            self._root_tk.after(delay_ms, self._runScheduler)
        else:
            self._tk_app.debug_var.set("Macro completed successfully")
            self.cancelMacroExecution()
            self._tk_app.toggleRun(False)

    def mainLoop(self):
        try:
            self._root_tk.mainloop()
        except KeyboardInterrupt:
            pass

        self.cancelMacroExecution()
        self._tk_app.cleanup()

class _SetupHandler:
    def __init__(self, setup_steps: MacroSteps, tk_app: TKApp):
        self._tk_app = tk_app
        self._click_mode = ClickMode.IDLE
        self._rect_start: QPoint | None = None
        self._mouse_listener = mouse_listener = mouse.Listener(on_click=lambda x,y,_,pressed: self._onClick(x, y, pressed), on_move=lambda x,y: self._onMove(x,y), daemon=True)
        self._step_iter = iter(setup_steps.items())
        self._last_key = None
        self._setup_results = {}
        mouse_listener.start()
        self._nextSetupStep()

    def _safeUpdateRect(self, rect_end: QPoint) -> QRect:
        if self._rect_start:
            new_rect = QRect(self._rect_start, rect_end).normalized()
        else:
            self._rect_start = rect_end
            new_rect = QRect(rect_end, rect_end)

        self._setup_results[self._last_key] = new_rect
        self._tk_app.updateOverlay(self._setup_results)
        return new_rect

    def _onClick(self, x, y, pressed):
        click_mode = self._click_mode
        if click_mode != ClickMode.IDLE:
            p = QPoint(x, y)
            if pressed:
                if click_mode == ClickMode.SET_BOUNDS:
                    # Set top left of rect
                    self._tk_app.debug_var.set("Release to finish setting bounds")
                    self._safeUpdateRect(p)
            else:
                if click_mode == ClickMode.SET_BUTTON:
                    # Set click point
                    self._nextSetupStep(p)
                elif click_mode == ClickMode.SET_BOUNDS and self._rect_start:
                    # Set bottom right of rect, finish
                    self._nextSetupStep(self._safeUpdateRect(p))
                else:
                    self._click_mode = ClickMode.IDLE
                    # TODO: Probably tell the program something went wrong here

    def _onMove(self, x, y):
        if self._click_mode == ClickMode.SET_BOUNDS and self._rect_start is not None:
            self._safeUpdateRect(QPoint(x, y))

    def _nextSetupStep(self, result=None):
        if result is not None:
            # Add data from the previous step
            if type(result != QRect): # Rects already added, don't add another
                self._setup_results[self._last_key] = result
                self._tk_app.updateOverlay(self._setup_results)

        next_step_data = next(self._step_iter, None)
        if next_step_data:
            self._last_key, step = next_step_data
            self._click_mode = step.click_mode
            self._tk_app.debug_var.set(step.display_str)
            self._tk_app.updateOverlay(self._setup_results)
        else:
            self.exit()
            self._tk_app.finishSetup(self._setup_results)

    def exit(self):
        self._mouse_listener.stop()


if __name__ == "__main__":
    mackrel_test = MacroCreator()

    def some_task():
        print("I am going to sleep")
        yield from macroWait(1)
        print("We are back")

    def another_task():
        print("I am going to sleep as another task")
        yield from macroWait(5)
        print("We are done :D", mackrel_test.setup_vars["idk"])

    mackrel_test.addSetupStep("idk", ClickMode.SET_BUTTON, "Select SOmewhere")

    mackrel_test.addRunTask(some_task)
    mackrel_test.addRunTask(another_task)

    mackrel_test.mainLoop()

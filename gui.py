import ctypes, sys
import tkinter as tk
from pynput import mouse, keyboard
from pynput.keyboard import Key
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QPainter, QPen, QColor
from types_and_enums import ClickMode, MacroSteps
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine import MacroCreator

class TransparentOverlay(QWidget):
    def __init__(self):
        self.q_app = QApplication.instance()
        if not self.q_app:
            self.q_app = QApplication(sys.argv)

        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # Prevents showing in taskbar
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = self.q_app.primaryScreen()
        self.setGeometry(screen.geometry())

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
        hwnd = int(self.winId())

        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)

        if enable:
            new_style = ex_style | 0x80000 | 0x20
        else:
            new_style = ex_style & ~0x20

        ctypes.windll.user32.SetWindowLongW(hwnd, -20, new_style)

    def destroy(self, destroyWindow: bool = True, destroySubWindows: bool = True):
        # Only exit if we hold the reference, though usually main.py handles this
        if self.q_app:
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

        self.select_button = tk.Button(root, text="Begin Setup", command=self._alterSetup)
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
                    # First escape pauses creator, second stops it
                    if self.macro_creator.isPaused():
                        self.debug_var.set("ESC pressed. Stopped run")
                        self.macro_creator.cancelMacroExecution()
                    else:
                        self.toggleRun(False)
                elif setup_handler:
                    # First escape pauses setup, second stops it
                    if not setup_handler.listening:
                        self.setup_handler = None
                        self.updateOverlay()
                        self.macro_creator.finishSetup()
                        self.select_button.config(text="Begin Setup")
                        self.debug_var.set("ESC pressed. Setup cancelled.")
                    else:
                        self._alterSetup()
                    setup_handler.exit()
        keyboard.Listener(on_press=onPress, daemon=True).start()

    def _alterSetup(self):
        if self.macro_creator.isRunningMacros():
            self.debug_var.set("Cannot setup while macro is running.")
            return
        prev_handler = self.setup_handler
        if prev_handler:
            if prev_handler.listening: # Pause previous
                self.debug_var.set("Setup paused. ESC again to cancel setup.")
                self.select_button.config(text="Resume Setup")
                prev_handler.exit()
            else:
                prev_handler.resumeListening()
        else:
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
        was_paused = self.macro_creator.isPaused()
        should_run = not was_running if should_run is None else should_run
        if should_run:
            self.run_button.config(text="Pause")
            self.debug_var.set("Executing macro")
            self.macro_creator.startMacroExecution()
        elif was_running:
            if was_paused:
                self.run_button.config(text="Pause")
                self.debug_var.set("Execution resumed")
            else:
                self.run_button.config(text="Resume")
                self.debug_var.set("Execution paused")
            self.macro_creator.toggleMacroExecution()
        else:
            self.run_button.config(text="Start")

    def cleanup(self):
        if self.setup_handler:
            self.setup_handler.exit()
        self.overlayWidget.destroy()

class _SetupHandler:
    def __init__(self, setup_steps: MacroSteps, tk_app: TKApp):
        self._tk_app = tk_app
        self._click_mode = ClickMode.IDLE
        self._rect_start: QPoint | None = None
        self._step_iter = iter(setup_steps.items())
        self._last_packet = None
        self._setup_results = {}
        self._mouse_listener = None
        self.listening = False
        self.resumeListening()

    def _safeUpdateRect(self, rect_start: QPoint, rect_end: QPoint) -> QRect:
        new_rect = QRect(rect_start, rect_end).normalized()
        self._setup_results[self._last_packet[0]] = new_rect
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
                    self._rect_start = p
                    self._safeUpdateRect(p, p)
            else:
                prev_start = self._rect_start
                if click_mode == ClickMode.SET_BUTTON:
                    # Set click point
                    self._nextSetupStep(p)
                elif click_mode == ClickMode.SET_BOUNDS and prev_start:
                    # Set bottom right of rect, finish
                    self._rect_start = None
                    self._nextSetupStep(self._safeUpdateRect(prev_start, p))

    def _onMove(self, x, y):
        rect_start = self._rect_start
        if self._click_mode == ClickMode.SET_BOUNDS and rect_start is not None:
            self._safeUpdateRect(rect_start, QPoint(x, y))

    def _nextSetupStep(self, result=None):
        if result is not None:
            # Add data from the previous step
            if type(result != QRect): # Rects already added, don't add another
                self._setup_results[self._last_packet[0]] = result
                self._tk_app.updateOverlay(self._setup_results)

        if result is not None or self._last_packet is None:
            next_step_data = next(self._step_iter, None)
            if next_step_data:
                self._last_packet = next_step_data
                step = next_step_data[1]
                self._click_mode = step.click_mode
                self._tk_app.debug_var.set(step.display_str)
                self._tk_app.updateOverlay(self._setup_results)
            else:
                self.exit()
                self._tk_app.finishSetup(self._setup_results)
        else: # Resumed listening, use last step data
            self._tk_app.debug_var.set(self._last_packet[1].display_str)

    def resumeListening(self):
        if self._mouse_listener and self._mouse_listener.running: return
        self.listening = True
        self._mouse_listener = mouse_listener = mouse.Listener(
            on_click=lambda x, y, _, pressed: self._onClick(x, y, pressed), on_move=lambda x, y: self._onMove(x, y),
            daemon=True)

        mouse_listener.start()
        self._nextSetupStep()

    def exit(self):
        self._mouse_listener.stop()
        self.listening = False
        if self._rect_start:
            self._rect_start = None
            # Remove the last rectangle from the results since it was exited and update the overlay again
            del self._setup_results[self._last_packet[0]]
            self._tk_app.updateOverlay(self._setup_results)

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

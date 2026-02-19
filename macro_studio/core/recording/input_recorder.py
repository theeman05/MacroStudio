import time
from PySide6.QtCore import Signal, QObject, QPoint, QMutex, QMutexLocker
from pynput import mouse, keyboard
from pynput.mouse import Button

from .timeline_handler import TimelineStep, ActionType, MouseFunction
from .input_translator import DirectInputTranslator

_BUTTON_TO_FUNCTION_MAP = {
    Button.left: MouseFunction.LEFT_CLICK.name,
    Button.right: MouseFunction.RIGHT_CLICK.name,
    Button.middle: MouseFunction.SCROLL_CLICK.name,
}

class InputRecorder(QObject):
    stepAdded = Signal(int, object)  # (index, TimelineStep)

    def __init__(self, /):
        super().__init__()
        self.is_recording = False
        self._last_event_time = None
        self._start_time = 0

        self._mutex = QMutex()
        self._mouse_listener = None
        self._keyboard_listener = None
        self._pending_release = {}
        self._step_idx = 0
        self._ignore_keys = {"F8"}

    def start(self, start_step_ct):
        """Starts the recording listeners."""
        self.is_recording = True
        self._last_event_time = self._start_time =  time.time()
        self._step_idx = start_step_ct

        self._mouse_listener = mouse.Listener(
            on_click=self._onClick,
            on_scroll=self._onScroll
        )
        self._keyboard_listener = keyboard.Listener(
            on_press=self._onPress,
            on_release=self._onRelease
        )

        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self):
        """Stops the recording listeners."""
        self.is_recording = False
        self._pending_release.clear()
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

    def _incAndGetTaskIdx(self):
        with QMutexLocker(self._mutex):
            idx = self._step_idx
            self._step_idx = idx + 1
            return idx

    def _addPendingRelease(self, button, data: TimelineStep):
        with QMutexLocker(self._mutex):
            idx = self._step_idx
            self._step_idx += 1
            self._pending_release[button] = (data, idx)

        self.stepAdded.emit(idx, data)

    def _tryBindRelease(self, button, data: TimelineStep):
        p_data = p_idx = None
        with QMutexLocker(self._mutex):
            t_idx = self._step_idx
            self._step_idx += 1
            if button in self._pending_release:
                p_data, p_idx = self._pending_release.pop(button)

        if p_data:
            data.partner_idx = p_idx
            p_data.partner_idx = t_idx

        self.stepAdded.emit(t_idx, data)

    def _recordDelay(self):
        """Calculates delay between the current and previous event."""
        current_time = time.time()
        if self._last_event_time is None:
            self._last_event_time = current_time
            return

        delay = current_time - self._last_event_time
        self._last_event_time = current_time

        if delay > 0.01:
            idx = self._incAndGetTaskIdx()
            self.stepAdded.emit(idx, TimelineStep(
                action_type=ActionType.DELAY,
                value=round(delay, 3)
            ))

    def _onClick(self, x, y, button, pressed):
        if not self.is_recording:
            return

        if time.time() - self._start_time < 0.2:
            return

        mouse_btn = _BUTTON_TO_FUNCTION_MAP.get(button)
        if not mouse_btn: return

        if not pressed:
            # If we're releasing, ensure it was pressed before, or void it
            with QMutexLocker(self._mutex):
                if mouse_btn not in self._pending_release:
                    return

        self._recordDelay()
        value = (mouse_btn, QPoint(int(x), int(y)))

        if pressed:
            self._addPendingRelease(mouse_btn, TimelineStep(
                action_type=ActionType.MOUSE, value=value, detail=1
            ))
        else:
            self._tryBindRelease(mouse_btn, TimelineStep(
                action_type=ActionType.MOUSE, value=value, detail=2
            ))

    def _onScroll(self, x, y, _, dy):
        if not self.is_recording: return

        if dy > 0: func_enum = MouseFunction.SCROLL_UP
        elif dy < 0: func_enum = MouseFunction.SCROLL_DOWN
        else: return

        self._recordDelay()

        value = (func_enum.name, QPoint(int(x), int(y)))
        idx = self._incAndGetTaskIdx()
        self.stepAdded.emit(idx, TimelineStep(
            action_type=ActionType.MOUSE, value=value
        ))

    def _onPress(self, key):
        if not self.is_recording: return

        formatted_key = DirectInputTranslator.translateKey(key)
        if not formatted_key or formatted_key in self._ignore_keys:
            return

        # Don't allow double presses of the same key
        with QMutexLocker(self._mutex):
            if formatted_key in self._pending_release:
                return

        self._recordDelay()
        self._addPendingRelease(formatted_key, TimelineStep(
            action_type=ActionType.KEYBOARD, value=formatted_key, detail=1
        ))

    def _onRelease(self, key):
        if not self.is_recording: return

        formatted_key = DirectInputTranslator.translateKey(key)
        if not formatted_key or formatted_key in self._ignore_keys:
            return

        with QMutexLocker(self._mutex):
            if formatted_key not in self._pending_release:
                return

        self._recordDelay()
        self._tryBindRelease(formatted_key, TimelineStep(
            action_type=ActionType.KEYBOARD, value=formatted_key, detail=2
        ))
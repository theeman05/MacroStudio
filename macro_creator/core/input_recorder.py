import time
from PySide6.QtCore import Signal, QObject, QPoint, QMutex, QMutexLocker
from pynput import mouse, keyboard
from pynput.keyboard import Key

from macro_creator.core.data.timeline_handler import TimelineData, ActionType, MouseFunction, BUTTON_TO_FUNCTION_MAP


def _formatKey(key):
    if isinstance(key, Key):
        return key.name
    elif hasattr(key, 'char') and key.char:
        return key.char
    else:
        return str(key)


class InputRecorder(QObject):
    stepAdded = Signal(int, object)  # (index, TimelineData)

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
        self._ignore_keys = {"f8"}

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

    def _addPendingRelease(self, button, data: TimelineData):
        with QMutexLocker(self._mutex):
            idx = self._step_idx
            self._step_idx += 1
            self._pending_release[button] = (data, idx)

        self.stepAdded.emit(idx, data)

    def _tryBindRelease(self, button, data: TimelineData):
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
            self.stepAdded.emit(idx, TimelineData(
                action_type=ActionType.DELAY,
                value=round(delay, 3)
            ))

    def _onClick(self, x, y, button, pressed):
        if not self.is_recording:
            return

        if time.time() - self._start_time < 0.2:
            return

        if not pressed:
            with QMutexLocker(self._mutex):
                if button not in self._pending_release:
                    return

        self._recordDelay()
        mouse_fun = BUTTON_TO_FUNCTION_MAP.get(button)
        if not mouse_fun: return

        value = (mouse_fun.name, QPoint(int(x), int(y)))

        if pressed:
            self._addPendingRelease(button, TimelineData(
                action_type=ActionType.MOUSE, value=value, detail=1
            ))
        else:
            self._tryBindRelease(button, TimelineData(
                action_type=ActionType.MOUSE, value=value, detail=2
            ))

    def _onScroll(self, x, y, dx, dy):
        if not self.is_recording: return

        self._recordDelay()

        if dy > 0: func_enum = MouseFunction.SCROLL_UP
        elif dy < 0: func_enum = MouseFunction.SCROLL_DOWN
        elif dx > 0: func_enum = MouseFunction.SCROLL_RIGHT
        elif dx < 0: func_enum = MouseFunction.SCROLL_LEFT
        else: return

        value = (func_enum.name, QPoint(int(x), int(y)))
        idx = self._incAndGetTaskIdx()
        self.stepAdded.emit(idx, TimelineData(
            action_type=ActionType.MOUSE, value=value
        ))

    def _onPress(self, key):
        if not self.is_recording: return

        formatted_key = _formatKey(key)
        if formatted_key in self._ignore_keys:
            return

        self._recordDelay()
        self._addPendingRelease(key, TimelineData(
            action_type=ActionType.KEYBOARD, value=formatted_key, detail=1
        ))

    def _onRelease(self, key):
        if not self.is_recording: return

        formatted_key = _formatKey(key)
        if formatted_key in self._ignore_keys:
            return

        with QMutexLocker(self._mutex):
            if key not in self._pending_release:
                return

        self._recordDelay()
        self._tryBindRelease(key, TimelineData(
            action_type=ActionType.KEYBOARD, value=formatted_key, detail=2
        ))
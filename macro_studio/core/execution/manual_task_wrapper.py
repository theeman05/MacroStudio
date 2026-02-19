import pyperclip
import pydirectinput
from typing import TYPE_CHECKING
from PySide6.QtCore import QPoint

from macro_studio.core.types_and_enums import TaskInterruptedException
from macro_studio.core.recording.input_translator import DirectInputTranslator
from macro_studio.core.recording.timeline_handler import ActionType, TimelineStep, M_FUNCTION_TO_PYDIRECTINPUT
from macro_studio.actions import taskSleep, taskWaitForResume

if TYPE_CHECKING:
    from macro_studio.core.data import VariableStore, TaskModel

FORCE_YIELD_AT = 50

def _isPress(step):
    return step.detail == 1

def _isRelease(step):
    return step.detail == 2

def _isScroll(step):
    return step.action_type == ActionType.MOUSE and isinstance(step.value[0], int)

def pasteText(text_to_paste: str):
    if not text_to_paste:
        return

    original_clipboard = pyperclip.paste()
    try:
        pyperclip.copy(text_to_paste)

        yield from taskSleep(0.05)

        pydirectinput.keyDown('ctrl')
        pydirectinput.press('v')
        pydirectinput.keyUp('ctrl')

        yield from taskSleep(0.05)
    finally:
        pyperclip.copy(original_clipboard)


class ManualTaskWrapper:
    def __init__(self, var_store: "VariableStore", model: "TaskModel"):
        self.steps: list[TimelineStep] = []
        self.var_store = var_store
        self.step_idx = 0
        self.inputs_pending_release = set() # Set of inputs that had a partner
        self.active_solo_inputs = set() # Set of inputs to release upon task completion without partners
        self.updateModel(model)

    def updateModel(self, model: "TaskModel"):
        self.steps.clear()
        for raw_step in model.steps:
            step = TimelineStep.fromDict(raw_step)
            # Translate mouse and key stuff to pydirectinput
            if step.action_type == ActionType.MOUSE:
                button, pos = step.value
                button = M_FUNCTION_TO_PYDIRECTINPUT.get(button)
                step.value = (button, pos)
            elif step.action_type == ActionType.KEYBOARD:
                step.value = DirectInputTranslator.translateQtKey(step.value)
            self.steps.append(step)

    def _getMousePos(self, m_pos):
        if isinstance(m_pos, str):
            config = self.var_store.get(m_pos)
            value = config.value if config else None
            m_pos = value if isinstance(value, QPoint) else None

        if m_pos is None: return None, None

        return m_pos.x(), m_pos.y()

    def _pressKeyOrBtn(self, step_value):
        if isinstance(step_value, tuple):
            m_btn, m_pos = step_value
            x, y = self._getMousePos(m_pos)

            if isinstance(m_btn, int):
                pydirectinput.scroll(120 * m_btn, x=x, y=y)
            else:
                pydirectinput.mouseDown(m_btn, x=x, y=y)
        else:
            pydirectinput.keyDown(step_value)

    def _releaseKeyOrBtn(self, step_value):
        if isinstance(step_value, tuple):
            m_btn, m_pos = step_value
            x, y = self._getMousePos(m_pos)
            pydirectinput.mouseUp(m_btn, x=x, y=y, duration=0.001)
        else:
            pydirectinput.keyUp(step_value)

    def _addToSoloOrPending(self, step, solo, pending):
        if step.partner_idx is None:
            solo.add(step.value) # Need to release when task terminates
        else:
            pending.add(self.steps[step.partner_idx].value) # Need to release if interrupted

    def _shouldReleaseStep(self, step):
        return (step.partner_idx is not None or
                (step.value in self.inputs_pending_release) or
                (step.value in self.active_solo_inputs))

    def _processStep(self, step):
        if step.value is None: return

        if _isScroll(step):
            self._pressKeyOrBtn(step.value)
        elif _isPress(step):
            self._addToSoloOrPending(step, self.active_solo_inputs, self.inputs_pending_release)
            self._pressKeyOrBtn(step.value)
        elif _isRelease(step):
            if self._shouldReleaseStep(step):
                self.inputs_pending_release.discard(step)
                self.active_solo_inputs.discard(step)
                self._releaseKeyOrBtn(step.value)

    def _releasePendingInputs(self, release_solo=False):
        for step_val in self.inputs_pending_release:
            self._releaseKeyOrBtn(step_val)
        self.inputs_pending_release.clear()

        if release_solo:
            for step_val in self.active_solo_inputs:
                self._releaseKeyOrBtn(step_val)

            self.active_solo_inputs.clear()

    def resetState(self):
        self.step_idx = 0
        self._releasePendingInputs(release_solo=True)

    def runTask(self):
        try:
            while self.step_idx < len(self.steps):
                step = self.steps[self.step_idx]
                self.step_idx += 1

                if step.action_type == ActionType.DELAY:
                    delay_time = step.value or 0
                    yield from taskSleep(delay_time)
                elif step.action_type == ActionType.TEXT:
                    yield from pasteText(step.value)
                else:
                    self._processStep(step)
        except TaskInterruptedException:
            self._releasePendingInputs()
            yield from taskWaitForResume()
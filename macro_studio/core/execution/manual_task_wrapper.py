import pydirectinput
from typing import TYPE_CHECKING
from PySide6.QtCore import QPoint

from macro_studio.core.types_and_enums import TaskInterruptedException
from macro_studio.core.recording.input_translator import DirectInputTranslator
from macro_studio.core.recording.timeline_handler import ActionType, TimelineStep, M_FUNCTION_TO_PYDIRECTINPUT
from macro_studio.actions import taskSleep, taskWaitForResume, taskPasteText

if TYPE_CHECKING:
    from macro_studio.core.data import VariableStore, TaskModel

FORCE_YIELD_AT = 50

def _isPress(step):
    return step.detail == 1

def _isRelease(step):
    return step.detail == 2

def _isScroll(step):
    return step.action_type == ActionType.MOUSE and isinstance(step.value[0], int)


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
            step = TimelineStep.fromJson(raw_step)
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
                pydirectinput.scroll(clicks=120 * m_btn, x=x, y=y)
            else:
                pydirectinput.mouseDown(x=x, y=y, button=m_btn)
        else:
            pydirectinput.keyDown(step_value)

    def _releaseKeyOrBtn(self, step_value):
        if isinstance(step_value, tuple):
            m_btn, m_pos = step_value
            x, y = self._getMousePos(m_pos)
            pydirectinput.mouseUp(x=x, y=y, button=m_btn, duration=0.001)
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
        step_val = step.value

        if _isScroll(step):
            self._pressKeyOrBtn(step_val)
        elif _isPress(step):
            self._addToSoloOrPending(step, self.active_solo_inputs, self.inputs_pending_release)
            self._pressKeyOrBtn(step_val)
        elif _isRelease(step):
            if self._shouldReleaseStep(step):
                self.inputs_pending_release.discard(step_val)
                self.active_solo_inputs.discard(step_val)
                self._releaseKeyOrBtn(step_val)

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
                    yield from taskPasteText(step.value)
                else:
                    self._processStep(step)
        except TaskInterruptedException:
            self._releasePendingInputs()
            yield from taskWaitForResume()

    def generatePythonCode(self, task_name="my_exported_task") -> str:
        """Translates the current macro steps into a Python script."""

        lines = [
            "import pydirectinput",
            "from macro_studio import Controller, taskSleep, pasteText",
            "",
            f"def {task_name.lower().replace(' ', '_')}(controller: Controller):"
        ]

        body_lines = []
        vars_to_fetch = set()

        for step in self.steps:
            if step.action_type == ActionType.DELAY:
                body_lines.append(f"    yield from taskSleep({step.value})")

            elif step.action_type == ActionType.TEXT:
                body_lines.append(f"    yield from pasteText({repr(step.value)})")

            elif step.action_type == ActionType.KEYBOARD:
                key = step.value
                if _isPress(step):
                    body_lines.append(f"    pydirectinput.keyDown({repr(key)})")
                elif _isRelease(step):
                    body_lines.append(f"    pydirectinput.keyUp({repr(key)})")

            elif step.action_type == ActionType.MOUSE:
                m_btn, m_pos = step.value
                x_str, y_str = "None", "None"

                # Check if the position is a Variable or a hardcoded QPoint
                if isinstance(m_pos, str):
                    vars_to_fetch.add(m_pos)
                    safe_var = m_pos.replace(' ', '_')
                    x_str, y_str = f"{safe_var}_pos.x()", f"{safe_var}_pos.y()"
                elif m_pos:
                    x_str, y_str = m_pos.x(), m_pos.y()

                if _isScroll(step):
                    body_lines.append(f"    pydirectinput.scroll(clicks={120 * m_btn}, x={x_str}, y={y_str})")
                elif _isPress(step):
                    body_lines.append(f"    pydirectinput.mouseDown(x={x_str}, y={y_str}, button={repr(m_btn)})")
                elif _isRelease(step):
                    body_lines.append(f"    pydirectinput.mouseUp(x={x_str}, y={y_str}, button={repr(m_btn)})")

        # Inject variable fetching at the top of the function if needed
        if vars_to_fetch:
            for var_name in vars_to_fetch:
                safe_var = var_name.replace(' ', '_')
                lines.append(f"    {safe_var}_pos = controller.getVar({repr(var_name)})")
            lines.append("")  # Empty line for readability

        if not body_lines:
            body_lines.append("    pass")

        lines.extend(body_lines)
        return "\n".join(lines)
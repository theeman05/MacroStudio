from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias, OrderedDict, Hashable, Callable, Generator, Dict
from PyQt6.QtCore import QPoint, QRect

class ClickMode(Enum):
    IDLE = 0
    SET_BUTTON = 1
    SET_BOUNDS = 2

@dataclass
class SetupStep:
    display_str: str
    click_mode: ClickMode

@dataclass
class SetupStep:
    display_str: str
    click_mode: ClickMode

class MacroAbortException(Exception):
    """Exception raised when a macro is stopped by the user or system."""
    def __init__(self, message="Macro execution was aborted"):
        self.message = message
        super().__init__(self.message)

MacroSteps: TypeAlias = OrderedDict[Hashable, SetupStep]
TaskFunc: TypeAlias = Callable[[], Generator | None]
SetupVariable = QRect | QPoint
SetupVariables: TypeAlias = Dict[Hashable, SetupVariable]

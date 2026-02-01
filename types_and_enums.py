from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias, OrderedDict, Hashable, Callable, Generator, Dict
from PyQt6.QtCore import QPoint, QRect

class CaptureMode(Enum):
    IDLE = "IDLE"
    POINT = "POS"      # Single click
    REGION = "REGION"  # Drag selection

@dataclass
class SetupStep:
    display_str: str
    capture_mode: CaptureMode

@dataclass
class SetupStep:
    display_str: str
    capture_mode: CaptureMode

class MacroAbortException(Exception):
    """Exception raised when a macro is stopped by the user or system."""
    def __init__(self, message="Macro execution was aborted"):
        self.message = message
        super().__init__(self.message)

MacroSteps: TypeAlias = OrderedDict[Hashable, SetupStep]
TaskFunc: TypeAlias = Callable[[], Generator | None]
SetupVariable = QRect | QPoint
SetupVariables: TypeAlias = Dict[Hashable, SetupVariable]

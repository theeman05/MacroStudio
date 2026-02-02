from enum import Enum
from typing import TypeAlias, Callable, Generator, get_args

from PyQt6.QtCore import QRect, QPoint


class CaptureMode(Enum):
    POINT = "POS"      # Single click
    REGION = "REGION"  # Drag selection

class MacroAbortException(Exception):
    """Exception raised when a macro is stopped by the user or system."""
    def __init__(self, message="Macro execution was aborted"):
        self.message = message
        super().__init__(self.message)

TaskFunc: TypeAlias = Callable[[], Generator | None]
Pickable = CaptureMode | QRect | QPoint

PICKABLE_TYPES = get_args(Pickable)

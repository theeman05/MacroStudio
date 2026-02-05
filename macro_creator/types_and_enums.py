from enum import Enum
from typing import TypeAlias, Callable, Generator, get_args
from PySide6.QtCore import QRect, QPoint


class CaptureMode(Enum):
    POINT = "POS"      # Single click
    REGION = "REGION"  # Drag selection

class MacroAbortException(Exception):
    """Raised when the macro is stopped normally."""
    pass

class MacroHardPauseException(Exception):
    """Raised when the user triggers a hard stop/pause that requires cleanup."""
    pass

TaskFunc: TypeAlias = Callable[[], Generator | None]
Pickable = CaptureMode | QRect | QPoint

PICKABLE_TYPES = get_args(Pickable)

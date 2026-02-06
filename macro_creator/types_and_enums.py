from dataclasses import dataclass
from enum import Enum, auto
from typing import TypeAlias, Callable, Generator, Tuple, get_args
from PySide6.QtCore import QRect, QPoint


class CaptureMode(Enum):
    POINT = auto()      # Single click
    REGION = auto()  # Drag selection

class LogLevel(Enum):
    ERROR = auto()
    INFO = auto()
    WARN = auto()

@dataclass
class LogPacket:
    parts: Tuple[object, ...]
    level: LogLevel = LogLevel.INFO
    task_id: int = 0

@dataclass
class LogErrorPacket:
    message: str
    traceback: str
    task_id: int

class MacroAbortException(Exception):
    """Raised when the macro is stopped normally."""
    pass

class MacroHardPauseException(Exception):
    """Raised when the user triggers a hard stop/pause that requires cleanup."""
    pass

TaskFunc: TypeAlias = Callable[..., Generator | None]
Pickable = CaptureMode | QRect | QPoint

PICKABLE_TYPES = get_args(Pickable)

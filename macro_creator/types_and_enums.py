from dataclasses import dataclass
from enum import Enum, auto
from typing import TypeAlias, Callable, Generator, Tuple

class CaptureMode(Enum):
    POINT = auto()      # Single click
    REGION = auto()  # Drag selection

@dataclass(frozen=True)
class CaptureTypeDef:
    mode: CaptureMode
    type_class: type
    tip: str

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

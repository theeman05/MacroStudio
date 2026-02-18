from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, TypeAlias, Callable, Generator, Tuple

if TYPE_CHECKING:
    from macro_studio.ui.overlay import TransparentOverlay
    from macro_studio.core.data.variable_config import VariableConfig

class CaptureMode(Enum):
    POINT = auto()      # Single click
    REGION = auto()  # Drag selection

@dataclass(frozen=True)
class CaptureTypeDef:
    mode: CaptureMode
    type_class: type
    tip: str
    capture_method: Callable[["TransparentOverlay", "VariableConfig"], None]

class LogLevel(Enum):
    ERROR = auto()
    INFO = auto()
    WARN = auto()

@dataclass
class LogPacket:
    parts: Tuple[object, ...]
    level: LogLevel = LogLevel.INFO
    task_name: int | str = 0

@dataclass
class LogErrorPacket:
    message: str
    traceback: str | None
    task_name: int | str

class TaskAbortException(BaseException):
    """Raised when the macro is stopped normally."""
    pass

class TaskInterruptedException(BaseException):
    """Raised when the user triggers an interrupted pause."""
    pass

TaskFunc: TypeAlias = Callable[..., Generator | None]

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias, OrderedDict, Hashable, Callable, Generator

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

MacroSteps: TypeAlias = OrderedDict[Hashable, SetupStep]
TaskFunc: TypeAlias = Callable[[], Generator | None]

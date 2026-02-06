from PySide6.QtCore import QRect, QPoint

from .types_and_enums import CaptureTypeDef, CaptureMode

class CaptureRegistry:
    _definitions = {} # Maps Mode -> Definition
    _type_map = {}  # Maps PythonType -> Mode

    @classmethod
    def register(cls, definition: CaptureTypeDef):
        cls._definitions[definition.mode] = definition
        cls._type_map[definition.type_class] = definition.mode

    @classmethod
    def get(cls, mode: CaptureMode) -> CaptureTypeDef | None:
        return cls._definitions.get(mode)

    @classmethod
    def getAll(cls):
        return cls._definitions.values()

    @classmethod
    def getModeFromType(cls, type_class: type) -> CaptureMode | None:
        """Lookup to find the CaptureMode associated with a specific class. """
        return cls._type_map.get(type_class, None)

    @classmethod
    def containsMode(cls, mode: CaptureMode) -> bool:
        """
        Checks if a mode is explicitly registered.
        Usage: if CaptureRegistry.contains(mode):
        """
        return mode in cls._definitions

    @classmethod
    def containsType(cls, type_class: type) -> bool:
        """
        Checks if a mode is explicitly registered.
        Usage: if CaptureRegistry.contains(mode):
        """
        return type_class in cls._type_map

CaptureRegistry.register(CaptureTypeDef(
    mode=CaptureMode.POINT,
    type_class=QPoint,
    tip="Format: x, y"
))

CaptureRegistry.register(CaptureTypeDef(
    mode=CaptureMode.REGION,
    type_class=QRect,
    tip="Format: x, y, width, height"
))
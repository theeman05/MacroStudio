from enum import Enum

from typing import Hashable

from .type_handler import GlobalTypeHandler
from .types_and_enums import CaptureMode
from .capture_type_registry import CaptureRegistry

class VariableConfig:
    def __init__(self, data_type: CaptureMode | type, default_val=None, pick_hint: str=None):
        """
        Instantiates a new variable config object
        Args:
            data_type: The data type for the object used for parsing and getting.
            default_val: The value on initializing the config
            pick_hint: The hint to display when we are hovering over the object (if pickable, when selecting)
        """
        self.data_type = CaptureRegistry.get(data_type).type_class if CaptureRegistry.containsMode(data_type) else data_type
        self.value = default_val
        self.hint = pick_hint
        self.row: int | None = None # The row in the UI

    @classmethod
    def keyToStr(cls, key: Hashable):
        """Converts the given key to a compatible string for hashing and saving."""
        return key.name if isinstance(key, Enum) else str(key)

    def toDict(self):
        """
        Serializes this variable for saving.
        Uses the GlobalTypeHandler to safely stringify complex objects.
        """
        type_name = self.data_type.__name__

        if self.value is None:
            value_str = None
        else:
            try:
                value_str = GlobalTypeHandler.toString(self.value)
            except Exception as e:
                print(f"Error serializing {self}: {e}")
                value_str = ""

        serial = {
            "type": type_name,
            "value": value_str,
        }

        if self.hint: serial["hint"] = self.hint

        return serial

    @staticmethod
    def fromDict(data):
        """Factory method to create a VariableConfig from saved JSON."""
        type_name = data.get("type", "str")
        value_data = data.get("value")
        hint = data.get("hint", "")

        # Resolve the string "int" back to the class <int>
        target_type = GlobalTypeHandler.getTypeClass(type_name)
        real_value = GlobalTypeHandler.fromString(target_type, value_data) if value_data is not None else None

        return VariableConfig(target_type, real_value, hint)
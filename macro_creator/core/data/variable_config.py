from enum import Enum

from typing import Hashable

from macro_creator.core.type_handler import GlobalTypeHandler
from macro_creator.core.types_and_enums import CaptureMode
from macro_creator.core.capture_type_registry import GlobalCaptureRegistry

class VariableConfig:
    def __init__(self, data_type: CaptureMode | type, default_val=None, pick_hint: str=None):
        """
        Instantiates a new variable config object
        Args:
            data_type: The value type for the object used for parsing and getting.
            default_val: The value on initializing the config
            pick_hint: The hint to display when we are hovering over the object (if pickable, when selecting)
        """
        self.data_type = GlobalCaptureRegistry.get(data_type).type_class if GlobalCaptureRegistry.containsMode(data_type) else data_type
        self.value = default_val
        self.hint = pick_hint

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

        value_str = None
        if self.value is not None:
            try:
                value_str = GlobalTypeHandler.toString(self.value)
            except Exception as e:
                print(f"Error serializing {self}: {e}")

        serial = {"type": type_name}

        GlobalTypeHandler.setIfEvals("value", value_str, serial)
        GlobalTypeHandler.setIfEvals("hint", self.hint, serial)

        return serial

    @staticmethod
    def fromDict(data):
        """Factory method to create a VariableConfig from saved JSON."""
        type_name = data.get("type", "str")
        value_data = data.get("value")
        hint = data.get("hint")

        target_type = GlobalTypeHandler.getTypeClass(type_name)
        real_value = None
        if value_data is not None:
            try:
                real_value = GlobalTypeHandler.fromString(target_type, value_data)
            except Exception as e:
                print(f"Error serializing deserializing value for {type_name}: {e}")

        return VariableConfig(target_type, real_value, hint)
from typing import Hashable
from PySide6.QtCore import Signal

from .base_store import BaseStore
from .variable_config import VariableConfig
from macro_studio.core.types_and_enums import CaptureMode
from macro_studio.core.controllers.capture_type_registry import GlobalCaptureRegistry


class VariableStore(BaseStore):
    varAdded = Signal(str, object) # (key string, config)
    varRemoved = Signal(str, object) # (key string, config)
    varChanged = Signal(str) # (key string)

    def __init__(self):
        super().__init__("variables")
        self._vars: dict[str, VariableConfig] = {}

    def add(self, key: Hashable, data_type: CaptureMode | type, default_val: object=None, pick_hint: str=None):
        """
        Add a variable to the store.

        If the key is present already and value types differ, overwrites the previous variable.
        Args:
            key: The key to store the variable under.
            data_type: The value type of the variable.
            default_val: The default value of this variable.
            pick_hint: The hint to display while the variable is being picked or hovered over
        """
        key_str = VariableConfig.keyToStr(key)
        if key_str not in self:
            config = VariableConfig(data_type, default_val, pick_hint)
            self._vars[key_str] = config
            self.varAdded.emit(key_str, config)
        else:
            config = self[key_str]
            has_changes = False
            if config.hint != pick_hint and pick_hint is not None:
                config.hint = pick_hint
                has_changes = True

            data_type = GlobalCaptureRegistry.get(data_type).type_class if GlobalCaptureRegistry.containsMode(data_type) else data_type

            # If value types differ, or there's no value for config, overwrite the previous value and value type
            if (data_type is not config.data_type) or (config.value is None and default_val != config.value):
                has_changes = True
                config.data_type = data_type
                config.value = default_val

            if has_changes: self.varChanged.emit(key_str)

    def remove(self, key: Hashable) -> VariableConfig | None:
        """Attempts to remove the key from the store. If the key is not present, returns None."""
        key_str = VariableConfig.keyToStr(key)
        if key_str in self:
            config = self._vars.pop(key_str)
            self.varRemoved.emit(key_str, config)
            return config
        return None

    def updateValue(self, key: Hashable, new_value):
        """
        Updates the value for the config associated with the key to be the new value.

        Args:
            key: The key to store the variable under.
            new_value: The new value.

        Raises:
            KeyError: If the key is not present in the store.
        """
        key_str = VariableConfig.keyToStr(key)

        if not key_str in self: raise KeyError(f"Could not find key '{key_str}' in store.")

        self._vars[key_str].value = new_value
        self.varChanged.emit(key_str)

    def get(self, key: Hashable) -> VariableConfig | None:
        return self._vars.get(VariableConfig.keyToStr(key))

    def items(self):
        return self._vars.items()

    def values(self):
        return self._vars.values()

    def keys(self):
        return self._vars.keys()

    def serialize(self):
        serial_data = {}
        for key_str, var_config in self._vars.items():
            serial_data[key_str] = var_config.toDict()

        return serial_data

    def deserialize(self, data: dict):
        if not data: return

        new_vars = {}
        for key_str, var_data in data.items():
            new_vars[key_str] = VariableConfig.fromDict(var_data)

        self._vars = new_vars

    def __contains__(self, item):
        return item in self._vars

    def __getitem__(self, item):
        return self._vars[item]

    def __len__(self):
        return len(self._vars)

    def __iter__(self):
        return iter(self._vars)
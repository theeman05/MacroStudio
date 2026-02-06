from PySide6.QtCore import QPoint, QRect

from .types_and_enums import Pickable, CaptureMode


class VariableConfig:
    def __init__(self, data_type: Pickable | type, default_val=None, pick_hint: str=None):
        """
        Instantiates a new variable config object. Feel free to override these methods to fit your casting needs :P.
        :param data_type: The data type for the object used for parsing and getting.
        :param default_val: The value on initializing the config
        :param pick_hint: The hint to display when we are hovering over the object (if pickable, when selecting)
        """
        if data_type is CaptureMode.POINT:
            self._data_type = QPoint
        elif data_type is CaptureMode.REGION:
            self._data_type = QRect
        else:
            self._data_type = data_type

        self.value = default_val
        self.pick_hint = pick_hint

    @property
    def data_type(self):
        return self._data_type

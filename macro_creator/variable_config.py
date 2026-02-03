from PyQt6.QtCore import QPoint, QRect
from .types_and_enums import Pickable, CaptureMode, PICKABLE_TYPES


def _parseQTVariant(text: str, target_type):
    """
    Parses a comma-separated string into a QRect or QPoint.
    """
    # 1. Basic Cleanup: Remove spaces/tabs so " 10,  20 " becomes "10,20"
    clean_text = text.strip()
    if not clean_text:
        print(f"Expected '{target_type}' but got None")
        raise ValueError()

    # 2. Split by comma
    parts = clean_text.split(',')

    # 3. Clean up each part (remove spaces around numbers) and convert to int
    # This will raise ValueError if the user types "10, abc"
    values = [int(p.strip()) for p in parts if p.strip()]

    # --- QRECT LOGIC ---
    if target_type is QRect:
        if len(values) == 4:
            return QRect(values[0], values[1], values[2], values[3]).normalized()
        else:
            print(f"Parse Error: QRect requires 4 numbers (x, y, w, h). Got {len(values)}.")
            raise TypeError()

    # --- QPOINT LOGIC ---
    elif target_type is QPoint:
        if len(values) == 2:
            return QPoint(values[0], values[1])
        else:
            print(f"Parse Error: QPoint requires 2 numbers (x, y). Got {len(values)}.")
            raise TypeError()

    # Fallback for other types if needed
    return TypeError()


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

    def parseAndSetValue(self, val_str: str) -> bool:
        """
        Try to parse the value to this config's data type. If parse fails, uses the previous value.
        :param val_str: String to parse
        :return: True if parsed successfully, False otherwise
        """
        try:
            if val_str == "" and self._data_type is not str:
                self.value = val_str
            elif self._data_type is bool:
                self.value = str(val_str).lower() in ("true", "1", "yes", "on")
            elif self._data_type in PICKABLE_TYPES:
                self.value = _parseQTVariant(val_str, self._data_type)
            else:
                self.value = self._data_type(val_str)
            return True
        except (ValueError, TypeError):
            print(f"Failed to cast '{val_str}' to {self._data_type}")
            return False

    def getValueStr(self) -> str:
        """
        Gets the value string for the current value.
        If a string formatter is present, uses that to format the value.
        Otherwise, defaults to some common built-ins, or lastly uses str(value)
        """
        val = self.value
        if isinstance(val, float):
            return f"{val:.2f}"

        if isinstance(val, QPoint):
            return f"{val.x()}, {val.y()}"

        if isinstance(val, QRect):
            return f"{val.x()}, {val.y()}, {val.width()}, {val.height()}"

        return str(val) if val is not None else ""

from pynput import keyboard

_PYNPUT_TO_QT_STRING = {
    "ctrl_l": "Control",
    "ctrl_r": "Control",
    "shift_l": "Shift",
    "shift_r": "Shift",
    "alt_l": "Alt",
    "alt_r": "Alt",
    "cmd": "Meta",        # Qt calls the Windows/Mac key "Meta"
    "cmd_r": "Meta",
    "enter": "Return",    # Qt calls the Enter key "Return"
    "esc": "Escape",
    "space": "Space",
    "tab": "Tab",
    "backspace": "Backspace",
    "delete": "Del",
    "insert": "Ins",
    "page_up": "PgUp",
    "page_down": "PgDown",
    "home": "Home",
    "end": "End",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "caps_lock": "CapsLock"
}

_QT_TO_PYDIRECTINPUT = {
    "control": "ctrl",
    "meta": "win",       # Qt calls the Windows key "Meta"
    "return": "enter",   # Qt calls the Enter key "Return"
    "escape": "esc",
    "del": "delete",
    "ins": "insert",
    "pgup": "pageup",
    "page up": "pageup",
    "pgdown": "pagedown",
    "page down": "pagedown"
}


class DirectInputTranslator:
    @classmethod
    def translateKey(cls, key):
        """Converts a raw pynput key into a Qt QKeySequence string."""

        # 1. Handle Special Keys (e.g., Key.shift, Key.enter)
        if isinstance(key, keyboard.Key) or hasattr(key, 'name'):
            key_name = key.name
            if key_name is None:
                return None

            # Return the mapped Qt version. If it's a weird hardware key
            # not in the dict, fallback to Title Case (e.g., "media_play" -> "Media_Play")
            return _PYNPUT_TO_QT_STRING.get(key_name, key_name.title())

        # 2. Handle Standard Alphanumeric Keys
        if hasattr(key, 'char') and key.char is not None:
            char_code = ord(key.char)

            # Catch OS-mutated Control keys (Ctrl+A = \x01 ... Ctrl+Z = \x1a)
            if 1 <= char_code <= 26:
                # Math trick: Add 64 to convert the control code back to an UPPERCASE letter!
                # e.g., Ctrl+C is ASCII 3. 3 + 64 = 67. ASCII 67 is 'C'.
                return chr(char_code + 64)

            # Qt standardized strings use uppercase for the base letters
            return key.char.upper()

        # 3. Fallback for completely unknown hardware keys
        return None

    @classmethod
    def translateQtKey(cls, qt_string: str):
        """Translates a single Qt string directly into PyDirectInput format."""
        if not qt_string: return None

        clean_key = qt_string.lower()

        # If it's a special key in our map (like "return" -> "enter"), return the mapping.
        # Otherwise, just return the lowercase letter (like "c" -> "c")
        return _QT_TO_PYDIRECTINPUT.get(clean_key, clean_key)
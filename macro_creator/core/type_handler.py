import ast
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Type
from PySide6.QtCore import QRect, QPoint

BASIC_TYPES = (int, float, str, bool, type(None))

# Basic types that we didn't register
DEFAULT_TYPE_CLASS_NAMES = {
    int: "Integer",
    str: "Text",
    float: "Decimal"
}

@dataclass
class RegistryItem:
    formatter: Callable[[Any], str]=None
    parser: Callable[[str], Any]=None
    display_name: str = None

class GlobalTypeHandler:
    """
    Central registry for converting objects into human-readable strings/HTML.
    """
    _registry: Dict[Type, RegistryItem] = {}
    _type_names_map: Dict[str, Type] = {
        "int": int,
        "float": float,
    }

    @classmethod
    def register(cls, target_type, formatter: Callable[[Any], str]=None, parser: Callable[[str], Any]=None,
                 display_name: str=None):
        """
        Registers support for a custom type.
        Args:
            target_type: The class you are supporting (e.g. QRect)
            formatter: Function that converts Object -> String
            parser: Function that converts String -> Object
            display_name: A pretty name to display the type as, like "Region" or "Whole Number"
        """
        reg_item = cls._registry.setdefault(target_type, RegistryItem())
        cls._type_names_map[target_type.__name__] = target_type

        if formatter: reg_item.formatter = formatter
        if parser: reg_item.parser = parser
        if display_name: reg_item.display_name = display_name

    @classmethod
    def toString(cls, obj: Any) -> str:
        """Converts any object to a string using the best registered formatter."""
        if obj is None:
            return ""

        # Exact Match (Fastest)
        if (reg_item := cls._registry.get(type(obj))) and reg_item.formatter:
            return reg_item.formatter(obj)

        # If it's a basic python type not in exact matches, just return it as a string
        if isinstance(obj, BASIC_TYPES):
            return str(obj)

        # Inheritance Match (Slower, but handles subclasses)
        # We check if the object is an instance of a registered key
        for registered_type, reg_item in cls._registry.items():
            if isinstance(obj, registered_type) and reg_item.formatter:
                return reg_item.formatter(obj)

        # Fallback to str if unregistered type
        return str(obj)

    @classmethod
    def fromString(cls, target_type, val_str: str):
        """
        Converts the value from a string to the target type.
        Raises:
            ValueError/TypeError: if failed.
        """
        # Custom Parsers
        if (reg_item := cls._registry.get(target_type)) and reg_item.parser:
            return reg_item.parser(val_str)

        # Default Casting
        return target_type(val_str)

    @classmethod
    def getDisplayName(cls, target_type) -> str:
        """Returns the friendly name if registered, otherwise defaults to the class name."""
        if (reg_item := cls._registry.get(target_type)) and reg_item.display_name:
            return reg_item.display_name

        # Basic types that we don't have anything for
        if target_type in DEFAULT_TYPE_CLASS_NAMES:
            return DEFAULT_TYPE_CLASS_NAMES[target_type]

        if hasattr(target_type, '__name__'):
            return target_type.__name__.capitalize()

        return str(target_type)

    @classmethod
    def getTypeClass(cls, type_name: str):
        """Returns the type class for the name string if the type is registered"""
        if type_name in cls._type_names_map:
            return cls._type_names_map.get(type_name)

        # Fallback to str if unregistered type
        return str


# --- Helper Decorator for easy registration ---
def _registerClass(cls, target_type = None):
    GlobalTypeHandler.register(target_type or cls,
                               getattr(cls, "toString", None),
                               getattr(cls, "fromString", None),
                               getattr(cls, "display_name", None)
                               )
    return cls

def register_handler(cls=None):
    """
    Auto-registers a class.

    * Looks for static methods: **toString**, **fromString**
    * Looks for class attribute: **display_name**

    Supports:

    * **@register_handler**        (Registers the class itself)
    * **@register_handler(QRect)** (Registers the class as a proxy for QRect)
    """

    # HEURISTIC: Use 'duck typing' to detect if 'cls' is the Handler Class.
    # If it is a class AND has the methods we expect, it's the Handler (Direct Mode).
    is_likely_handler = (inspect.isclass(cls) and (hasattr(cls, "toString") or hasattr(cls, "fromString")))

    if is_likely_handler:
        # Case 1: @registerHandler (No Parens) on a class with correct methods
        return _registerClass(cls)

    # Case 2: @registerHandler(QRect) (Target Type passed as argument)
    target_type = cls
    def wrapper(handler_cls):
        return _registerClass(handler_cls, target_type)

    return wrapper

# --- Custom type registration ---
@register_handler(QRect)
class QRectHandler:
    display_name = "Region"

    @staticmethod
    def toString(obj: QRect):
        return f"{obj.x()}, {obj.y()}, {obj.width()}, {obj.height()}"

    @staticmethod
    def fromString(text: str):
        parts = [p.strip() for p in text.split(',') if p.strip()]

        if len(parts) != 4:
            raise ValueError(f"QRect requires 4 integers (x, y, w, h). Found {len(parts)}.")

        try:
            vals = [int(p) for p in parts]
            return QRect(vals[0], vals[1], vals[2], vals[3]).normalized()
        except ValueError:
            raise ValueError(f"Could not convert parts to integers: {text}")

@register_handler(QPoint)
class QPointHandler:
    display_name = "Point"
    @staticmethod
    def toString(point: QPoint):
        return f"{point.x()}, {point.y()}"

    @staticmethod
    def fromString(text: str):
        parts = [p.strip() for p in text.split(',') if p.strip()]

        if len(parts) != 2:
            raise ValueError(f"QPoint requires 2 integers (x,y). Found {len(parts)}.")

        try:
            vals = [int(p) for p in parts]
            return QPoint(vals[0], vals[1])
        except ValueError:
            raise ValueError(f"Could not convert parts to integers: {text}")


# --- Python type registration ---
@register_handler(bool)
class BooleanHandler:
    display_name = "Boolean"

    @staticmethod
    def fromString(text: str):
        clean = text.strip().lower()
        return clean in ("true", "1", "yes", "on", "t")

@register_handler(list)
class ListHandler:
    @staticmethod
    def toString(val: list):
        return str([GlobalTypeHandler.toString(item) for item in val])

    @staticmethod
    def fromString(text: str):
        text = text.strip()

        # Handle empty input
        if not text:
            return []

        # Add brackets if user forgot them: "1, 2, 3" -> "[1, 2, 3]"
        if not text.startswith("["):
            text = f"[{text}]"

        try:
            # NOTE: This returns basic types (int, float, str).
            # It does NOT automatically convert "1, 1" back to QPoint
            # because a generic list doesn't know what type it holds.
            val = ast.literal_eval(text)

            if not isinstance(val, list):
                raise ValueError("Parsed value is not a list")

            return val
        except (ValueError, SyntaxError):
            raise ValueError(f"Invalid list format: {text}")

@register_handler(tuple)
class TupleHandler:
    @staticmethod
    def toString(val: tuple):
        return str(tuple(GlobalTypeHandler.toString(item) for item in val))

    @staticmethod
    def fromString(text: str):
        text = text.strip()

        if not text:
            return ()

        # Add parens if user forgot them: "1, 2" -> "(1, 2)"
        # Note: Users must explicitly type "1," (with comma) for single-item tuples
        if not text.startswith("("):
            text = f"({text})"

        try:
            val = ast.literal_eval(text)

            # Edge case: "(1)" parses as int 1, not tuple (1,).
            # We fail here so user knows to add a comma.
            if not isinstance(val, tuple):
                raise ValueError("Parsed value is not a tuple (Did you forget a comma for a single item?)")

            return val
        except (ValueError, SyntaxError):
            raise ValueError(f"Invalid tuple format: {text}")
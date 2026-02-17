from PySide6.QtCore import QObject


class BaseStore(QObject):
    """
    The foundational class for all data stores in the profile.
    Enforces a strict contract for serialization.
    """
    def __init__(self, store_name: str, parent=None):
        super().__init__(parent)
        # This is the exact key name that will be used in the JSON file
        self._store_name = store_name

    @property
    def store_name(self) -> str:
        return self._store_name

    def serialize(self) -> dict | list | None:
        """
        Converts the store's internal data into standard Python types
        (dicts, lists, strings, ints) so it can be saved to JSON.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement serialize()")

    def deserialize(self, data: dict | list | None):
        """Takes parsed JSON data and rebuilds the store's internal state."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement deserialize()")
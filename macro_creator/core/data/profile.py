import os

from .base_store import BaseStore
from .task_store import TaskStore
from .variable_store import VariableStore
from macro_creator.core.controllers.type_handler import GlobalTypeHandler
from macro_creator.core.utils import FileIO


class Profile:
    def __init__(self, profile_name: str, auto_load=True):
        super().__init__()
        self.name = profile_name
        self.vars = VariableStore()
        self.tasks = TaskStore()
        self.has_saved = False

        self._registered_stores: list[BaseStore] = [
            self.tasks,
            self.vars
        ]

        if auto_load: self.load()

    def save(self):
        if self.has_saved: return
        self.has_saved = True
        master_data = {}

        start_len = len(master_data)
        for store in self._registered_stores:
            GlobalTypeHandler.setIfEvals(store.store_name, store.serialize(), master_data)

        # Save if we have data
        if start_len != len(master_data):
            FileIO.exportData(master_data, self.getFilepath())

    def load(self):
        self.has_saved = False
        master_data = FileIO.importData(self.getFilepath())
        if master_data is not None:
            for store in self._registered_stores:
                # If the JSON file has this store's data, pass it down
                if store.store_name in master_data:
                    store.deserialize(master_data.pop(store.store_name))
                else:
                    # If missing (e.g. an older save file), pass None
                    store.deserialize(None)

    def getFilepath(self) -> str:
        base_dir = os.path.join(os.getcwd(), "data", "profiles")

        os.makedirs(base_dir, exist_ok=True)

        safe_name = "".join(c for c in self.name if c.isalnum() or c in (' ', '_', '-')).strip()
        safe_name = safe_name.replace(" ", "_").lower()

        return os.path.join(base_dir, f"{safe_name}.json")
from dataclasses import dataclass

from .task_store import TaskStore
from .variable_store import VariableStore
from .database_manager import DatabaseManager

@dataclass
class TaskRelationship:
    id: int
    task_id: int
    repeat: bool=False
    enabled: bool=True

class Profile:
    def __init__(self, profile_name: str, parent=None):
        self.db = DatabaseManager()
        self.name = profile_name
        self.id = self._get_or_create_id()
        self.task_relationships = set()

        self.vars = VariableStore(self.db, self.id, parent=parent)
        self.tasks = TaskStore(self.db, self.id, parent=parent)

        self.load()

    def _get_or_create_id(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM profiles WHERE name = ?", (self.name,))
            row = cursor.fetchone()
            if row:
                return row["id"]
            else:
                cursor.execute("INSERT INTO profiles (name) VALUES (?)", (self.name,))
                conn.commit()
                return cursor.lastrowid

    def load(self):
        self.task_relationships.clear()
        self.vars.load()
        self.tasks.load()
        # Load relationships
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from .task_store import TaskStore, TaskModel
from .variable_store import VariableStore
from .database_manager import DatabaseManager

@dataclass
class TaskRelationship:
    id: int
    task_id: int
    repeat: bool
    is_enabled: bool

class Profile(QObject):
    relationshipCreated = Signal(object) # (relationship object)

    def __init__(self, profile_name: str, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()
        self.name = profile_name
        self.id = self._getOrCreateId()
        self.task_relationships: dict[int, TaskRelationship] = dict() # Task_id, relationship

        self.vars = VariableStore(self.db, self.id, parent=self)
        self.tasks = TaskStore(self, parent=self)

        self.load()

        # Connect Signals
        self.tasks.taskRemoved.connect(self._onTaskRemoved)

    def _getOrCreateId(self):
        with self.db.getConn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM profiles WHERE name = ?", (self.name,))
            row = cursor.fetchone()
            if row:
                return row["id"]
            else:
                cursor.execute("INSERT INTO profiles (name) VALUES (?)", (self.name,))
                conn.commit()
                return cursor.lastrowid

    def _onTaskRemoved(self, deleted_model: TaskModel):
        if deleted_model.id in self.task_relationships:
            del self.task_relationships[deleted_model.id]

    def createRelationship(self, task_id, repeat=False, enabled=True):
        with self.db.getConn() as conn:
            cursor = conn.execute("""
                INSERT INTO profile_tasks (profile_id, task_id, repeat, is_enabled) 
                VALUES(?, ?, ?, ?)
                RETURNING id
            """, (self.id, task_id, repeat, enabled))
            row = cursor.fetchone()
            relation_id = row["id"]

            conn.commit()

        relationship = TaskRelationship(relation_id, task_id, repeat, enabled)
        self.task_relationships[task_id] = relationship
        self.relationshipCreated.emit(relationship)

    def updateRelationshipState(self, relationship: TaskRelationship, field: str, value):
        """Updates relationship state and pushes changes to the DB"""
        setattr(relationship, field, value)

        with self.db.getConn() as conn:
            query = f"UPDATE profile_tasks SET {field} = ? WHERE id = ?"
            conn.execute(query, (value, relationship.id))
            conn.commit()

    def load(self):
        self.task_relationships.clear()

        with self.db.getConn() as conn:
            rows = conn.execute("SELECT * FROM profile_tasks WHERE profile_id = ? ORDER BY created_at", (self.id,))
            for row in rows:
                self.task_relationships[row["task_id"]] = TaskRelationship(
                    id=row["id"],
                    task_id=row["task_id"],
                    repeat=row["repeat"],
                    is_enabled=row["is_enabled"]
                )

        self.vars.load()
        self.tasks.load()
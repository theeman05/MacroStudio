import sqlite3
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from .task_store import TaskStore, TaskModel
from .variable_store import VariableStore, copyVarsToNewProfile
from .database_manager import DatabaseManager

from macro_studio.core.utils import generateUniqueName

@dataclass
class TaskRelationship:
    id: int
    task_id: int
    repeat: bool
    is_enabled: bool

class Profile(QObject):
    loaded = Signal(bool) # Is First Load
    relationshipCreated = Signal(object) # (relationship object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()
        self.task_relationships: dict[int, TaskRelationship] = dict() # Task_id, relationship
        self.name: str | None = None
        self.id: int | None = None

        self.vars = VariableStore(self.db, parent=self)
        self.tasks = TaskStore(self, parent=self)
        self.profile_names = set()

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

    def createProfile(self, profile_name: str):
        if profile_name in self.profile_names: return False
        self.profile_names.add(profile_name)
        with self.db.getConn() as conn:
            try:
                conn.execute("INSERT INTO profiles (name) VALUES (?)", (profile_name,))
                conn.commit()
            except sqlite3.IntegrityError:
                return False
        return True

    def renameProfile(self, old_name, new_name):
        if old_name not in self.profile_names or new_name in self.profile_names: return False
        with self.db.getConn() as conn:
            try:
                conn.execute("UPDATE profiles SET name = ? WHERE name = ?", (new_name, old_name))
                conn.commit()
            except sqlite3.IntegrityError:
                return False

        self.profile_names.remove(old_name)
        self.profile_names.add(new_name)

        return True

    def deleteProfile(self, profile_name):
        if profile_name not in self.profile_names: return False
        self.profile_names.remove(profile_name)
        with self.db.getConn() as conn:
            try:
                conn.execute("DELETE FROM profiles WHERE name = ?", (profile_name,))
            except sqlite3.IntegrityError:
                return False

        return True

    def duplicateProfile(self, profile_name):
        if profile_name not in self.profile_names: return None
        new_name = generateUniqueName(self.profile_names, profile_name)

        with self.db.getConn() as conn:
            cursor = conn.cursor()

            # Select original profile's id
            cursor.execute("SELECT id FROM profiles WHERE name = ?", (profile_name,))
            row = cursor.fetchone()
            if not row: return None
            original_id = row["id"]

            # Create new profile and grab that ID
            cursor.execute("INSERT INTO profiles (name) VALUES (?)", (new_name,))
            new_id = cursor.lastrowid

            # Copy relationships
            cursor.execute("""
                           INSERT INTO profile_tasks (profile_id, task_id, repeat, is_enabled)
                           SELECT ?, task_id, repeat, is_enabled
                           FROM profile_tasks
                           WHERE profile_id = ?
                           """, (new_id, original_id))

            # Copy variables
            copyVarsToNewProfile(cursor, original_id, new_id)

            conn.commit()

        self.profile_names.add(new_name)

        return new_name


    def createRelationship(self, task_id, repeat=False, enabled=True):
        if task_id in self.task_relationships: return
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

    def removeRelationship(self, task_id):
        if task_id in self.task_relationships:
            del self.task_relationships[task_id]

            with self.db.getConn() as conn:
                conn.execute("DELETE FROM profile_tasks WHERE task_id = ?", (task_id,))
                conn.commit()

    def load(self, profile_name: str):
        is_first_load = self.name is None
        self.name = profile_name
        self.id = self._getOrCreateId()

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

            if is_first_load:
                rows = conn.execute("SELECT * FROM profiles ORDER BY updated_at")
                for row in rows:
                    self.profile_names.add(row["name"])

        self.vars.load(self.id)
        if is_first_load:
            self.tasks.initialLoad()

        self.loaded.emit(is_first_load)
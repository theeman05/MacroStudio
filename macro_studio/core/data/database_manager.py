import sqlite3, os
from macro_studio.core.utils.logger import global_logger


class DatabaseManager:
    _instance = None
    DB_NAME = "macro_studio.db"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.initDB()
        return cls._instance

    def getConn(self):
        db_path = os.path.join(os.getcwd(), self.DB_NAME)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def initDB(self):
        """Create tables if they don't exist."""
        conn = self.getConn()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                            CREATE TABLE IF NOT EXISTS profiles (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT UNIQUE NOT NULL,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                           """)

            cursor.execute("""
                            CREATE TABLE IF NOT EXISTS tasks (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT,
                                steps TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                           """)

            cursor.execute("""
                            CREATE TABLE IF NOT EXISTS profile_tasks (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                profile_id INTEGER NOT NULL,
                                task_id INTEGER NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                
                                repeat BOOLEAN DEFAULT 0,
                                is_enabled BOOLEAN DEFAULT 1,

                                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                                UNIQUE(profile_id, task_id)
                            )
                           """)

            cursor.execute("""
                            CREATE TABLE IF NOT EXISTS variables (
                                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                                 profile_id INTEGER,
                                 key TEXT,
                                 value TEXT,
                                 data_type TEXT,
                                 hint TEXT,
                                 FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                                 UNIQUE(profile_id, key)
                            )
                           """)

            conn.commit()
        except Exception as e:
            print("INIT ERROR", e)
            global_logger.logError(f"Database Init Error: {e}")
        finally:
            conn.close()
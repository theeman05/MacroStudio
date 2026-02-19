import json
import os
from .logger import global_logger

class FileIO:
    @staticmethod
    def exportData(data: dict | list, filepath: str) -> bool:
        """
        Universally exports any JSON-serializable data to disk.
        Returns True if successful, False if it failed.
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            global_logger.logError(f"FileIO Export Error ({filepath}): {e}")
            return False

    @staticmethod
    def importData(filepath: str) -> dict | list | None:
        """
        Universally imports JSON data from disk.
        Returns the raw data, or None if the read failed.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            global_logger.logError(f"FileIO Export Error ({filepath}): {e}")
            return None

    @staticmethod
    def deleteFile(filepath: str) -> bool:
        """
        Deletes a file from disk.
        Returns True if successful, False otherwise.
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        except Exception as e:
            global_logger.logError(f"FileIO Delete Error ({filepath}): {e}")
            return False
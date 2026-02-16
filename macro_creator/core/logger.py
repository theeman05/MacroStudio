from traceback import format_exc
from PySide6.QtCore import QObject, Signal

from .types_and_enums import LogLevel, LogPacket, LogErrorPacket


class _AppLogger(QObject):
    log_emitted = Signal(object) # The log message

    def log(self, *args, level: LogLevel = LogLevel.INFO, task_id: int = -1):
        """
        Sends a structured log packet to the ui.
        Args:
            args: The objects to be printed in the log. If mode is not ERROR, will cast the args automatically.
            level: The log level to display at.
            task_id: The task id associated with the packet. If -1, logs as System
        """
        payload = LogPacket(parts=args, level=level, task_id=task_id)
        self.log_emitted.emit(payload)

    def logError(self, error_msg, include_trace=True, task_id: int = -1):
        """Sends a specialized LogErrorPacket object to the ui."""
        trace = None
        if include_trace:
            trace = format_exc()

            # Protect against the "NoneType" trap if they called it outside an except block
            if not trace or trace.strip() == "NoneType: None":
                trace = None

        payload = LogErrorPacket(message=error_msg, traceback=trace, task_id=task_id)
        self.log_emitted.emit(payload)

global_logger = _AppLogger()
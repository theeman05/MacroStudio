from traceback import format_exc
from PySide6.QtCore import QObject, Signal

from macro_studio.core.types_and_enums import LogLevel, LogPacket, LogErrorPacket


class _AppLogger(QObject):
    log_emitted = Signal(object) # The log packet

    def log(self, *args, level: LogLevel= LogLevel.INFO, task_name: int|str= -1):
        """
        Sends a structured log packet to the ui.
        Args:
            args: The objects to be printed in the log. If mode is not ERROR, will cast the args automatically.
            level: The log level to display at.
            task_name: The task name associated with the packet. If -1, logs as System
        """
        payload = LogPacket(parts=args, level=level, task_name=task_name)
        self.log_emitted.emit(payload)

    def logError(self, error_msg, include_trace=True, task_name: int|str= -1):
        """
        Sends a structured error packet to the ui.
        Args:
            error_msg: The error message.
            include_trace: If the trace should be captured.
            task_name: The task name associated with the packet. If -1, logs as System
        """
        trace = None
        if include_trace:
            trace = format_exc()

            # Protect against the "NoneType" trap if they called it outside an except block
            if not trace or trace.strip() == "NoneType: None":
                trace = None

        payload = LogErrorPacket(message=error_msg, traceback=trace, task_name=task_name)
        self.log_emitted.emit(payload)

global_logger = _AppLogger()
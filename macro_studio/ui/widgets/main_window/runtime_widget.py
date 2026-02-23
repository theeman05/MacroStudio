from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer, QElapsedTimer, Qt


class RuntimeWidget(QLabel):
    """A self-contained, resumable timer widget for the status bar."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. Logic Objects
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.updateDisplay)
        self.refresh_timer.setInterval(100)

        self.elapsed_timer = QElapsedTimer()

        # 2. State Tracking Variables
        self.accumulated_time = 0
        self.is_running = False

        self.setStyleSheet("""
            font-family: 'Consolas', 'Roboto Mono', monospace;
            font-size: 12px;
            color: #b0b0b0;
            padding-right: 10px;
            padding-left: 10px;
            margin-right: 10px;
            margin-left: 10px;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("00:00:00")

    def startCounting(self):
        """Wipes previous memory and starts a fresh clock."""
        if self.is_running: return
        self.accumulated_time = 0
        self.is_running = True
        self.elapsed_timer.start()
        self.refresh_timer.start()

        self.setStyleSheet("font-family: monospace; color: #4caf50; font-weight: bold; margin-right: 10px; margin-left: 10px;")

    def pauseCounting(self):
        """Banks the currently elapsed time and halts the UI updates."""
        if not self.is_running:
            return

        self.is_running = False
        self.refresh_timer.stop()

        # Bank the time that passed during this specific run
        self.accumulated_time += self.elapsed_timer.elapsed()

        # Visual cue: Turn amber to show it is suspended
        self.setStyleSheet("font-family: monospace; color: #ff9800; font-weight: bold; margin-right: 10px; margin-left: 10px;")

    def resumeCounting(self):
        """Restarts the hardware clock without wiping the banked time."""
        if self.is_running:
            return

        self.is_running = True
        self.elapsed_timer.start()  # Starts a fresh hardware count
        self.refresh_timer.start()

        self.setStyleSheet("font-family: monospace; color: #4caf50; font-weight: bold; margin-right: 10px; margin-left: 10px;")

    def stopCounting(self):
        """Completely halts the timer, keeping the final total on screen."""
        if self.is_running:
            self.pauseCounting()  # Safely bank the final milliseconds

        self.setStyleSheet("font-family: monospace; color: #b0b0b0; margin-right: 10px; margin-left: 10px;")

    def updateDisplay(self):
        """Calculates total time (banked + current) and formats it."""
        current_ms = self.accumulated_time
        if self.is_running:
            current_ms += self.elapsed_timer.elapsed()

        seconds = (current_ms // 1000) % 60
        minutes = (current_ms // 60000) % 60
        hours = (current_ms // 3600000)

        time_str = f"{hours:02}:{minutes:02}:{seconds:02}"
        self.setText(time_str)
import time


class PauseState:
    def __init__(self):
        self.active = False  # Is it currently paused?
        self.is_hard = False  # Is it a hard pause (cleanup required)?
        self._start_time = 0.0  # When did the pause start?

    def trigger(self, hard: bool = False):
        """Start a pause."""
        self.active = True
        self.is_hard = hard
        self._start_time = time.perf_counter()

    def clear(self) -> float | None:
        """
        End the pause and return how long it lasted.
        :return: The duration paused for in seconds or None if not paused.
        """
        if not self.active:
            return None

        duration = time.perf_counter() - self._start_time

        # Reset state
        self.active = False
        self.is_hard = False
        self._start_time = 0.0

        return duration

"""
Hard Pausable Macro Example
---------------------------
This example demonstrates how to create a robust, long-running task class
that correctly handles the Engine's "Hard Pause" and "Stop" signals.

Key Concepts:
1. Persistence: Using a class allows you to store state (self.counter) easily.
2. Hard Pause Safety: catching TaskInterruptedException to prevent loop breakage.
3. Cleanup: Using 'finally' to ensure resources are closed on Stop.
"""

from macro_creator import MacroCreator, TaskInterruptedException, taskSleep, taskWaitForResume

class DatabaseUpdaterTask:
    """
    A simulated task that processes records in a loop.
    It demonstrates safe pausing and graceful shutdown.
    """

    def __init__(self):
        self.records_processed = 0
        self.is_connected = False

    def connectDB(self, controller):
        """Simulate opening a resource."""
        controller.log("🔌 Connecting to database...")
        self.is_connected = True
        yield from taskSleep(0.5)  # Slight delay to simulate connection time

    def disconnectDB(self, controller):
        """Simulate closing a resource."""
        if self.is_connected:
            controller.log("🔌 Disconnecting from database...")
            self.is_connected = False

    def run(self, controller):
        """
        The main entry point called by the Engine.
        """
        yield from self.connectDB(controller)

        try:
            # --- MAIN LOOP ---
            while self.records_processed < 20:

                # 1. THE SAFE SLEEP PATTERN
                # We wrap the sleep in a try/except block.
                # If we don't, a Pause signal would crash this 'while' loop immediately!
                try:
                    controller.log(f"Processing record #{self.records_processed}...")

                    # Simulate work (takes 1 second)
                    yield from taskSleep(1.0)

                    self.records_processed += 1

                except TaskInterruptedException:
                    # 2. HANDLE PAUSE
                    # The user clicked "Pause". We must explicitly wait here.
                    controller.log("⏸️ Task Paused safely. Waiting for resume...")

                    # This yields control until the task is resumed
                    yield from taskWaitForResume()

                    controller.log("▶️ Resuming task loop...")
                    # When this returns, the loop continues naturally at the top

            controller.log("✅ Task completed successfully!")

        finally:
            # 3. HANDLE STOP / CLEANUP
            # This block runs if:
            # - The loop finishes normally.
            # - The script crashes (Error).
            # - The user clicks STOP (TaskAbortException).
            self.disconnectDB(controller)


# --- Engine Registration ---
# If your engine expects a function, you can wrap the class like this:
def runSafeTask(controller):
    task = DatabaseUpdaterTask()
    yield from task.run(controller)

if __name__ == '__main__':
    creator = MacroCreator("Database Updater Macro")

    creator.addRunTask(runSafeTask)

    creator.launch()
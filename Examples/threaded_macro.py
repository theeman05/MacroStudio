import time
from macro_creator import MacroCreator, MacroAbortException, MacroHardPauseException, macroRunTaskInThread, macroSleep

class ThreadMacro:
    def __init__(self, creator: MacroCreator):
        self.engine = creator

        # Add run tasks to the creator
        self.thread_task_controller = creator.addRunTask(self.threadedTask)
        creator.addRunTask(self.threadHardPauser)

    def _taskInThread(self):
        """
        A simple example of a task running in its own thread.
        It demonstrates how to handle 'Hard Pauses' (Safety Stops) and Aborts correctly without crashing.
        """
        try:
            controller = self.thread_task_controller

            # We want to sleep for exactly 5 seconds
            # We calculate the target end time immediately
            target_duration = 5.0
            end_time = time.time() + target_duration

            self.engine.ui.log(f"[Thread] Attempting to sleep for {target_duration} seconds...")
            try:
                # Access resources here if needed
                self.engine.ui.log(f"[Thread] Accessing resources...")
                # Sleep the thread for the target duration
                controller.sleep(target_duration)
            except MacroHardPauseException:
                self.engine.ui.log("[Thread] PAUSED!")
            finally:
                # Always clean up resources here if needed
                self.engine.ui.log("[Thread] Cleaning up resources...")

            # We could be paused after breaking out of the previous block, so wait until we're resumed
            controller.waitForResume()

            self.engine.ui.log(
                f"[Thread] Sleep Complete! Total elapsed real time: {time.time() - (end_time - target_duration):.2f}s")
        except MacroAbortException:
            # This handles any aborts from controller.sleep and controller.waitForResume
            self.engine.ui.log("[Thread] STOPPED! Exiting task immediately.")

    def threadedTask(self):
        # Create and start thread task with the argument being the task controller
        self.engine.ui.log("Starting background work...")

        # Yield while the thread task is running
        yield from macroRunTaskInThread(self._taskInThread)

    def threadHardPauser(self):
        # Let's attempt to hard pause the threaded task!
        yield from macroSleep(1)
        # After a second of running, pause the threaded task
        self.engine.ui.log("Hard pausing the thread controller!")
        self.thread_task_controller.pause(True)
        yield from macroSleep(2)
        # After two seconds, unpause the threaded task so it can finish
        # Since we were hard paused, the remaining time from the thread's sleep was discarded and the task ends early
        self.thread_task_controller.resume()

import time
from macro_studio import MacroStudio, ThreadController, TaskAbortException, TaskInterruptedException, taskSleep


def _taskInThread(controller: ThreadController):
    """
    A simple example of a task running in its own thread.
    It demonstrates how to handle 'Interrupted Pauses' (Safety Stops) and Aborts correctly without crashing.
    """
    try:
        # We want to sleep for exactly 5 seconds
        # We calculate the target end time immediately
        target_duration = 5.0
        end_time = time.time() + target_duration

        controller.log(f"[Thread] Attempting to sleep for {target_duration} seconds...")
        try:
            # Access resources here if needed
            controller.log(f"[Thread] Accessing resources...")
            # Sleep the thread for the target duration
            controller.sleep(target_duration)
        except TaskInterruptedException:
            controller.log("[Thread] INTERRUPTION CAUGHT!")
        finally:
            # Always clean up resources here if needed
            controller.log("[Thread] Cleaning up resources...")

        # We could be paused after breaking out of the previous block, so wait until we're resumed
        controller.waitForResume()

        controller.log(
            f"[Thread] Sleep Complete! Total elapsed real time: {time.time() - (end_time - target_duration):.2f}s")
    except TaskAbortException:
        # This handles any aborts from controller.sleep and controller.waitForResume
        # We generally don't want to use this, but if you do make sure to return immediately after to not have hanging threads
        controller.log("[Thread] STOPPED! Exiting task immediately.")

class ThreadMacro:
    def __init__(self, creator: MacroStudio):
        self.engine = creator

        # Add run tasks to the creator
        self.thread_task_controller = creator.addThreadTask(_taskInThread)
        self.pauser_controller = creator.addBasicTask(self.threadHardPauser)

    def threadHardPauser(self, controller):
        # Let's attempt to interrupt the threaded task!
        yield from taskSleep(1)
        # After a second of running, interrupt the threaded task
        controller.log("Interrupting the thread controller!")
        self.thread_task_controller.pause(True)
        yield from taskSleep(2)
        # After two seconds, unpause the threaded task so it can finish
        # Since we were hard paused, the remaining time from the thread's sleep was discarded and the task ends early
        self.thread_task_controller.resume()

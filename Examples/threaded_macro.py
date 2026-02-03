import threading
from macro_creator import MacroCreator, TaskController, macroSleep


# This is the task that will be in the thread
def threadTask(controller: TaskController):
    print("Wow, I am running in a separate thread!")
    controller.sleep(5)
    print("The thread has woken back up ;)")

class ThreadMacro:
    def __init__(self, creator: MacroCreator):
        self.engine = creator

        # Add run tasks to the creator
        self.thread_task_controller = creator.addRunTask(self.threader)

    def threader(self):
        # Create and start thread task with the argument being the task controller
        t = threading.Thread(target=threadTask, args=self.thread_task_controller, daemon=True)
        t.start()

        # Let the engine know we have a task running still while the thread is still running
        while self.engine.isRunningMacros() and t.is_alive():
            yield from macroSleep(1)
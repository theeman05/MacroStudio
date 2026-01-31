import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine import MacroCreator
    from task_controller import TaskController

# This is the task that will be in the thread
def threadTask(controller: "TaskController"):
    print("Wow, I am running in a separate thread!")
    controller.sleep(5)
    print("The thread has woken back up ;)")

class ThreadMacro:
    def __init__(self, creator: "MacroCreator"):
        self.engine = creator

        # Add run tasks to the creator
        self.thread_task_controller = creator.addRunTask(self.threader)

    def threader(self):
        # Create and start thread task with the argument being the task controller
        threading.Thread(target=threadTask, args=self.thread_task_controller, daemon=True).start()
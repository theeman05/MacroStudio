import time
from typing import TYPE_CHECKING
from utils import macroSleep

if TYPE_CHECKING:
    from engine import MacroCreator


def anotherTask():
    print("I am going to sleep as another task")
    start = time.time()
    yield from macroSleep(5)
    print(f"Total Elapsed: {time.time() - start}")


class BasicMacro:
    def __init__(self, creator: "MacroCreator"):
        self.engine = creator

        # Add run tasks to the creator
        self.another_task_controller = creator.addRunTask(anotherTask)
        creator.addRunTask(self.someTask)

    def someTask(self):
        print("I am going to sleep")
        yield from macroSleep(1)
        print("Stopping another")
        self.another_task_controller.pause()
        yield from macroSleep(1)
        print("resuming other")
        self.another_task_controller.resume()
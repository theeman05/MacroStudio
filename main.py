from engine import MacroCreator, ClickMode, macroWait
import time

if __name__ == "__main__":
    mackrel_test = MacroCreator()

    def another_task():
        print("I am going to sleep as another task")
        start = time.time()
        yield from macroWait(5)
        print(f"Total Elapsed: {time.time() - start}")

    def some_task():
        print("I am going to sleep")
        yield from macroWait(1)
        print("Stopping another")
        another_controller.pause()
        yield from macroWait(1)
        print("resuming other")
        another_controller.resume()

    mackrel_test.addSetupStep("idk", ClickMode.SET_BUTTON, "Select SOmewhere")

    another_controller = mackrel_test.addRunTask(another_task)
    mackrel_test.addRunTask(some_task)

    mackrel_test.mainLoop()

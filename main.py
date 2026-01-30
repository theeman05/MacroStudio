from engine import MacroCreator, ClickMode, macroWait

if __name__ == "__main__":
    mackrel_test = MacroCreator()

    def some_task():
        print("I am going to sleep")
        yield from macroWait(1)
        print("Stopping another")
        mackrel_test.stopTask("another_task")
        # mackrel_test.pauseTask("another_task")
        # yield from macroWait(4)
        # mackrel_test.resumeTask("another_task")

    def another_task():
        print("I am going to sleep as another task")
        yield from macroWait(5)
        print("We are done :D", mackrel_test.setup_vars["idk"])

    mackrel_test.addSetupStep("idk", ClickMode.SET_BUTTON, "Select SOmewhere")

    mackrel_test.addRunTask(some_task)
    mackrel_test.addRunTask(another_task, "another_task")

    mackrel_test.mainLoop()
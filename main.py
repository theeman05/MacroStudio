from Examples.threaded_macro import ThreadMacro
from macro_creator import MacroCreator
from Examples.basic_macro import BasicMacro

if __name__ == "__main__":
    creator = MacroCreator()

    # Add steps and tasks from BasicMacro
    ThreadMacro(creator)

    creator.launch()

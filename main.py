from macro_engine import MacroCreator
from Examples.basic_macro import BasicMacro

if __name__ == "__main__":
    creator = MacroCreator()

    # Add steps and tasks from BasicMacro
    BasicMacro(creator)

    creator.launch()

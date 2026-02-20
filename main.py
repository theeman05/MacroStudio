from macro_studio import MacroStudio
from Examples.basic_macro import BasicMacro

if __name__ == "__main__":
    studio = MacroStudio("Macro Main Tester")

    # Add steps and tasks from BasicMacro
    BasicMacro(studio)

    studio.launch()

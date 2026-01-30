from macrocreator import MacroCreator, ClickMode, MacroAbortException, captureScreenText
from pynput.mouse import Controller as MouseController
from pynput.keyboard import Controller as KeyboardController

mouse_controller = MouseController()
keyboard_controller = KeyboardController()

castle_macro = MacroCreator()
castle_macro.addSetupStep("start_point", ClickMode.SET_BUTTON, "Select start/stop button")
castle_macro.addSetupStep("wave_rect", ClickMode.SET_BOUNDS, "Click and drag to set wave bounds")

def safeHoldKey(key, duration):
    """Safely hold a key for the given duration, always releases the key"""
    keyboard_controller.press(key)
    try:
        castle_macro.macroWait(duration)
    finally:
        keyboard_controller.release(key)

def moveCharacter():
    """Periodically moves the character while running the macros"""
    try:
        while castle_macro.isRunningMacros():
            safeHoldKey("W", 2)
            safeHoldKey("A", 4)
            safeHoldKey("S", 2)
            safeHoldKey("D", 4)
    except MacroAbortException:
        # Macro was aborted during waiting
        return

def monitorMatchStatus():
    """Monitors the match status and starts or stops the game"""
    pass

castle_macro.addRunTask(moveCharacter)

if __name__ == '__main__':
    castle_macro.mainLoop()
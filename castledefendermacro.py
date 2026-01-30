import cv2, pytesseract, mss
#from main import MacroCreator, ClickMode, macroWait
from enum import Enum, auto
from pynput.mouse import Controller as MouseController
from pynput.keyboard import Controller as KeyboardController
from PyQt5.QtCore import QRect
from PIL import Image
import numpy as np

class StepKey(Enum):
    START_POINT = auto()
    WAVE_RECT = auto()

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'

mouse_controller = MouseController()
keyboard_controller = KeyboardController()

castle_macro = MacroCreator()

castle_macro.addSetupStep(StepKey.START_POINT, ClickMode.SET_BUTTON, "Select start/stop button")
castle_macro.addSetupStep(StepKey.WAVE_RECT, ClickMode.SET_BOUNDS, "Click and drag to set wave bounds")

def captureScreenText(bounds: QRect) -> str:
    """Capture a screenshot within the bounds and return the text within it"""
    region = {
        "top": bounds.top(),
        "left": bounds.left(),
        "width": bounds.width(),
        "height": bounds.height(),
    }
    with mss.mss() as sct:
        screenshot = sct.grab(region)

    np_img = np.array(screenshot)
    bgr_img = np_img[..., :3]
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    # Use binary thresh to improve ocr accuracy
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    return pytesseract.image_to_string(Image.fromarray(binary))

def safeHoldKey(key, duration: float):
    """Safely hold a key for the given duration (in seconds), always releases the key"""
    keyboard_controller.press(key)
    try:
        yield from macroWait(duration)
    finally:
        keyboard_controller.release(key)

def moveCharacter():
    """Periodically moves the character while running the macros"""
    while castle_macro.isRunningMacros():
        yield from safeHoldKey("W", 2)
        yield from safeHoldKey("A", 4)
        yield from safeHoldKey("S", 2)
        yield from safeHoldKey("D", 4)

def monitorMatchStatus():
    """Monitors the match status and starts or stops the game"""
    pass

castle_macro.addRunTask(moveCharacter)

if __name__ == '__main__':
    castle_macro.mainLoop()
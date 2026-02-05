import cv2, pytesseract, mss, pydirectinput
import numpy as np
from contextlib import contextmanager
from PyQt6.QtCore import QRect, QPoint
from PIL import Image
from pydirectinput import MOUSE_PRIMARY

from macro_creator.types_and_enums import MacroHardPauseException

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'

pydirectinput.PAUSE = 0.0

def macroSleep(duration: float=.01):
    """
    Non-blocking, yields control back to the scheduler for 'duration' seconds.

    Usage in task: yield from macroSleep(2.0).
    """
    yield duration

def macroWaitForResume():
    """
    Non-blocking, yields until the controller's hard-pause state is cleared.

    Usage in task: yield from macroWaitForResume().
    """
    yield None

def captureScreenText(bounds: QRect) -> str:
    """Capture a screenshot within the bounds and return the text within it."""
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
    return pytesseract.image_to_string(Image.fromarray(binary)).strip()

@contextmanager
def holdKey(key_name: str):
    """Context manager that holds a key and guarantees its release."""
    pydirectinput.keyDown(key_name)
    try:
        yield  # Run the block inside the 'with' statement
    finally:
        pydirectinput.keyUp(key_name)

def macroHoldKey(key_name: str, duration: float):
    """
    Holds a key for some duration via yielding and guarantees its release.

    If the task is hard paused, the key will be released immediately, but will still wait for resume by yielding

    Usage in task: yield from macroHoldKey("a", 2.0).
    :param key_name: The name of the key to hold down.
    :param duration: Duration to hold for (in seconds).
    """
    try:
        with holdKey(key_name):
            yield from macroSleep(duration)
    except MacroHardPauseException:
        yield from macroWaitForResume()

@contextmanager
def mouseClick(coords: QPoint=None, button: str=MOUSE_PRIMARY):
    """Context manager that holds a clicks at the coordinates and guarantees its mouse release."""
    x = y = None
    if coords: x, y = coords.x(), coords.y()
    pydirectinput.mouseDown(x, y, button, tween=.05)
    try:
        yield  # Run the block inside the 'with' statement
    finally:
        if coords:
            pydirectinput.mouseUp(x + np.random.randint(-5, 5), y + np.random.randint(-5, 5), button, tween=.05)
        else:
            pydirectinput.mouseUp(None, None, button)

def macroMouseClick(coords: QPoint=None, button: str=MOUSE_PRIMARY):
    """
    Clicks at the given coordinates with the button, yields shortly, then releases the mouse.

    If the task is hard paused, the mouse will be released immediately, but will still wait for resume by yielding

    Usage in task: yield from macroMouseClick(QPoint(0,0)).
    :param coords: Coordinates to click at.
    :param button: Button to use.
    """
    try:
        with mouseClick(coords, button):
            yield from macroSleep(.1)
    except MacroHardPauseException:
        yield from macroWaitForResume()
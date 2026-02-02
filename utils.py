import cv2, pytesseract, mss, pydirectinput
import numpy as np
from PyQt6.QtCore import QRect, QPoint
from PIL import Image
from pydirectinput import MOUSE_PRIMARY

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'

pydirectinput.PAUSE = 0.0

def macroSleep(duration: float=.01):
    """
    Non-blocking, yields control back to the scheduler for 'duration' seconds.
    Usage in task: yield from self.macroSleep(2.0).
    """
    yield duration

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

def safeClickKey(key: str, duration: float):
    """
    Holds a key for some duration by yielding.
    :param key: The key string to hold down.
    :param duration: Duration to hold for (in seconds).
    """
    pydirectinput.keyDown(key)
    try:
        yield from macroSleep(duration)
    finally:
        pydirectinput.keyUp(key)

def clickPosition(coords: QPoint, button: str=MOUSE_PRIMARY):
    """
    Clicks at the given coordinates with the button, yields shortly, then releases the mouse.
    :param coords: Coordinates to click at.
    :param button: Button to use.
    """
    x, y = coords.x(), coords.y()
    pydirectinput.mouseDown(x, y, button, tween=.05)
    try:
        yield from macroSleep(.1)
    finally:
        # Offset slightly so there's a little movement after
        pydirectinput.mouseUp(x + np.random.randint(-5, 5), y + np.random.randint(-5, 5), button, tween=.1)
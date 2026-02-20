import pydirectinput, threading
import numpy as np
from contextlib import contextmanager
from PySide6.QtCore import QPoint
from pydirectinput import MOUSE_PRIMARY

from macro_studio.core.types_and_enums import TaskInterruptedException

pydirectinput.PAUSE = 0.0

def taskSleep(duration: float=.01):
    """
    Non-blocking, yields control back to the worker for 'duration' seconds.

    Usage in task: yield from **taskSleep(2.0)**.
    Raises:
        TaskInterruptedException: If hard-paused while sleeping.
    """
    yield duration

def taskWaitForResume():
    """
    Non-blocking, yields until the controller's hard-pause state is cleared.

    Usage in task: yield from **taskWaitForResume()**.
    """
    yield None

@contextmanager
def holdKey(key_name: str):
    """Context manager that holds a key and guarantees its release."""
    pydirectinput.keyDown(key_name)
    try:
        yield  # Run the block inside the 'with' statement
    finally:
        pydirectinput.keyUp(key_name)

def taskHoldKey(key_name: str, duration: float):
    """
    Holds a key for some duration via yielding and guarantees its release.

    If the task is hard paused, the key will be released immediately, but will still wait for resume by yielding

    Usage in task: yield from **taskHoldKey("a", 2.0)**.
    Args:
        key_name: The name of the key to hold down.
        duration: Duration to hold for (in seconds).
    """
    try:
        with holdKey(key_name):
            yield from taskSleep(duration)
    except TaskInterruptedException:
        yield from taskWaitForResume()

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

def taskMouseClick(coords: QPoint=None, button: str=MOUSE_PRIMARY):
    """
    Clicks at the given coordinates with the button, yields shortly, then releases the mouse.

    If the task is hard paused, the mouse will be released immediately, but will still wait for resume by yielding

    Usage in task: yield from **taskMouseClick(QPoint(0,0))**.
    Args:
        coords: Coordinates to click at.
        button: The mouse button to use.
    """
    try:
        with mouseClick(coords, button):
            yield from taskSleep(.1)
    except TaskInterruptedException:
        yield from taskWaitForResume()

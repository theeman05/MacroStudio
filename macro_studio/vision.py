import cv2, pytesseract, mss
import numpy as np
from PySide6.QtCore import QRect
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract'

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
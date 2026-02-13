from typing import Union
import qtawesome as qta
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QTableWidgetItem, QLineEdit, QWidget, QPushButton, QLabel

EMPTY_VALUE_STR = "<Empty>"
DEFAULT_ICON_COLOR = "#E7E7E7"
SELECTED_COLOR = "#1158c7"
SELECTED_HOVER_COLOR = "#007FF4"

class HoverButton(QPushButton):
    """A button that swaps its icon color when hovered."""
    def __init__(self, icon_name, normal_color=DEFAULT_ICON_COLOR, hover_color=SELECTED_COLOR, size=20, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 1. Pre-generate both states to ensure instant swapping
        self.icon_normal = qta.icon(icon_name, color=normal_color)
        self.icon_hover = qta.icon(icon_name, color=hover_color)

        # 2. Set Default State
        self.setIcon(self.icon_normal)
        self.setIconSize(QSize(size, size))
        self.setFixedSize(size, size)

    def enterEvent(self, event):
        self.setIcon(self.icon_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(self.icon_normal)
        super().leaveEvent(event)

def updateItemPlaceholder(main_widget: "QWidget", item: Union["QTableWidgetItem", "QLineEdit", "QPushButton"], text: str | None=None, placeholder: str=EMPTY_VALUE_STR):
    """If text is None, sets the item to have placeholder text"""
    font = item.font()
    if text is None:
        item.setText(placeholder)
        font.setItalic(True)
        item.setForeground(QBrush(QColor("gray")))
    else:
        item.setText(text)
        font.setItalic(False)
        item.setForeground(main_widget.palette().text())
    item.setFont(font)

def setBtnState(btn, state_value):
    btn.setProperty("state", state_value)
    btn.style().unpolish(btn)
    btn.style().polish(btn)

def createIconLabel(icon_name: str, color: str=DEFAULT_ICON_COLOR, size=(30,30)):
    size_x, size_y = size
    lbl_icon = QLabel()
    lbl_icon.setFixedSize(size_x, size_y)
    lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    icon_obj = qta.icon(icon_name, color=color)
    pixmap = icon_obj.pixmap(size_x - 5, size_y - 5)
    lbl_icon.setPixmap(pixmap)

    return lbl_icon
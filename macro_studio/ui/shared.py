from typing import Union
import qtawesome as qta
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QTableWidgetItem, QLineEdit, QWidget, QPushButton, QLabel

EMPTY_VALUE_STR = "<Empty>"

class IconColor:
    DEFAULT = "#E7E7E7"
    DISABLED = "#606060"
    DISABLED_HOVER = "#929292"
    SELECTED = "#1158c7"
    SELECTED_HOVER = "#007FF4"


class HoverButton(QPushButton):
    """A standard button that swaps its icon color when hovered."""

    def __init__(self, icon_name, normal_color=IconColor.DEFAULT, hover_color=IconColor.SELECTED_HOVER,
                 tooltip: str = None, size=20, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.icon_normal = qta.icon(icon_name, color=normal_color)
        self.icon_hover = qta.icon(icon_name, color=hover_color)

        self.setIcon(self.icon_normal)
        self.setIconSize(QSize(size, size))
        self.setFixedSize(size, size)

        if tooltip:
            self.setToolTip(tooltip)

    def enterEvent(self, event):
        if self.isEnabled():
            self.setIcon(self.icon_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(self.icon_normal)
        super().leaveEvent(event)


class ToggleHoverButton(HoverButton):
    """A checkable hover button with dynamic tooltips and checked states."""

    def __init__(self, icon_name, checked_icon_name=None, normal_color=IconColor.DISABLED, hover_color=IconColor.DISABLED_HOVER,
                 checked_color=IconColor.SELECTED, checked_hover_color=IconColor.SELECTED_HOVER,
                 normal_tooltip: str = None, checked_tooltip: str = None, size=20, parent=None):
        super().__init__(icon_name, normal_color, hover_color, normal_tooltip, size, parent)

        checked_icon_name = checked_icon_name or icon_name
        self.icon_checked = qta.icon(checked_icon_name, color=checked_color)
        self.icon_checked_hover = qta.icon(checked_icon_name, color=checked_hover_color)

        self.normal_tooltip = normal_tooltip
        self.checked_tooltip = checked_tooltip

        if normal_tooltip: self.setToolTip(normal_tooltip)

        self.setCheckable(True)
        self.toggled.connect(self._onToggled)

    def _onToggled(self, is_checked: bool):
        """Handles visual and tooltip updates when the toggle state changes."""

        if is_checked and self.checked_tooltip:
            self.setToolTip(self.checked_tooltip)
        elif not is_checked and self.normal_tooltip:
            self.setToolTip(self.normal_tooltip)

        if self.underMouse():
            self.setIcon(self.icon_checked_hover if is_checked else self.icon_hover)
        else:
            self.setIcon(self.icon_checked if is_checked else self.icon_normal)

    def enterEvent(self, event):
        if self.isEnabled():
            self.setIcon(self.icon_checked_hover if self.isChecked() else self.icon_hover)
        # We bypass HoverButton's enterEvent to prevent it from overwriting our checked logic
        QPushButton.enterEvent(self, event)

    def leaveEvent(self, event):
        self.setIcon(self.icon_checked if self.isChecked() else self.icon_normal)
        QPushButton.leaveEvent(self, event)

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

def createIconLabel(icon_name: str, color: str=IconColor.DEFAULT, size=(30,30)):
    size_x, size_y = size
    lbl_icon = QLabel()
    lbl_icon.setFixedSize(size_x, size_y)
    lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    icon_obj = qta.icon(icon_name, color=color)
    pixmap = icon_obj.pixmap(size_x - 5, size_y - 5)
    lbl_icon.setPixmap(pixmap)

    return lbl_icon

def _resetStyle(item, origin_style):
    item.setStyleSheet(origin_style)

def flashError(item):
    original_style = item.styleSheet()
    item.setStyleSheet("background-color: #FFCDD2;")
    QTimer.singleShot(250, lambda: _resetStyle(item, original_style))
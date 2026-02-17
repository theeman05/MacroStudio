from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QEvent


class LockOverlay(QWidget):
    def __init__(self, parent_widget: QWidget, message: str = "Tasks cannot be edited while running macros"):
        super().__init__(parent_widget)

        # Block clicks from passing through just in case
        self.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation, True)

        # Create and style the centered text
        self.label = QLabel(message)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("""
            color: white; 
            font-size: 18px; 
            font-weight: bold; 
            background-color: transparent;
        """)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)

        parent_widget.installEventFilter(self)
        self.resize(parent_widget.size())

        self.hide()

    def eventFilter(self, obj, event):
        if obj == self.parent() and event.type() == QEvent.Type.Resize:
            self.resize(event.size())
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        # Dark background
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200))

    def show(self, /):
        self.raise_()
        super().show()
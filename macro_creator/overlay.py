from PySide6.QtWidgets import QWidget, QFrame, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QPen, QColor, QKeyEvent
from typing import TYPE_CHECKING
from .types_and_enums import CaptureMode

if TYPE_CHECKING:
    from .gui_main import MainWindow

TOOLBAR_STYLE = """
QFrame#OverlayToolbar {
    background-color: #333333;
    border: 1px solid #555;
    border-radius: 5px;
    color: white;
}
QLabel {
    color: white;
    font-weight: bold;
    padding: 0 10px;
    font-size: 14px;
}
QPushButton {
    background-color: transparent;
    border: none;
    color: #bbb;
    font-weight: bold;
    font-size: 16px;
    padding: 5px 10px;
}
QPushButton:hover {
    color: #ff5555; /* Red on hover */
    background-color: #444;
    border-radius: 3px;
}
"""


class TransparentOverlay(QWidget):
    def __init__(self, main_window: "MainWindow"):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # Prevents showing in taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._click_through = True
        self.main_window = main_window

        self._setup_toolbar()

        screen = main_window.app.primaryScreen()
        self.setGeometry(screen.geometry())

        self.show()
        self.setClickThrough(True)
        self.render_geometry = set()

        self.current_mode: CaptureMode | None = None
        self.start_pos = None
        self.selection_rect: QRect | None = None
        self.highlighted_config = None

    def _setup_toolbar(self):
        """Creates the floating bar at the top center"""
        self.toolbar = QFrame(self)
        self.toolbar.setObjectName("OverlayToolbar")
        self.toolbar.setStyleSheet(TOOLBAR_STYLE)

        layout = QHBoxLayout(self.toolbar)
        layout.setContentsMargins(5, 5, 5, 5)

        self.lbl_instruction = QLabel("Select Region")
        layout.addWidget(self.lbl_instruction)

        self.btn_cancel = QPushButton("X")
        self.btn_cancel.clicked.connect(self.cancelCapture)
        layout.addWidget(self.btn_cancel)

        self.toolbar.hide()

    def resizeEvent(self, event):
        """Keep the toolbar centered at the top"""
        if hasattr(self, 'toolbar'):
            w = 300  # Width of toolbar
            h = 50  # Height
            x = (self.width() - w) // 2
            self.toolbar.setGeometry(x, 20, w, h)
        super().resizeEvent(event)

    def startCapture(self, mode: CaptureMode, display_text=None):
        self.current_mode = mode

        if display_text is None:
            if mode is CaptureMode.REGION:
                display_text = "Click and drag to select a region"
            elif mode is CaptureMode.POINT:
                display_text = "Click to set the point"

        self.lbl_instruction.setText(display_text)

        # Show Toolbar
        self.show()
        self.toolbar.show()
        self.toolbar.raise_()  # Make sure it's on top of drawn rectangles

        self.setClickThrough(False)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()  # Trigger repaint

    def cancelCapture(self):
        """Called when X is pressed"""
        self.toolbar.hide()

        # Reset Logic
        self.start_pos = self.selection_rect = self.current_mode = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

        # Notify main window
        self.main_window.afterCaptureEnded()

    def setClickThrough(self, enabled: bool):
        """
        Toggles whether clicks pass through to the game or stay in the overlay.
        """
        self._click_through = enabled
        if enabled:
            # Game Mode: Clicks go through to the game
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

            self.hide()
            self.showFullScreen()

            self.raise_()  # Bring to very front
            self.activateWindow()  # Tell OS "This is the active app"
            self.setFocus()  # Tell Qt "Send key/mouse events here"

            self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

    def mousePressEvent(self, event):
        if not self.current_mode:
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode is CaptureMode.POINT:
                self._finish_capture(event.pos())
            elif self.current_mode is CaptureMode.REGION:
                # Start dragging
                self.start_pos = event.pos()
                self.selection_rect = QRect(self.start_pos, self.start_pos)
                self.update()

    def mouseMoveEvent(self, event):
        if self.current_mode is CaptureMode.REGION and self.start_pos:
            # Update the drag rectangle
            self.selection_rect = QRect(self.start_pos, event.pos()).normalized()
            self.update()  # Force repaint to show the box growing

    def mouseReleaseEvent(self, event):
        if self.current_mode is CaptureMode.REGION and self.start_pos:
            # Finish dragging
            final_rect = self.selection_rect
            self._finish_capture(final_rect)

    def keyPressEvent(self, event: QKeyEvent):
        cur_mode = self.current_mode
        if cur_mode and event.key() == Qt.Key.Key_Escape:
            self._finish_capture(None)

    def _finish_capture(self, result):
        """Internal helper to clean up and notify main window"""
        self.start_pos = self.selection_rect = self.current_mode = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.toolbar.hide()

        # Send result back to main window
        self.main_window.afterCaptureEnded(result)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        highlight_pen = QPen(QColor(100, 200, 255), 2, Qt.PenStyle.SolidLine)
        highlight_brush = QColor(100, 200, 255, 30)
        if not self._click_through:
            # Dim the screen a bit when we are selecting
            dim_color = QColor(0, 0, 0, 100)
            painter.fillRect(self.rect(), dim_color)

            selection_rect = self.selection_rect
            if selection_rect:
                painter.setPen(highlight_pen)
                painter.setBrush(highlight_brush)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.drawRect(selection_rect)
        else:
            # Show geometry when we're click-through
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            red_pen = QPen(QColor(255, 0, 0, 180), 2)
            painter.setPen(red_pen)
            highlighted_config = self.highlighted_config
            for obj_conf in self.render_geometry:
                val = obj_conf.value
                if val:
                    if highlighted_config == obj_conf:
                        painter.setPen(highlight_pen)
                        painter.setBrush(highlight_brush)

                    if isinstance(val, QPoint):
                        painter.drawEllipse(val, 10, 10)
                    elif isinstance(val, QRect):
                        painter.drawRect(val)
                    else:
                        print(f'UNEXPECTED OBJECT {type(val)} FOUND WHEN DRAWING')

                    if highlighted_config == obj_conf:
                        # Reset the brush
                        painter.setPen(red_pen)
                        painter.setBrush(QColor(0, 0, 0, 0))

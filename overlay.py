from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QKeyEvent
from types_and_enums import CaptureMode


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
    capture_complete_signal = pyqtSignal(object)
    capture_cancelled_signal = pyqtSignal()

    def __init__(self, app: QApplication):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # Prevents showing in taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.app = app
        self._click_through = True

        self._setup_toolbar()

        screen = app.primaryScreen()
        self.setGeometry(screen.geometry())

        self.show()
        self.setClickThrough(True)
        self.render_geometry: dict | None = None

        self.current_mode: CaptureMode = CaptureMode.IDLE
        self.start_pos = None
        self.selection_rect: QRect | None = None

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
        self.btn_cancel.clicked.connect(self.cancel_capture)
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

    def startCapture(self, mode: CaptureMode, display_text: str):
        self.current_mode = mode

        # Update Text based on mode
        self.lbl_instruction.setText(display_text)

        # Show Toolbar
        self.show()
        self.toolbar.show()
        self.toolbar.raise_()  # Make sure it's on top of drawn rectangles

        self.setClickThrough(False)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()  # Trigger repaint

    def cancel_capture(self):
        """Called when X is pressed"""
        self.toolbar.hide()

        # Reset Logic
        self.current_mode = CaptureMode.IDLE
        self.start_pos = None
        self.selection_rect = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

        # Notify Engine
        self.capture_cancelled_signal.emit()

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
        if self.current_mode == CaptureMode.IDLE:
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_mode == CaptureMode.POINT:
                # Immediate success for single point
                self._finish_capture(event.pos())
            elif self.current_mode == CaptureMode.REGION:
                # Start dragging
                self.start_pos = event.pos()
                self.selection_rect = QRect(self.start_pos, self.start_pos)
                self.update()

    def mouseMoveEvent(self, event):
        if self.current_mode == CaptureMode.REGION and self.start_pos:
            # Update the drag rectangle
            self.selection_rect = QRect(self.start_pos, event.pos()).normalized()
            self.update()  # Force repaint to show the box growing

    def mouseReleaseEvent(self, event):
        if self.current_mode == CaptureMode.REGION and self.start_pos:
            # Finish dragging
            final_rect = self.selection_rect
            self._finish_capture(final_rect)

    def keyPressEvent(self, event: QKeyEvent):
        cur_mode = self.current_mode
        if event.key() == Qt.Key.Key_Escape and cur_mode != CaptureMode.IDLE:
            self._finish_capture(None)

    def _finish_capture(self, result):
        """Internal helper to clean up and notify engine"""
        self.current_mode = CaptureMode.IDLE
        self.start_pos = None
        self.selection_rect = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.toolbar.hide()

        # Send result back to Engine
        self.capture_complete_signal.emit(result)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        # dim_color = QColor(0, 0, 0, 100)
        # painter.fillRect(self.rect(), dim_color)

        if not self._click_through:
            # Dim the screen a bit when we are selecting
            dim_color = QColor(0, 0, 0, 100)
            painter.fillRect(self.rect(), dim_color)

            selection_rect = self.selection_rect
            if selection_rect:
                painter.setPen(QPen(QColor(100, 200, 255), 2, Qt.PenStyle.SolidLine))
                painter.setBrush(QColor(100, 200, 255, 30))
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.drawRect(selection_rect)
        else:
            # Show geometry when we're click-through
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(255, 0, 0, 180), 2))
            render_geom_dict = self.render_geometry
            if render_geom_dict:
                for obj in render_geom_dict.values():
                    if isinstance(obj, QPoint):
                        painter.drawEllipse(obj, 10, 10)
                    elif isinstance(obj, QRect):
                        painter.drawRect(obj)
                    else:
                        print(f'UNEXPECTED OBJECT {type(obj)} FOUND')

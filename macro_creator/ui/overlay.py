from PySide6.QtWidgets import QWidget, QFrame, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint, QRect, Signal, QEventLoop
from PySide6.QtGui import QPainter, QPen, QColor, QKeyEvent
from typing import TYPE_CHECKING

from macro_creator.core.types_and_enums import CaptureMode
from macro_creator.core.capture_type_registry import GlobalCaptureRegistry
from macro_creator.core.data import VariableConfig

if TYPE_CHECKING:
    from .main_window import MainWindow

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


def _paintCapturable(painter, to_paint):
    if isinstance(to_paint, VariableConfig):
        to_paint = to_paint.value

    if to_paint is None: return

    if isinstance(to_paint, QPoint):
        painter.drawEllipse(to_paint, 10, 10)
    elif isinstance(to_paint, QRect):
        painter.drawRect(to_paint)
    else:
        print(f'UNEXPECTED OBJECT {type(to_paint)} FOUND WHEN DRAWING')


class TransparentOverlay(QWidget):
    captureFinished = Signal()

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
        self._showing_geometry = True

        self.current_mode: CaptureMode | None = None
        self.start_pos = None
        self.selection_rect: QRect | None = None
        self._highlighted: VariableConfig | QPoint | QRect | None = None
        self._captured_data = None

    @property
    def showing_geometry(self):
        return self._showing_geometry

    @showing_geometry.setter
    def showing_geometry(self, value: bool):
        if value != self._showing_geometry:
            self._showing_geometry = value
            self.update()

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
        self.btn_cancel.clicked.connect(lambda: self._finishCapture())
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

    def captureData(self, mode: CaptureMode, display_text=None) -> QRect | QPoint | None:
        """Shows the overlay and waits until capture is finished"""
        self.main_window.hide()
        self.current_mode = mode

        if display_text is None:
            if mode is CaptureMode.REGION:
                display_text = "Click and drag to select a region"
            elif mode is CaptureMode.POINT:
                display_text = "Click to set the point"

        self.lbl_instruction.setText(display_text)

        self.show()
        self.toolbar.show()
        self.toolbar.raise_()

        self.setClickThrough(False)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

        loop = QEventLoop()
        self.captureFinished.connect(loop.quit)
        loop.exec()

        # Finished capture when past loop.exec
        capture_data = self._captured_data
        self._captured_data = None

        return capture_data

    def _finishCapture(self, capture_data=None):
        self._captured_data = capture_data
        self.start_pos = self.selection_rect = self.current_mode = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.toolbar.hide()
        self.update()
        self.setClickThrough(True)
        self.main_window.show()
        self.captureFinished.emit()

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
                self._finishCapture(event.pos())
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
            self._finishCapture(final_rect)

    def keyPressEvent(self, event: QKeyEvent):
        cur_mode = self.current_mode
        if cur_mode and event.key() == Qt.Key.Key_Escape:
            self._finishCapture(None)

    def trySetHighlighted(self, config_name: str | QPoint | QRect):
        prev = self._highlighted
        if isinstance(config_name, str):
            config = self.main_window.profile.vars.get(config_name)
            if not config: return
            self._highlighted = config if (config and GlobalCaptureRegistry.containsType(config.data_type)) else None
        else:
            self._highlighted = config_name

        if prev != self._highlighted:
            self.update()

    def removeHighlightedData(self):
        if self._highlighted:
            self._highlighted = None
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
            highlighted = self._highlighted
            if self._showing_geometry:
                painter.setPen(QPen(QColor(255, 0, 0, 180), 2))
                for obj_conf in self.render_geometry:
                    val = obj_conf.value
                    if val and highlighted != obj_conf:
                        _paintCapturable(painter, val)

            if highlighted:
                painter.setPen(highlight_pen)
                painter.setBrush(highlight_brush)
                _paintCapturable(painter, highlighted)
import qtawesome as qta
from dataclasses import dataclass
from typing import TYPE_CHECKING
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QListWidget, QAbstractItemView, QCheckBox
)
from PySide6.QtGui import QDrag, QPainter, QColor, QPen, QBrush, QPalette
from PySide6.QtCore import Qt, QMimeData, QSize

from macro_creator.core.data.timeline_handler import ActionType, TimelineData
from macro_creator.ui.shared import DEFAULT_ICON_COLOR, SELECTED_COLOR, HoverButton

if TYPE_CHECKING:
    from macro_creator.ui.tabs.recorder_tab import RecorderTab

@dataclass
class ActionConfig:
    color: str
    icon_name: str
    pairable: bool = False

ACTION_TYPES = {
    ActionType.DELAY:    ActionConfig(color="#A6A6A6", icon_name="ph.clock"),
    ActionType.KEYBOARD: ActionConfig(color="#4CAF50", icon_name="fa5.keyboard", pairable=True),
    ActionType.MOUSE:    ActionConfig(color="#FF9800", icon_name="ph.mouse", pairable=True),
    ActionType.TEXT:     ActionConfig(color="#2196F3", icon_name="ph.text-align-left"),
    # ActionType.LOOP:     ActionConfig(color="#F44336", icon_name="ph.repeat", pairable=True), # Meh
}

GRIP_CONFIG = ActionConfig(color="#666", icon_name="msc.gripper")

TRASH_ICON = "ph.trash"

def createQtIcon(config_or_icon: str | ActionConfig, color_override: str=None):
    if isinstance(config_or_icon, str):
        icon = config_or_icon
        color = DEFAULT_ICON_COLOR
    else:
        icon = config_or_icon.icon_name
        color = config_or_icon.color

    return qta.icon(icon, color=color_override if color_override else color)

def createIconLabel(config_or_icon: str | ActionConfig, color_override: str=None):
    lbl_icon = QLabel()
    lbl_icon.setFixedSize(30, 30)
    lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    icon_obj = createQtIcon(config_or_icon, color_override)
    pixmap = icon_obj.pixmap(25, 25)
    lbl_icon.setPixmap(pixmap)

    return lbl_icon


class RecorderToolbar(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("recorder_toolbar")
        self.setFixedHeight(46)  # consistent height

        layout = QHBoxLayout(self)
        layout.setContentsMargins(32, 5, 15, 5)
        layout.setSpacing(15)

        # 1. Select All Checkbox
        first_container = QWidget()
        first_layout = QHBoxLayout(first_container)
        first_layout.setContentsMargins(0, 0, 0, 0)
        first_layout.setSpacing(0)
        self.chk_select_all = QCheckBox()
        self.chk_select_all.setToolTip("Select All")
        self.chk_select_all.setCursor(Qt.CursorShape.PointingHandCursor)
        first_layout.addWidget(self.chk_select_all)

        # 2. Timer Label
        self.timer_container = QWidget()
        timer_layout = QHBoxLayout(self.timer_container)
        timer_layout.setContentsMargins(0, 0, 0, 0)
        timer_layout.setSpacing(5)
        label_icon = createIconLabel("ph.clock-clockwise")
        label_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        label_icon.setToolTip("Total Duration")
        self.lbl_timer = QLabel("0.0s")
        self.lbl_timer.setObjectName("ActionTitle")
        timer_layout.addWidget(label_icon)
        timer_layout.addWidget(self.lbl_timer)
        first_layout.addWidget(self.timer_container)

        self.trash_container = QWidget()
        trash_layout = QHBoxLayout(self.trash_container)
        trash_layout.setContentsMargins(0, 0, 0, 0)
        trash_layout.setSpacing(5)

        self.btn_trash_selected = HoverButton(TRASH_ICON, hover_color="#ff0000")
        self.btn_trash_selected.setToolTip("Delete Selected")
        self.lbl_select_ct = QLabel("0 Selected")
        self.lbl_select_ct.setObjectName("ActionTitle")

        trash_layout.addWidget(self.btn_trash_selected)
        trash_layout.addWidget(self.lbl_select_ct)
        first_layout.addWidget(self.trash_container)

        self.trash_container.hide()

        # 3. Record Button (Red Gradient)
        self.btn_record = QPushButton("RECORD")
        self.btn_record.setIcon(createQtIcon("ph.record-fill", color_override="#ff0000"))
        self.btn_record.setIconSize(QSize(25,25))
        self.btn_record.setObjectName("btn_record")
        self.btn_record.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_record.setFixedSize(110, 32)

        # 4. Undo / Redo
        undo_redo_container = QWidget()
        undo_redo_layout = QHBoxLayout(undo_redo_container)
        undo_redo_layout.setContentsMargins(0, 0, 0, 0)
        undo_redo_layout.setSpacing(5)

        self.btn_undo = HoverButton("ph.arrow-u-up-left", size=32)
        self.btn_redo = HoverButton("ph.arrow-u-up-right", size=32)

        undo_redo_layout.addWidget(self.btn_undo)
        undo_redo_layout.addWidget(self.btn_redo)

        # 5. Save Button (Green)
        self.btn_save = QPushButton("SAVE")
        self.btn_save.setObjectName("btn_save")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setFixedSize(90, 32)

        # Add widgets to layout
        layout.addWidget(first_container)
        layout.addStretch()  # Spacer
        layout.addWidget(self.btn_record)
        layout.addWidget(undo_redo_container)
        layout.addWidget(self.btn_save)

    def updateTimer(self, seconds: float):
        self.lbl_timer.setText(f"{seconds:g}s")

    def setRecordingState(self, is_recording: bool):
        """Visual toggle for the record button"""
        if is_recording:
            self.btn_record.setText("⏹ STOP")
            self.btn_record.setStyleSheet("""
                background-color: #ff4444; border: 1px solid #ff0000; color: white;
            """)
        else:
            self.btn_record.setText("🔴 RECORD")
            self.btn_record.setStyleSheet(self._record_style_idle)


class DragPreviewWidget(QWidget):
    def __init__(self, config_or_icon, text: str):
        super().__init__()
        self.setObjectName("drag_preview")
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(10, 10, 25, 10)
        self.layout().setSpacing(5)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)

        palette = self.palette()
        opposite_color = self.palette().color(self.backgroundRole())
        palette.setColor(QPalette.ColorRole.WindowText, opposite_color)

        lbl_icon = createIconLabel(config_or_icon, color_override=opposite_color.name())
        lbl_text = QLabel(text)
        lbl_text.setObjectName("ActionTitle")

        font = lbl_text.font()
        font.setBold(True)
        lbl_text.setFont(font)

        lbl_text.setPalette(palette)

        self.layout().addWidget(lbl_icon)
        self.layout().addWidget(lbl_text)

    def paintEvent(self, event):
        """
        Manually draw the rounded background.
        This is 100% reliable compared to Stylesheets for this specific case.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        background_color = QColor(SELECTED_COLOR)

        painter.setBrush(QBrush(background_color))
        painter.setPen(QPen(background_color, 1))

        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.drawRoundedRect(rect, 10, 10)


class PaletteItemWidget(QWidget):
    """The widget displayed in the LEFT sidebar."""

    def __init__(self, action_type: ActionType):
        super().__init__()
        config = ACTION_TYPES[action_type]

        self.action_type = action_type

        self.text = action_type.value
        self.color_code = config.color

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(5)

        lbl_icon = createIconLabel(config)

        self.lbl_text = QLabel(self.text)
        self.lbl_text.setObjectName("ActionTitle")

        self.lbl_grip = createIconLabel(GRIP_CONFIG)
        self.lbl_grip.hide()

        self.layout.addWidget(lbl_icon)
        self.layout.addWidget(self.lbl_text)
        self.layout.addStretch()
        self.layout.addWidget(self.lbl_grip)

    def enterEvent(self, event):
        self.lbl_grip.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.lbl_grip.hide()
        super().leaveEvent(event)

# --- LIST WIDGETS ---

class DraggableListWidget(QListWidget):
    """The Palette List (Left Side)"""

    def __init__(self, recorder_tab: "RecorderTab"):
        super().__init__()
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.recorder_tab = recorder_tab

        self.itemClicked.connect(self._onItemClicked)

    def _onItemClicked(self, item):
        """Add a new step to the timeline list"""
        widget = self.itemWidget(item)
        if widget:
            action_type = widget.action_type
            detail = 1 if ACTION_TYPES[action_type].pairable else None
            self.recorder_tab.userAddsStep(None, TimelineData(action_type=action_type,detail=detail))

    def startDrag(self, supportedActions):
        item = self.currentItem()
        widget = self.itemWidget(item)
        if not widget: return

        action_str = widget.text
        action_type = widget.action_type

        preview = DragPreviewWidget(ACTION_TYPES[action_type], action_str)

        preview.adjustSize()
        pixmap = preview.grab()

        mime = QMimeData()
        mime.setText(action_str)

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(pixmap)
        drag.setHotSpot(pixmap.rect().center())

        self.recorder_tab.palette_drag_action = action_type

        drag.exec(Qt.DropAction.CopyAction)
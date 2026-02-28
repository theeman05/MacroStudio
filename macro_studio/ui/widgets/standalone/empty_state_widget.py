from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

from macro_studio.ui.shared import updateLabelIcon

DEFAULT_ICON = "ph.ghost"
DEFAULT_TITLE = "Nothing here yet"
DEFAULT_SUBTITLE = ""
DEFAULT_ACTION_TEXT = ""

class EmptyStateWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.setContentsMargins(20, 40, 20, 40)
        self.main_layout.setSpacing(10)

        self.default_icon = DEFAULT_ICON
        self.default_title = DEFAULT_TITLE
        self.default_subtitle = DEFAULT_SUBTITLE
        self.default_action_txt = DEFAULT_ACTION_TEXT

        # UI Elements
        self.icon_label = QLabel()

        self.title_label = QLabel()
        self.title_label.setObjectName("EmptyStateTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("EmptyStateSubtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.action_btn = QPushButton()
        self.action_btn.setObjectName("EmptyStateButton")
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.hide()  # Hidden until text is set

        # Assemble
        for w in [self.icon_label, self.title_label, self.subtitle_label, self.action_btn]:
            self.main_layout.addWidget(w, alignment=Qt.AlignmentFlag.AlignCenter)

    def setupState(self, icon_name, title, subtitle, btn_text=None):
        updateLabelIcon(self.icon_label, icon_name)
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)

        if btn_text:
            self.action_btn.setText(btn_text)
            self.action_btn.show()
        else:
            self.action_btn.hide()

    def defaultState(self, subtitle=None, btn_text=None):
        updateLabelIcon(self.icon_label, self.default_icon)
        self.title_label.setText(self.default_title)
        self.subtitle_label.setText(subtitle or self.default_subtitle)
        btn_text = btn_text or self.default_action_txt

        if btn_text:
            self.action_btn.setText(btn_text)
            self.action_btn.show()
        else:
            self.action_btn.hide()
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit

from macro_studio.ui.shared import HoverButton


class ManagerHeader(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("BlueHeader")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search tasks...")
        self.search_bar.setFixedWidth(300)

        layout.addWidget(self.search_bar)

        layout.addStretch()

        self.add_btn = HoverButton("ph.plus-circle", tooltip="Add Task", size=35)
        self.add_btn.setAutoDefault(False)
        self.add_btn.setDefault(False)

        layout.addWidget(self.add_btn)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit

from macro_studio.ui.shared import HoverButton


class ManagerHeader(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search tasks...")

        layout.addWidget(self.search_bar)

        layout.addStretch()

        add_task_btn = HoverButton("ph.plus-circle", tooltip="Add Task", size=35)
        remove_task_btn = HoverButton("ph.trash", hover_color="#f44336", tooltip="Remove Selected Tasks", size=35)

        layout.addWidget(add_task_btn)
        layout.addWidget(remove_task_btn)
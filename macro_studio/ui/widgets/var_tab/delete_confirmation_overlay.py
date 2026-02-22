from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QFrame, QLabel)
from PySide6.QtCore import Qt, Signal


class DeleteConfirmationOverlay(QWidget):
    """A reusable modal overlay for destructive actions."""
    deleteConfirmed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("<b>Delete Variables?</b>")
        self.warning_label = QLabel()
        self.btn_confirm = QPushButton("Delete")
        self.btn_confirm.setObjectName("btn_stop")
        self.btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)

        # 2. The Modal Card
        self.dialog_card = QFrame()
        self.dialog_card.setObjectName("FormCard")
        self.dialog_card.setMinimumWidth(320)

        self.buildUi()

        self.main_layout.addWidget(self.dialog_card)
        self.hide()

    def buildUi(self):
        card_layout = QVBoxLayout(self.dialog_card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(15)  # Give the warning text room to breathe

        # Title
        self.title_label.setStyleSheet("font-size: 14px;")
        card_layout.addWidget(self.title_label)

        # Dynamic Warning Text

        self.warning_label.setWordWrap(True)  # Crucial so long text doesn't stretch the card
        self.warning_label.setStyleSheet("color: #b0b0b0;")  # Soft gray for description text
        card_layout.addWidget(self.warning_label)

        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.hide)

        self.btn_confirm.clicked.connect(self.confirmDeletion)

        button_layout.addWidget(btn_cancel)
        button_layout.addWidget(self.btn_confirm)
        card_layout.addLayout(button_layout)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200))

    def showOverlay(self, count: int):
        """Dynamically updates the text based on how many items are selected."""
        if count == 1:
            text = "Are you sure you want to delete the selected variable? This action cannot be undone."
        else:
            text = f"Are you sure you want to delete {count} selected variables? This action cannot be undone."

        self.warning_label.setText(text)
        self.show()
        self.raise_()

    def confirmDeletion(self):
        """Fires the flare gun and hides the overlay."""
        self.deleteConfirmed.emit()
        self.hide()
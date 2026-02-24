from typing import TYPE_CHECKING

from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QFrame, QFormLayout,
                               QLineEdit, QComboBox, QLabel)
from PySide6.QtCore import Qt

from macro_studio.core.registries.type_handler import GlobalTypeHandler
from macro_studio.core.registries.capture_type_registry import GlobalCaptureRegistry
from macro_studio.ui.shared import flashError

if TYPE_CHECKING:
    from macro_studio.core.data import VariableStore


class VarCreateOverlay(QWidget):
    """A reusable, self-contained modal overlay for creating variables."""
    def __init__(self, var_store: "VariableStore", parent=None):
        super().__init__(parent)
        # 2. Give the overlay its own layout to center the card
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.var_store = var_store

        # 3. Build the Form Card
        self.form_card = QFrame()
        self.form_card.setObjectName("FormCard")
        self.form_card.setStyleSheet("""
            QFrame { background-color: #212121; border-radius: 8px; border: 1px solid #444; }
            QLabel { background-color: transparent; color: white; border: none; }
        """)
        self.form_card.setMinimumWidth(350)

        self.input_name = QLineEdit()
        self.combo_type = QComboBox()
        self.input_tooltip = QLineEdit()

        self.error_label_name = QLabel("Variable name cannot be empty.")
        self.error_label_name.setStyleSheet("color: #ff5252; font-size: 11px; font-weight: bold;")
        self.error_label_name.hide()  # Keep it invisible by default

        self.buildForm()

        # Attach the card to the overlay
        self.main_layout.addWidget(self.form_card)

        # Hide it by default upon creation
        self.hide()

    def buildForm(self):
        """Constructs the internal layouts and inputs of the form card."""
        card_layout = QVBoxLayout(self.form_card)
        card_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("<b>Create New Variable</b>")
        card_layout.addWidget(title)

        form_layout = QFormLayout()

        name_container = QVBoxLayout()
        name_container.setSpacing(2)
        name_container.setContentsMargins(0, 0, 0, 0)

        name_container.addWidget(self.input_name)
        name_container.addWidget(self.error_label_name)

        form_layout.addRow("Variable ID:", name_container)
        form_layout.addRow("Type:", self.combo_type)
        form_layout.addRow("Tooltip:", self.input_tooltip)
        card_layout.addLayout(form_layout)

        # Populate the combo box immediately!
        self.populateTypes()

        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.hide)

        btn_save = QPushButton("Save")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self.saveVariable)

        button_layout.addWidget(btn_cancel)
        button_layout.addWidget(btn_save)
        card_layout.addLayout(button_layout)

    def show(self):
        self.input_name.clear()
        self.input_tooltip.clear()
        self.error_label_name.hide()
        self.combo_type.setCurrentIndex(0)
        super().show()
        self.raise_()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200))

    def saveVariable(self):
        """Extracts data, interacts with the engine, and closes the overlay."""
        var_name = self.input_name.text().strip()
        has_error = False
        if not var_name:
            has_error = True
            self.error_label_name.setText("Variable name cannot be empty.")

        if var_name in self.var_store:
            has_error = True
            self.error_label_name.setText("Variable name already exists.")

        if has_error:
            self.error_label_name.show()
            flashError(self.input_name)
            return

        self.var_store.add(var_name, self.combo_type.currentData(),None, self.input_tooltip.text())
        self.hide()

    def populateTypes(self):
        """Fills the dropdown with primitives and registered custom types."""
        type_defs = GlobalCaptureRegistry.getAll()
        capture_types = set()

        for type_def in type_defs:
            display_name = GlobalTypeHandler.getDisplayName(
                type_def.type_class)
            self.combo_type.addItem(display_name, type_def.type_class)
            capture_types.add(type_def.type_class)

        self.combo_type.insertSeparator(self.combo_type.count())

        custom_types = GlobalTypeHandler.getRegisteredTypes()
        for t in custom_types:
            if t not in capture_types:
                self.combo_type.addItem(GlobalTypeHandler.getDisplayName(t), t)
from typing import Union

from PySide6.QtWidgets import (QPushButton, QComboBox, QWidget, QGridLayout, QTextEdit, QDoubleSpinBox, QDialog,
                               QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QPlainTextEdit, QSpinBox, QStackedWidget)
from PySide6.QtGui import QKeySequence
from PySide6.QtCore import Qt, Signal, QEvent, QTimer

from macro_studio.ui.shared import setBtnState
from macro_studio.core.recording.timeline_handler import MouseFunction


EditorWidget = Union[QPushButton, QComboBox, QTextEdit, QDoubleSpinBox, QSpinBox, QStackedWidget]

class SneakyWidget(QWidget):
    """
    Container that swaps between a 'Display Button' and an 'Internal Editor'.
    """
    valueChanged = Signal(object) # Called before the value changes to the (new_value)

    def __init__(self, internal_widget: EditorWidget | None, value, parent=None):
        super().__init__(parent)
        self.value = value

        self.can_finish = False

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.display_btn = QPushButton()
        self.display_btn.setObjectName("SneakyButton")
        self.display_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.display_btn.clicked.connect(self.startCapture)

        self.editor = internal_widget
        internal_widget.setObjectName("SneakyInternalWidget")
        self.editor.installEventFilter(self)  # Spy on focus events
        self.editor.hide()

        self.layout.addWidget(self.display_btn, 0, 0)
        self.layout.addWidget(self.editor, 0, 0)

        self.setValue(value)

    def startCapture(self):
        """Switch to editor and give it focus."""
        setBtnState(self.display_btn, "setting")
        self.display_btn.setText("")

        self.editor.raise_()
        self.editor.setFocus()
        self.editor.show()
        self.can_finish = True

    def finishEditing(self, new_value=None):
        """Switch back to button and update text."""
        self.can_finish = False

        old_value = self.value
        has_new_data = new_value is not None
        if has_new_data and old_value != new_value:
            # Emit change before setting the value
            self.valueChanged.emit(new_value)
        self.setValue(new_value if has_new_data else old_value)
        self.editor.hide()

    def setValue(self, new_value):
        """Sets the value and updates the display thing without calling valueChanged"""
        self.value = new_value
        setBtnState(self.display_btn, "empty" if new_value is None else "")
        self.display_btn.setText(self.getDisplayStr())

    def eventFilter(self, source, event):
        """Detect when user clicks away (FocusOut) to close the editor."""
        if (event.type() == QEvent.Type.FocusOut or event.type() == QEvent.Type.FocusIn) and self.editor.isVisible() and self.can_finish:
            self.finishEditing()
        return super().eventFilter(source, event)

    def _setCanFinishTrue(self):
        self.can_finish = True

    # Should be based on the current value if pairable
    def getDisplayStr(self):
        return "IMPLEMENT ME SUBCLASS WHYYY"

## ----------- PAIRABLE ----------- ##
class KeyCaptureEditor(SneakyWidget):
    def __init__(self, parent, prev_key_str):
        super().__init__(QPushButton(), value=prev_key_str, parent=parent)

    def startCapture(self):
        self.editor.setText("Press any key...")
        self.grabKeyboard()
        super().startCapture()

    def keyPressEvent(self, event):
        if not self.can_finish:
            super().keyPressEvent(event)
            return

        self.releaseKeyboard()

        # Convert that single key into its standard Qt string format
        sequence = QKeySequence(event.key())
        data_str = sequence.toString()

        self.editor.setText(data_str)
        event.accept()

        self.finishEditing(data_str)

    def getDisplayStr(self):
        return self.value if self.value else "No key set"

class SneakyComboEditor(SneakyWidget):
    def __init__(self, parent, prev_key_str, enum=MouseFunction):
        combo_box = QComboBox()
        i = 0
        for e in enum:
            combo_box.addItem(e.value, e.name)
            if e.name == prev_key_str:
                combo_box.setCurrentIndex(i)
            i += 1
        self.enum = enum
        super().__init__(combo_box, value=prev_key_str, parent=parent)
        combo_box.activated.connect(lambda: self.finishEditing(combo_box.currentData()))

    def startCapture(self):
        self.editor.setCurrentText(self.getDisplayStr())
        super().startCapture()
        self.can_finish = False
        self.editor.showPopup()
        QTimer.singleShot(200, self._setCanFinishTrue)

    def setValue(self, new_value_str):
        if new_value_str is None:
            self.editor.setCurrentIndex(0)
            new_value_str = self.editor.currentData()

        super().setValue(new_value_str)

    def getDisplayStr(self):
        return self.enum[self.value].value

## ----------- NON - PAIRABLE ----------- ##
class SneakyDbSpinBox(SneakyWidget):
    def __init__(self, parent, prev_value: float):
        prev_value = prev_value
        spinner = QDoubleSpinBox()
        spinner.setRange(0.0, 1000000.0)
        spinner.setSingleStep(0.001)
        spinner.setDecimals(3)
        super().__init__(spinner, value=prev_value, parent=parent)
        spinner.editingFinished.connect(self.finishEditing)

    def startCapture(self):
        self.editor.setValue(self.value)
        super().startCapture()

    def finishEditing(self, new_value=None):
        super().finishEditing(new_value or self.editor.value())

    def setValue(self, new_value):
        super().setValue(new_value or 0.0)

    def getDisplayStr(self):
        return f"{self.value:g}s"

class SneakySpinBox(SneakyWidget):
    def __init__(self, parent, prev_value: int):
        prev_value = prev_value or 1
        spinner = QSpinBox()
        spinner.setRange(1, 10000)
        super().__init__(spinner, value=prev_value, parent=parent)
        spinner.editingFinished.connect(self.finishEditing)

    def startCapture(self):
        self.editor.setValue(self.value)
        super().startCapture()

    def finishEditing(self, new_value=None):
        super().finishEditing(new_value or self.editor.value())

    def setValue(self, new_value):
        super().setValue(new_value or 1)

    def getDisplayStr(self):
        return f"{self.editor.value():g}s"

class TextFunctionDialog(QDialog):
    MAX_LEN = 250
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.resize(300, 280)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 10, 15, 15)

        header_layout = QHBoxLayout()

        self.title_label = QLabel("TEXT FUNCTION")
        self.title_label.setObjectName("header_label")

        self.close_btn = QToolButton()
        self.close_btn.setText("X")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()  # Pushes X to the right
        header_layout.addWidget(self.close_btn)

        layout.addLayout(header_layout)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Enter Text")
        layout.addWidget(self.text_edit)

        tools_layout = QHBoxLayout()

        self.lbl_counter = QLabel("0/250")

        tools_layout.addStretch()
        tools_layout.addWidget(self.lbl_counter)

        layout.addLayout(tools_layout)

        action_layout = QHBoxLayout()

        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton("SAVE")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setObjectName("btn_save")
        self.btn_save.clicked.connect(self.trySave)

        action_layout.addWidget(self.btn_cancel)
        action_layout.addWidget(self.btn_save)

        layout.addLayout(action_layout)

        self.text_edit.textChanged.connect(self.update_counter)
        self.update_counter()

    def trySave(self):
        if len(self.text_edit.toPlainText()) < TextFunctionDialog.MAX_LEN: self.accept()

    def update_counter(self):
        current_len = len(self.text_edit.toPlainText())
        max_len = TextFunctionDialog.MAX_LEN
        self.lbl_counter.setText(f"{current_len}/{max_len}")

        if current_len > max_len:
            self.lbl_counter.setStyleSheet("color: red;")
        else:
            self.lbl_counter.setStyleSheet("")

class SneakyTextEditor(SneakyWidget):
    def __init__(self, parent, prev_text):
        self.text_dialog = None
        super().__init__(QPushButton(), value=prev_text, parent=parent)
        self.text_dialog = TextFunctionDialog(parent=parent)
        self.text_dialog.finished.connect(self.finishEditing)

    def startCapture(self):
        super().startCapture()
        self.can_finish = False
        disp_text = self.value or ""
        self.text_dialog.text_edit.setPlainText(disp_text)
        self.display_btn.setText(disp_text)
        self.text_dialog.show()

    def finishEditing(self, new_value=None):
        if self.text_dialog:
            if new_value == 1:
                new_value = self.text_dialog.text_edit.toPlainText()
            else:
                new_value = self.value

        if isinstance(new_value, int):
            new_value = None

        super().finishEditing(new_value)

    def setValue(self, new_value):
        super().setValue(new_value or None)

    def getDisplayStr(self):
        return f"Text: {self.value if self.value else "Enter Text"}"

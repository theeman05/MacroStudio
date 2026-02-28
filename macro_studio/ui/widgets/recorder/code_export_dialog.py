from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
from PySide6.QtGui import QGuiApplication, QFont


class CodeExportDialog(QDialog):
    def __init__(self, code_string: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export as Python Script")
        self.resize(600, 450)

        layout = QVBoxLayout(self)

        # Text Editor (Read-Only)
        self.code_viewer = QTextEdit()
        self.code_viewer.setReadOnly(True)
        self.code_viewer.setPlainText(code_string)

        # Make it look like an IDE using a monospace font
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.code_viewer.setFont(font)

        # Copy Button
        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.setMinimumHeight(35)
        self.copy_btn.clicked.connect(self.copyToClipboard)

        layout.addWidget(self.code_viewer)
        layout.addWidget(self.copy_btn)

    def copyToClipboard(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.code_viewer.toPlainText())
        self.copy_btn.setText("Copied!")
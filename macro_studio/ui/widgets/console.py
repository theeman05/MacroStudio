from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QTextBrowser, QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox


class LogWidget(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.setOpenExternalLinks(False)
        self.setPlaceholderText("System initialized. Waiting for tasks...")
        self.anchorClicked.connect(self._onLinkClicked)
        self.traceback_storage = {}

    def _onLinkClicked(self, url: QUrl):
        url_str = url.toString()
        if url_str.startswith("#id_"):
            trace_id = url_str.replace("#id_", "")
            trace_text = self.traceback_storage.get(trace_id, "Traceback not found.")
            TracebackDialog(trace_text, self).exec()
        elif url.scheme() in ["http", "https"]:
            QDesktopServices.openUrl(url)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction("Clear Console", self.clear)
        menu.exec(event.globalPos())

class TracebackDialog(QDialog):
    def __init__(self, traceback_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Error Traceback")
        self.resize(700, 500)
        layout = QVBoxLayout(self)

        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlainText(traceback_text)
        font = QFont("Courier New", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_area.setFont(font)
        self.text_area.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text_area)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        copy_btn = buttons.addButton("Copy", QDialogButtonBox.ButtonRole.ActionRole)
        copy_btn.clicked.connect(self.text_area.selectAll)
        copy_btn.clicked.connect(self.text_area.copy)
        layout.addWidget(buttons)
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QGroupBox, QLabel, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout, QApplication


class GUIStylesMixin:
    def apply_dark_theme(self):
        self.setStyleSheet("""
        QMainWindow {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 rgba(91, 206, 250, 180),   /* Trans flag light blue */
                stop: 0.4 rgba(245, 169, 184, 180), /* Trans flag pink */
                stop: 0.6 rgba(255, 255, 255, 180), /* Trans flag white */
                stop: 1 rgba(91, 206, 250, 180)     /* Trans flag light blue */
            );
        }
        QGroupBox {
            background-color: rgba(116,116,116, 0.3);  /* More translucent */
            border: 2px solid rgba(80, 80, 80, 0.3);  /* More translucent */
            border-radius: 3px;
            margin-top: 3px;
            color: #ffffff;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }
        QPushButton {
            background-color: rgba(74, 74, 74, 130);
            color: white;
            border: 1px solid rgba(80, 80, 80, 130);
            border-radius: 4px;
            padding: 5px 15px;
            min-width: 80px;
            transition: all 0.3s;
        }
        QPushButton:hover {
            background-color: rgba(245, 169, 184, 130);  /* Trans pink */
            border-color: rgba(91, 206, 250, 130);      /* Trans blue */
            color: white;
        }
        QPushButton:pressed {
            background-color: rgba(91, 206, 250, 130);  /* Trans blue */
            border-color: rgba(245, 169, 184, 130);     /* Trans pink */
        }
        QLabel {
            color: #ffffff;
        }
        QTextEdit {
            background-color: rgba(43, 43, 43, 130);  /* More translucent */
            color: #ffffff;
            border: 1px solid rgba(80, 80, 80, 130);  /* More translucent */
            border-radius: 4px;
        }
        QLineEdit {
            background-color: rgba(43, 43, 43, 130);  /* More translucent */
            color: #ffffff;
            border: 1px solid rgba(80, 80, 80, 130);  /* More translucent */
            border-radius: 4px;
            padding: 2px 5px;
        }
        QScrollArea {
            border: none;
            background: transparent;
        }
        QWidget#scrollAreaWidgetContents {
            background: transparent;
        }
        QScrollBar:vertical {
            border: none;
            background: rgba(43, 43, 43, 120);  /* More translucent */
            width: 14px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: rgba(74, 74, 74, 130);  /* More translucent */
            min-height: 30px;
            border-radius: 7px;
        }
        QScrollBar::handle:vertical:hover {
            background: rgba(90, 90, 90, 130);  /* More translucent */
        }
    """)

    def setup_log_colors(self):
        # Initialize with default HTML only if not already set
        if not self.log_text.toHtml().strip():
            self.log_text.setHtml('<html><body></body></html>')
        if not self.error_log_text.toHtml().strip():
            self.error_log_text.setHtml('<html><body></body></html>')

        # Set default text colors
        self.log_text.setStyleSheet("""
            QTextEdit {
                color: #ffffff;
                background-color: #2b2b2b;
            }
        """)
        self.error_log_text.setStyleSheet("""
            QTextEdit {
                color: #e74c3c;
                background-color: #2b2b2b;
            }
        """)

    def setup_fonts(self):
        title_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        text_font = QFont("Segoe UI", 9)
        mono_font = QFont("Consolas", 9)

        # Set fonts for different widget types
        for group in self.findChildren(QGroupBox):
            group.setFont(title_font)

        for label in self.findChildren(QLabel):
            label.setFont(text_font)

        for button in self.findChildren(QPushButton):
            button.setFont(text_font)

        for entry in self.findChildren(QLineEdit):
            entry.setFont(text_font)

        # Set monospace font for log outputs
        self.log_text.setFont(mono_font)
        self.error_log_text.setFont(mono_font)

    def setup_status_indicators(self):
        self.status_label.setStyleSheet("color: #e74c3c")  # Red for disconnected
        self.latency_label.setStyleSheet("color: #ffffff")

        # Style for Git status labels
        self.git_status_label.setStyleSheet("color: #ffffff")
        self.git_commit_label.setStyleSheet("color: #ffffff")
        self.git_update_status.setStyleSheet("color: #ffffff")

    def adjust_layouts(self):
        # Add spacing between widgets
        for layout in self.findChildren(QVBoxLayout) + self.findChildren(QHBoxLayout):
            layout.setSpacing(10)
            layout.setContentsMargins(10, 10, 10, 10)

    def show_error_notification(self):
        if not self.isActiveWindow():
            self.statusBar().showMessage("❌ New error in log", 3000)
            # Flash window or taskbar icon
            QApplication.alert(self)

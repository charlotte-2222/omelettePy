import asyncio
import logging
import queue

import psutil
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor, QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QLineEdit, QGroupBox, QScrollArea, QSizePolicy, QListWidget
)

from gui.bot_controls import BotControlsMixin
from gui.gui_styles import GUIStylesMixin


class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '#808080',
        'INFO': '#ffffff',
        'WARNING': '#f1c40f',
        'ERROR': '#e74c3c',
        'CRITICAL': '#c0392b'
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, '#ffffff')
        return f'<span style="color: {color}">{super().format(record)}</span>'


class GUIHandler(logging.Handler):
    def __init__(self, gui):
        super().__init__()
        self.gui = gui
        self.formatter = ColoredFormatter('[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s')

    def emit(self, record):
        try:
            msg = self.formatter.format(record)
            if record.levelno >= logging.ERROR:
                current = self.gui.error_log_text.toHtml()
                new_html = current[:-14] + msg + '<br></body></html>'
                self.gui.error_log_text.setHtml(new_html)
                self.gui.error_log_text.moveCursor(QTextCursor.MoveOperation.End)
                self.gui.show_error_notification()
            else:
                self.gui.msg_queue.put(msg)
        except Exception:
            self.handleError(record)


class BotGUI(QMainWindow, BotControlsMixin, GUIStylesMixin):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.msg_queue = queue.Queue()
        self.gui_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.gui_loop)

        self.setup_ui()
        self.setup_logging()
        self.setup_timer()
        self.setup_window()
        self.setup_theme_and_styles()
        self.add_reminder_monitor()

    def setup_window(self):
        self.setWindowTitle("OmelettePy Bot Control Panel")
        self.setMinimumSize(1000, 700)

        # Add status bar (customized)
        self.statusBar().showMessage("Ready")
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background: rgba(43, 43, 43, 130);
                color: white;
                border-top: 1px solid rgba(80, 80, 80, 130);
            }
        """)
        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setStyleSheet("color: #e74c3c")  # Red



        self.setStyleSheet(self.styleSheet() + """
        QMainWindow {
            transition: all 0.3s;
        }
    """)

        # Add resource monitor
        self.resource_label = QLabel()
        self.statusBar().addPermanentWidget(self.resource_label)

        def update_resources():
            process = psutil.Process()
            memory = process.memory_info().rss / 1024 / 1024
            self.resource_label.setText(f"Memory: {memory:.1f} MB")

        self.resource_timer = QTimer()  # Store timer as instance variable
        self.resource_timer.timeout.connect(update_resources)
        self.resource_timer.start(5000)

    def setup_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_msg_queue)
        self.timer.start(100)

    def setup_theme_and_styles(self):
        self.apply_dark_theme()
        self.setup_log_colors()
        self.setup_fonts()
        self.adjust_layouts()
        self.setup_status_indicators()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        scroll_layout = self.create_scroll_area(main_layout)

        self.create_status_group(scroll_layout)
        self.create_control_group(scroll_layout)
        self.create_git_group(scroll_layout)
        self.create_cog_group(scroll_layout)
        self.create_cog_status_group(scroll_layout)
        self.create_log_groups(scroll_layout)

        self.add_uptime_monitor()
        self.adjust_layout_spacing(main_layout)

        self.cog_entry.setPlaceholderText("Enter cog name (e.g. 'events')")
        self.cog_entry.setToolTip("Enter the name of the cog without 'cogs.' prefix")

        buttons = {
            "Start Bot": "Start the Discord bot",
            "Stop Bot": "Stop the Discord bot",
            "Reload Cogs": "Reload all currently loaded cogs",
            "Check Git": "Check repository status",
            "Update Repo": "Pull latest changes from remote"
        }

        for button in self.findChildren(QPushButton):
            if button.text() in buttons:
                button.setToolTip(buttons[button.text()])

    def create_scroll_area(self, main_layout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        return scroll_layout

    def create_status_group(self, parent_layout):
        group = QGroupBox("Bot Status")
        layout = QHBoxLayout()
        self.status_label = QLabel("Status: Disconnected")
        self.latency_label = QLabel("Latency: --")
        self.reminder_label = QLabel("Active Reminders: --")
        layout.addWidget(self.status_label)
        layout.addWidget(self.latency_label)
        layout.addWidget(self.reminder_label)
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def create_control_group(self, parent_layout):
        group = QGroupBox("Controls")
        layout = QHBoxLayout()

        buttons = {
            "Start Bot": self.start_bot,
            "Stop Bot": self.stop_bot,
            "Reload Cogs": self.reload_cogs,
            "Check Git": self.check_git_status
        }

        for text, callback in buttons.items():
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def create_git_group(self, parent_layout):
        group = QGroupBox("GitHub Status")
        layout = QVBoxLayout()

        self.git_status_label = QLabel("Git Status: Unknown")
        self.git_commit_label = QLabel("Current Commit: Unknown")
        self.git_update_status = QLabel("Update Status: --")

        update_btn = QPushButton("Update Repo")
        update_btn.clicked.connect(self.update_repo)

        for widget in [self.git_status_label, self.git_commit_label, update_btn, self.git_update_status]:
            layout.addWidget(widget)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def create_cog_group(self, parent_layout):
        group = QGroupBox("Cog Management")
        layout = QHBoxLayout()

        self.cog_entry = QLineEdit()
        load_btn = QPushButton("Load Cog")
        unload_btn = QPushButton("Unload Cog")

        load_btn.clicked.connect(self.load_cog)
        unload_btn.clicked.connect(self.unload_cog)

        for widget in [self.cog_entry, load_btn, unload_btn]:
            layout.addWidget(widget)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def create_log_groups(self, parent_layout):
        # Log Output
        log_group = QGroupBox("Log Output")
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_group.setLayout(QVBoxLayout())
        log_group.layout().addWidget(self.log_text)
        parent_layout.addWidget(log_group)

        # Error Log
        error_group = QGroupBox("Error Log")
        self.error_log_text = QTextEdit()
        self.error_log_text.setReadOnly(True)
        error_group.setLayout(QVBoxLayout())
        error_group.layout().addWidget(self.error_log_text)
        parent_layout.addWidget(error_group)

        self.log_text.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        clear_action = QAction("Clear Log", self.log_text)
        clear_action.triggered.connect(lambda: self.log_text.clear())
        self.log_text.addAction(clear_action)

        self.error_log_text.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        clear_error_action = QAction("Clear Error Log", self.error_log_text)
        clear_error_action.triggered.connect(lambda: self.error_log_text.clear())
        self.error_log_text.addAction(clear_error_action)

        self.log_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.error_log_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def create_cog_status_group(self, parent_layout):
        group = QGroupBox("Active Cogs")
        layout = QVBoxLayout()

        self.cog_list = QListWidget()
        self.cog_list.setAlternatingRowColors(True)
        self.cog_list.setStyleSheet("""
            QListWidget {
                background: rgba(43, 43, 43, 130);
                color: white;
                border: 1px solid rgba(80, 80, 80, 130);
                border-radius: 4px;
            }
            QListWidget::item:alternate {
                background: rgba(54, 54, 54, 130);
            }
        """)

        def update_cogs():
            self.cog_list.clear()
            for cog in sorted(self.bot.extensions):
                self.cog_list.addItem(cog.replace('cogs.', ''))

        update_btn = QPushButton("Refresh")
        update_btn.clicked.connect(update_cogs)

        layout.addWidget(self.cog_list)
        layout.addWidget(update_btn)
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def adjust_layout_spacing(self, main_layout):
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        for layout in self.findChildren(QHBoxLayout) + self.findChildren(QVBoxLayout):
            layout.setSpacing(10)
            layout.setContentsMargins(10, 10, 10, 10)

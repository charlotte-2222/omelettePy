import asyncio
import logging
import queue
import threading

import discord
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QLabel
from git import Repo


class BotControlsMixin:
    def setup_logging(self):
        from gui.main import GUIHandler
        gui_handler = GUIHandler(self)
        logging.getLogger().addHandler(gui_handler)

    def check_msg_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                # Use QMetaObject.invokeMethod for thread-safe updates
                self.log_text.document().setMaximumBlockCount(1000)  # Limit line count
                current = self.log_text.toHtml()
                new_html = current[:-14] + msg + '<br></body></html>'
                self.log_text.setHtml(new_html)
                self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        except queue.Empty:
            pass
        finally:
            self.update_status()

    def update_status(self):
        if self.bot.is_ready():
            self.status_label.setText(f"Status: Connected as {self.bot.user}")
            self.status_label.setStyleSheet("color: #2ecc71")  # Green
            self.latency_label.setText(f"Latency: {self.bot.latency * 1000:.2f}ms")
        else:
            self.status_label.setText("Status: Disconnected")
            self.status_label.setStyleSheet("color: #e74c3c")  # Red
            self.latency_label.setText("Latency: --")

    def start_bot(self):
        def run_bot():
            retries = 3
            for attempt in range(retries):
                try:
                    asyncio.set_event_loop(self.gui_loop)
                    self.gui_loop.run_until_complete(self.bot.start(self.bot.config.TOKEN))
                    break
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.error_log_text.append(f"Bot error: {str(e)}\n")

        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()

    def stop_bot(self):
        async def shutdown():
            try:
                if self.bot and self.bot.is_ready():
                    # First cancel the bot's tasks
                    tasks = [t for t in asyncio.all_tasks(self.gui_loop)
                             if t is not asyncio.current_task()]
                    for task in tasks:
                        task.cancel()

                    # Wait for tasks to complete
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)

                    # Close bot
                    await self.bot.close()
                    self.log_text.append("Bot shutdown completed\n")
            except Exception as e:
                self.error_log_text.append(f"Shutdown error: {str(e)}\n")
            finally:
                # Clean up timers
                if hasattr(self, 'resource_timer'):
                    self.resource_timer.stop()
                if hasattr(self, 'uptime_timer'):
                    self.uptime_timer.stop()
                if hasattr(self, 'reminder_timer'):
                    self.reminder_timer.stop()
                if hasattr(self, 'timer'):
                    self.timer.stop()
                # Update UI
                self.status_label.setText("Status: Disconnected")
                self.status_label.setStyleSheet("color: #e74c3c")
                self.latency_label.setText("Latency: --")
                self.uptime_label.setText("Uptime: --:--:--")

        if hasattr(self, 'bot_thread'):
            try:
                # Run shutdown in the GUI loop
                future = asyncio.run_coroutine_threadsafe(shutdown(), self.gui_loop)
                future.result(timeout=5.0)
            except Exception as e:
                self.error_log_text.append(f"Shutdown error: {str(e)}\n")
                # Force cleanup remaining tasks
                for task in asyncio.all_tasks(self.gui_loop):
                    task.cancel()

    def reload_cogs(self):
        async def _reload():
            try:
                for extension in self.bot.extensions.copy():
                    await self.bot.reload_extension(extension)
                self.log_text.append("All cogs reloaded successfully\n")
            except Exception as e:
                self.error_log_text.append(f"Error reloading cogs: {str(e)}\n")

        asyncio.run_coroutine_threadsafe(_reload(), self.gui_loop)

    def load_cog(self):
        cog_name = self.cog_entry.text().strip()
        if not cog_name:
            return

        async def _load():
            try:
                await self.bot.load_extension(f"cogs.{cog_name}")
                self.log_text.append(f"Loaded cog: {cog_name}\n")
            except Exception as e:
                self.error_log_text.append(f"Error loading cog {cog_name}: {str(e)}\n")

        asyncio.run_coroutine_threadsafe(_load(), self.gui_loop)

    def unload_cog(self):
        cog_name = self.cog_entry.text().strip()
        if not cog_name:
            return

        async def _unload():
            try:
                await self.bot.unload_extension(f"cogs.{cog_name}")
                self.log_text.append(f"Unloaded cog: {cog_name}\n")
            except Exception as e:
                self.error_log_text.append(f"Error unloading cog {cog_name}: {str(e)}\n")

        asyncio.run_coroutine_threadsafe(_unload(), self.gui_loop)

    def check_git_status(self):
        try:
            repo = Repo(".")
            status = repo.git.status()
            current = repo.head.commit
            self.git_status_label.setText(f"Git Status: {repo.git.status(porcelain=True) or 'Clean'}")
            self.git_commit_label.setText(f"Current Commit: {current.hexsha[:7]}")
        except Exception as e:
            self.git_status_label.setText("Git Status: Error")
            self.error_log_text.append(f"Git error: {str(e)}\n")

    def update_repo(self):
        try:
            repo = Repo(".")
            current = repo.head.commit
            repo.remotes.origin.pull()
            if current != repo.head.commit:
                self.git_update_status.setText("Update Status: Updated to new version")
                self.git_update_status.setStyleSheet("color: #2ecc71")
            else:
                self.git_update_status.setText("Update Status: Already up to date")
            self.check_git_status()
        except Exception as e:
            self.git_update_status.setText("Update Status: Error")
            self.git_update_status.setStyleSheet("color: #e74c3c")
            self.error_log_text.append(f"Update error: {str(e)}\n")

    def add_uptime_monitor(self):
        # Initialize label with proper styling
        self.uptime_label = QLabel("Uptime: --:--:--")
        self.uptime_label.setStyleSheet("color: white;")
        self.statusBar().addPermanentWidget(self.uptime_label)

        def update_uptime():
            try:
                if hasattr(self.bot, 'is_ready') and self.bot.is_ready() and hasattr(self.bot, 'uptime'):
                    delta = discord.utils.utcnow() - self.bot.uptime
                    hours = delta.days * 24 + delta.seconds // 3600
                    minutes = (delta.seconds % 3600) // 60
                    seconds = delta.seconds % 60
                    self.uptime_label.setText(f"Uptime: {hours}:{minutes:02d}:{seconds:02d}")
                else:
                    self.uptime_label.setText("Uptime: --:--:--")
            except Exception as e:
                self.error_log_text.append(f"Uptime error: {str(e)}\n")

        # Store timer as instance variable
        self.uptime_timer = QTimer(self)
        self.uptime_timer.timeout.connect(update_uptime)
        self.uptime_timer.start(1000)  # Update every second

    def add_reminder_monitor(self):
        def update_reminders():
            try:
                if hasattr(self.bot, 'is_ready') and self.bot.is_ready() and self.bot.reminder:
                    active_reminders = len(self.bot.reminder._current_timer)
                    self.reminder_label.setText(f"Active Reminders: {active_reminders}")
                else:
                    self.reminder_label.setText("No active reminders")
            except Exception as e:
                self.error_log_text.append(f"Reminder monitor error: {str(e)}\n")

        # Store timer as instance variable
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(update_reminders)
        self.reminder_timer.start(1000)

    def run(self):
        self.show()

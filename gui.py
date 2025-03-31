import asyncio
import logging
import queue
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

import sv_ttk
from git import Repo

import utilFunc.config


class BotGUI:
    def __init__(self, bot):
        self.bot = bot
        # self.config=Config("bot")
        self.root = tk.Tk()
        self.root.title("OmelettePy Bot Control Panel")
        self.root.geometry("1000x700")

        # Message queue for thread-safe GUI updates
        self.msg_queue = queue.Queue()

        # Set up the bot's event loop for GUI
        self.gui_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.gui_loop)

        self.setup_gui()
        self.setup_logging()

        # Start checking message queue
        self.root.after(100, self.check_msg_queue)

    def setup_gui(self):
        # Set theme
        sv_ttk.use_dark_theme()

        # Create main container
        main_container = ttk.Frame(self.root, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Status Frame
        status_frame = ttk.LabelFrame(main_container, text="Bot Status", padding="5")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        self.status_label = ttk.Label(status_frame, text="Status: Disconnected")
        self.status_label.grid(row=0, column=0, sticky=tk.W)

        self.latency_label = ttk.Label(status_frame, text="Latency: --")
        self.latency_label.grid(row=0, column=1, padx=20, sticky=tk.W)

        # Control Frame
        control_frame = ttk.LabelFrame(main_container, text="Controls", padding="5")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)

        ttk.Button(control_frame, text="Start Bot", command=self.start_bot).grid(row=0, column=0, padx=5)
        ttk.Button(control_frame, text="Stop Bot", command=self.stop_bot).grid(row=0, column=1, padx=5)
        ttk.Button(control_frame, text="Reload Cogs", command=self.reload_cogs).grid(row=0, column=2, padx=5)
        ttk.Button(control_frame, text="Check Git", command=self.check_git_status).grid(row=0, column=3, padx=5)

        # Reminder Stats Frame
        reminder_frame = ttk.LabelFrame(main_container, text="Reminder System", padding="5")
        reminder_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)

        self.reminder_count = ttk.Label(reminder_frame, text="Active Reminders: --")
        self.reminder_count.grid(row=0, column=0, sticky=tk.W)

        # Log Frame
        log_frame = ttk.LabelFrame(main_container, text="Log Output", padding="5")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, fg="dodgerblue")
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Error Log Frame
        error_log_frame = ttk.LabelFrame(main_container, text="Error Log", padding="5")
        error_log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        self.error_log_text = scrolledtext.ScrolledText(error_log_frame, height=10, fg="red")
        self.error_log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # GitHub Status Frame
        git_status_frame = ttk.LabelFrame(main_container, text="GitHub Status", padding="5")
        git_status_frame.grid(row=0, column=2, sticky=(tk.W, tk.E), pady=5, padx=10)
        self.git_status_label = ttk.Label(git_status_frame, text="Git Status: Unknown")
        self.git_status_label.grid(row=0, column=0, sticky=tk.W)
        self.git_commit_label = ttk.Label(git_status_frame, text="Current Commit: Unknown")
        self.git_commit_label.grid(row=1, column=1, padx=20, sticky=tk.W)
        # GitHub Update Frame
        git_update_frame = ttk.LabelFrame(main_container, text="GitHub Update", padding="5")
        git_update_frame.grid(row=1, column=2, sticky=(tk.W, tk.E), pady=5, padx=10)
        self.git_update_button = ttk.Button(git_update_frame, text="Update Repo", command=self.update_repo)
        self.git_update_button.grid(row=0, column=0, padx=5)
        self.git_update_status = ttk.Label(git_update_frame, text="Update Status: Unknown")
        self.git_update_status.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)

        # Configure grid weights
        main_container.columnconfigure(0, weight=1)
        main_container.columnconfigure(1, weight=1)
        main_container.columnconfigure(2, weight=0)  # Fixed width for GitHub column
        main_container.rowconfigure(2, weight=1)
        main_container.rowconfigure(3, weight=1)

    def setup_logging(self):
        class GUIHandler(logging.Handler):
            def __init__(self, gui):
                super().__init__()
                self.gui = gui

            def emit(self, record):
                msg = self.format(record)
                if record.levelno >= logging.ERROR:
                    self.gui.error_log_text.insert(tk.END, msg + '\n')
                    self.gui.error_log_text.see(tk.END)
                else:
                    self.gui.msg_queue.put(msg)

        # Configure logging
        gui_handler = GUIHandler(self)
        gui_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s'))
        logging.getLogger().addHandler(gui_handler)

    def check_msg_queue(self):
        """Check for new messages in the queue and update GUI"""
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self.log_text.insert(tk.END, msg + '\n')
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_msg_queue)
            self.update_status()

    def update_status(self):
        """Update bot status information"""
        if self.bot.is_ready():
            self.status_label.config(text=f"Status: Connected as {self.bot.user}")
            self.latency_label.config(text=f"Latency: {self.bot.latency * 1000:.2f}ms")

            # Update reminder count if reminder cog is loaded
            reminder_cog = self.bot.get_cog('Reminder')
            if reminder_cog:
                asyncio.run_coroutine_threadsafe(
                    self.update_reminder_count(reminder_cog),
                    self.bot.loop
                )

    async def update_reminder_count(self, reminder_cog):
        """Update reminder count asynchronously"""
        count = await self.bot.pool.fetchval("SELECT COUNT(*) FROM reminders")
        self.reminder_count.config(text=f"Active Reminders: {count}")

    def start_bot(self):
        """Start the bot in a separate thread"""
        if self.bot.is_ready():
            self.error_log_text.insert(tk.END, "Bot is already running!\n")
            return

        def run_bot():
            asyncio.set_event_loop(asyncio.new_event_loop())
            try:
                token = utilFunc.config.TOKEN
                self.bot.run(token)
            except Exception as e:
                self.msg_queue.put(f"Error starting bot: {str(e)}")

        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        self.log_text.insert(tk.END, "Starting bot...\n")

    def stop_bot(self):
        """Stop the bot"""
        asyncio.run_coroutine_threadsafe(self.bot.close(), self.bot.loop)
        self.log_text.insert(tk.END, "Stopping bot...\n")

    def reload_cogs(self):
        """Reload all cogs"""

        async def _reload_cogs():
            for extension in list(self.bot.extensions):
                try:
                    await self.bot.reload_extension(extension)
                    self.msg_queue.put(f"Reloaded {extension}")
                except Exception as e:
                    self.msg_queue.put(f"Failed to reload {extension}: {e}")

        asyncio.run_coroutine_threadsafe(_reload_cogs(), self.bot.loop)

    def check_git_status(self):
        """Check Git repository status"""
        try:
            repo = Repo('.')
            status = repo.git.status()
            current = repo.head.commit

            self.git_status_label.config(text=f"Git Status: {'Clean' if not repo.is_dirty() else 'Dirty'}")
            self.git_commit_label.config(text=f"Current Commit: {current.hexsha[:7]}")

            self.log_text.insert(tk.END, f"Git Status:\n{status}\n")
        except Exception as e:
            self.error_log_text.insert(tk.END, f"Error checking git status: {str(e)}\n")

    def update_repo(self):
        """Update Git repository"""
        try:
            repo = Repo('.')

            # Fetch updates
            self.git_update_status.config(text="Status: Fetching updates...")
            repo.remotes.origin.fetch()

            # Pull changes
            self.git_update_status.config(text="Status: Pulling changes...")
            pull_info = repo.remotes.origin.pull()

            if pull_info:
                self.git_update_status.config(text="Status: Update successful")
                self.log_text.insert(tk.END, f"Successfully pulled updates: {pull_info[0].note}\n")

                # Update git status display
                self.check_git_status()
            else:
                self.git_update_status.config(text="Status: No updates available")

        except Exception as e:
            self.git_update_status.config(text="Status: Update failed")
            self.error_log_text.insert(tk.END, f"Error updating repository: {str(e)}\n")

    def run(self):
        """Start the GUI main loop"""
        self.root.mainloop()

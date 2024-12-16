import re
import sqlite3
from datetime import datetime, timedelta
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.tags import cursor

conn = sqlite3.connect("tags.db")  # this table is withing the tags db, no need for a new DB
cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    channel_id TEXT,
    reminder_text TEXT NOT NULL,
    remind_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()
print("Table 'reminders' loaded successfully.")
conn.close()


class Reminders(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.check_reminders.start()  # start background task to check reminders

    def cog_unload(self) -> None:
        self.check_reminders.cancel()  # stop task if cog unloaded

    @app_commands.command(name="add_reminder", description="Set a reminder")
    @app_commands.describe(
        reminder_text="What do you want to be reminded about?",
        time_input="Specify the time: e.g., '1m', '10min', '11:33 AM', or 'on 2024-12-20 11:33 AM'.",
        delivery_method="Specify the delivery method: 'dm' for direct message, 'channel' for this text channel."
    )
    async def add_reminder(
            self,
            interaction: discord.Interaction,
            reminder_text: str,
            time_input: str,
            delivery_method: Literal["dm", "channel"] = "dm"  # Default to dm
    ) -> None:
        user_id = str(interaction.user.id)
        channel_id = str(interaction.channel_id)

        # Determine the reminder time
        now = datetime.utcnow()
        remind_at = None

        # Handle time input
        match_minutes = re.match(r"(\d+)\s*(m|min|minutes?)?", time_input.lower())
        if match_minutes:
            minutes = int(match_minutes.group(1))
            remind_at = now + timedelta(minutes=minutes)
        elif time_input.lower().startswith("on "):
            try:
                remind_at = datetime.strptime(time_input.replace("on ", "").strip(), "%Y-%m-%d %I:%M %p")
            except ValueError:
                await interaction.response.send_message(
                    "Invalid datetime format. Use 'on YYYY-MM-DD hh:mm AM/PM'."
                )
                return
        else:
            try:
                time_only = datetime.strptime(time_input.strip(), "%I:%M %p").time()
                remind_at = datetime.combine(now.date(), time_only)
                if remind_at < now:
                    remind_at += timedelta(days=1)
            except ValueError:
                await interaction.response.send_message(
                    "Invalid time format. Use 'hh:mm AM/PM' or '1m' for short input."
                )
                return

        if not remind_at:
            await interaction.response.send_message(
                "Invalid time input. Use formats like '1m', '11:33 AM', or 'on YYYY-MM-DD hh:mm AM/PM'."
            )
            return

        # Insert the reminder into the database
        conn = sqlite3.connect("tags.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO reminders (user_id, channel_id, reminder_text, remind_at)
            VALUES (?, ?, ?, ?);
            """,
            (user_id, channel_id if delivery_method == "channel" else None, reminder_text, remind_at)
        )
        conn.commit()
        conn.close()

        # Confirm the reminder
        await interaction.response.send_message(
            f"Reminder set for **{remind_at.strftime('%Y-%m-%d %I:%M %p')} UTC!**\n"
            f"It will be delivered via {'DM' if delivery_method == 'dm' else 'this channel'}."
        )

    # List reminders command
    @app_commands.command(name="list_reminders", description="List all your reminders")
    async def list_reminders(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)

        # Fetch reminders from the database
        conn = sqlite3.connect("tags.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, reminder_text, remind_at
            FROM reminders
            WHERE user_id = ?
            ORDER BY remind_at ASC
            """,
            (user_id,)
        )
        reminders = cursor.fetchall()
        conn.close()

        if not reminders:
            await interaction.response.send_message("You have no reminders set.")
            return

        # Prepare the reminders to display
        reminder_list = []
        for reminder_id, reminder_text, remind_at in reminders:
            try:
                # Parse the remind_at value, accounting for microseconds
                remind_time = datetime.strptime(remind_at, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                # Fallback if no microseconds
                remind_time = datetime.strptime(remind_at, "%Y-%m-%d %H:%M:%S")

            reminder_list.append(
                f"**ID:** {reminder_id}\n"
                f"**Time:** {remind_time.strftime('%Y-%m-%d %I:%M %p')} UTC\n"
                f"**Text:** {reminder_text}"

            )

        # Send the list of reminders
        await interaction.response.send_message(
            "*Your reminders:*\n\n" + "\n".join(reminder_list)
        )

    # Delete a reminder command
    @app_commands.command(name="delete_reminder", description="Delete a reminder by ID")
    @app_commands.describe(reminder_id="The ID of the reminder to delete")
    async def delete_reminder(self, interaction: discord.Interaction, reminder_id: int) -> None:
        conn = sqlite3.connect("tags.db")
        cursor = conn.cursor()

        # Attempt to delete the reminder
        cursor.execute(
            """
            DELETE FROM reminders WHERE id = ? AND user_id = ?;
            """,
            (reminder_id, str(interaction.user.id))
        )
        changes = conn.total_changes
        conn.commit()
        conn.close()

        if changes > 0:
            await interaction.response.send_message(f"Reminder ID {reminder_id} deleted successfully!")
        else:
            await interaction.response.send_message(f"Could not find a reminder with ID {reminder_id}.")

    # Background task to check reminders
    @tasks.loop(seconds=30)  # Adjust the interval as needed
    async def check_reminders(self) -> None:
        conn = sqlite3.connect("tags.db")
        cursor = conn.cursor()

        # Fetch reminders that are due
        current_time = datetime.utcnow()
        cursor.execute(
            """
            SELECT id, user_id, channel_id, reminder_text FROM reminders
            WHERE remind_at <= ?;
            """,
            (current_time,)
        )
        due_reminders = cursor.fetchall()

        # Delete triggered reminders and notify users
        for reminder_id, user_id, channel_id, text in due_reminders:
            # Notify the user
            user = self.bot.get_user(int(user_id))
            if user:
                try:
                    await user.send(f"⏰ **Reminder:**\n"
                                    f"{text}")
                except discord.Forbidden:
                    # Fallback to channel if DM fails
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        await channel.send(f"⏰ <@{user_id}>\n"
                                           f"**Reminder:**\n"
                                           f"{text}")

            # Remove the reminder from the database
            cursor.execute("DELETE FROM reminders WHERE id = ?;", (reminder_id,))

        conn.commit()
        conn.close()

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reminders(bot))

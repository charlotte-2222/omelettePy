import logging

import aiohttp
import discord
from aiohttp.web_fileresponse import extension
from discord.ext import commands

from utilFunc.config import TOKEN


class LoggingFormatter(logging.Formatter):
    # Colors
    black = "\x1b[30m"
    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    gray = "\x1b[38m"
    # Styles
    reset = "\x1b[0m"
    bold = "\x1b[1m"

    COLORS = {
        logging.DEBUG: gray + bold,
        logging.INFO: blue + bold,
        logging.WARNING: yellow + bold,
        logging.ERROR: red,
        logging.CRITICAL: red + bold,
    }

    def format(self, record):
        log_color = self.COLORS[record.levelno]
        format = "(black){asctime}(reset) (levelcolor){levelname:<8}(reset) (green){name}(reset) {message}"
        format = format.replace("(black)", self.black + self.bold)
        format = format.replace("(reset)", self.reset)
        format = format.replace("(levelcolor)", log_color)
        format = format.replace("(green)", self.green + self.bold)
        formatter = logging.Formatter(format, "%Y-%m-%d %H:%M:%S", style="{")
        return formatter.format(record)


logger = logging.getLogger("discord_bot")
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(LoggingFormatter())
# File handler
file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
file_handler_formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", "%Y-%m-%d %H:%M:%S", style="{"
)
file_handler.setFormatter(file_handler_formatter)

# Add the handlers
logger.addHandler(console_handler)
logger.addHandler(file_handler)


# def _get_prefix(bot, message):
#     return commands.when_mentioned(bot, message)


class OmelettePy(commands.AutoShardedBot):
    bot_app_info: discord.AppInfo
    user: discord.ClientUser
    def __init__(self):
        allowed_mentions = discord.AllowedMentions(roles=False, everyone=False, users=True)
        intents = discord.Intents(
            guilds=True,
            members=True,
            messages=True,
            reactions=True,
            message_content=True
        )
        super().__init__(command_prefix=commands.when_mentioned,
                         case_insensitive=True,
                         heartbeat_timeout=150.0,
                         intents=intents,
                         allowed_mentions=allowed_mentions,
                         enable_debug_events=True
                         )
        self.initial_extensions=[
            'cogs.events',
            'cogs.owner',
            'cogs.help',
            'cogs.tags',
            'cogs.misc',
            'cogs.tictactoe'
        ]
    async def setup_hook(self) -> None:
        # self.background_tasks.start()
        self.session = aiohttp.ClientSession()
        self.bot_app_info = await self.application_info()
        self.owner_id = self.bot_app_info.team.owner_id
        try:
            for ext in self.initial_extensions:
                await self.load_extension(ext)
        except Exception as e:
                logger.exception('Failed to load extension %s.',extension)

    @property
    def owner(self) -> discord.User:
        return self.bot_app_info.owner


    async def close(self) -> None:
        await super().close()
        await self.session.close()




bot = OmelettePy()
bot.run(TOKEN)





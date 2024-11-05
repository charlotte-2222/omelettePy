import logging

import aiohttp
import bungio
import discord
from aiohttp.web_fileresponse import extension
from discord.ext import commands

from utilFunc.config import TOKEN, BNG_API_KEY, BNG_OAUTH_CLIENT_ID, BNG_OAUTH_URL

bng_client=bungio.Client(
    bungie_client_id=BNG_OAUTH_CLIENT_ID,
    bungie_client_secret=BNG_OAUTH_URL,
    bungie_token=BNG_API_KEY
)


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


def _get_prefix(bot, message):
    prefixes = ['^']
    if not message.guild:
        return ['?', '^']
    return commands.when_mentioned_or(*prefixes)(bot, message)


class OmelettePy(commands.Bot):
    bot_app_info: discord.AppInfo
    def __init__(self):
        allowed_mentions = discord.AllowedMentions(roles=False, everyone=False, users=True)
        intents = discord.Intents(
            guilds=True,
            members=True,
            messages=True,
            reactions=True,
            message_content=True
        )
        super().__init__(command_prefix=_get_prefix,
                         case_insensitive=True,
                         strip_after_prefix=True,
                         intents=intents,
                         allowed_mentions=allowed_mentions
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

    # @tasks.loop(minutes=3)
    # async def background_tasks(self) -> None:
    #     statuses = ['/help',
    #                 '/quote',
    #                 '/tag',
    #                 'edging rn',
    #                 '/new-tag']
    #     activity = discord.Activity(
    #         type=discord.ActivityType.custom,
    #         name="Custom Status",
    #         state=random.choice(statuses)
    #     )
    #     await self.change_presence(activity=activity)

    # @background_tasks.before_loop
    # async def before_my_tasks(self) -> None:
    #     await self.wait_until_ready()


    async def close(self) -> None:
        await super().close()
        await self.session.close()




bot = OmelettePy()
bot.run(TOKEN)





from __future__ import annotations

import logging
from typing import Iterable, AsyncIterator, TYPE_CHECKING

import aiohttp
import asyncpg
import discord
from discord.ext import commands

# ai shit
from GPT.chatgpt import ChatGPT
from GPT.memory import Memory
from GPT.models import OpenAIModel
from utilFunc.config import TOKEN, OPEN_AI_KEY, OPEN_AI_MODEL_ENGINE

if TYPE_CHECKING:
    pass


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

models = OpenAIModel(api_key=OPEN_AI_KEY,
                     model_engine=OPEN_AI_MODEL_ENGINE)
memory = Memory(
    system_message="You are an AI focused on assisting users with general utility functions in concise and easy to understand ways.")
chatgpt = ChatGPT(models, memory)

def get_prefix(bot, message):
    prefixes = ['>>']
    if not message.guild:
        return ['?', '!']
    return commands.when_mentioned_or(*prefixes)(bot, message)


class OmelettePy(commands.AutoShardedBot):
    bot_app_info: discord.AppInfo
    user: discord.ClientUser
    pool: asyncpg.Pool
    def __init__(self):
        allowed_mentions = discord.AllowedMentions(roles=False, everyone=False, users=True)
        intents = discord.Intents(
            guilds=True,
            members=True,
            messages=True,
            reactions=True,
            message_content=True
        )
        super().__init__(command_prefix=get_prefix,
                         strip_after_prefix=True,
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
            'cogs.tictactoe',
            'cogs.git_stuff',
            'cogs.reminders',
            # 'cogs.gpt_cog'
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
            logger.exception('Failed to load extension %s.', e)

    @property
    def owner(self) -> discord.User:
        return self.bot_app_info.owner

    async def resolve_member_ids(self, guild: discord.Guild, member_ids: Iterable[int]) -> AsyncIterator[
        discord.Member]:
        """Bulk resolves member IDs to member instances, if possible.

        Members that can't be resolved are discarded from the list.

        This is done lazily using an asynchronous iterator.

        Note that the order of the resolved members is not the same as the input.

        Parameters
        -----------
        guild: Guild
            The guild to resolve from.
        member_ids: Iterable[int]
            An iterable of member IDs.

        Yields
        --------
        Member
            The resolved members.
        """

        needs_resolution = []
        for member_id in member_ids:
            member = guild.get_member(member_id)
            if member is not None:
                yield member
            else:
                needs_resolution.append(member_id)

        total_need_resolution = len(needs_resolution)
        if total_need_resolution == 1:
            shard: discord.ShardInfo = self.get_shard(guild.shard_id)  # type: ignore  # will never be None
            if shard.is_ws_ratelimited():
                try:
                    member = await guild.fetch_member(needs_resolution[0])
                except discord.HTTPException:
                    pass
                else:
                    yield member
            else:
                members = await guild.query_members(limit=1, user_ids=needs_resolution, cache=True)
                if members:
                    yield members[0]
        elif total_need_resolution <= 100:
            # Only a single resolution call needed here
            resolved = await guild.query_members(limit=100, user_ids=needs_resolution, cache=True)
            for member in resolved:
                yield member
        else:
            # We need to chunk these in bits of 100...
            for index in range(0, total_need_resolution, 100):
                to_resolve = needs_resolution[index: index + 100]
                members = await guild.query_members(limit=100, user_ids=to_resolve, cache=True)
                for member in members:
                    yield member

    # async def get_context(self, origin: Union[discord.Interaction, discord.Message], /, *, cls=Context) -> Context:
    # return await super().get_context(origin, cls=cls)


    async def close(self) -> None:
        await super().close()
        await self.session.close()




bot = OmelettePy()
bot.run(TOKEN)





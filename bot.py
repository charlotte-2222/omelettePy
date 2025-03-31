from __future__ import annotations

import asyncio
import datetime
import logging
import logging.handlers
from collections import defaultdict
from logging import exception
from typing import Iterable, AsyncIterator, TYPE_CHECKING, Optional, Union

import aiohttp
import asyncpg
import discord
from discord.ext import commands

import utilFunc.config
from gui import BotGUI
from utilFunc.context import Context

if TYPE_CHECKING:
    from cogs.reminders import Reminder
    from utilFunc.config import Config as ConfigCog
    # from launcher import create_pool

from dotenv import load_dotenv

load_dotenv()

description = """
I'm a general purpose bot written in Python by Charlotte. I'm still in development, but I hope to add a lot of new features!
"""

log = logging.getLogger('ommiepy')


initial_extensions = [
    'cogs.events',
    'cogs.owner',
    'cogs.help',
    'cogs.tags',
    'cogs.misc',
    'cogs.tictactoe',
    'cogs.git_stuff',
    'cogs.reminders',
    'cogs.api',
    # 'cogs.gpt_cog'
]


class RemoveNoise(logging.Filter):
    def __init__(self):
        super().__init__(name='discord.state')

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelname == 'WARNING' and 'referencing an unknown' in record.msg:
            return False
        return True



def setup_logging():
    log = logging.getLogger()

    # Remove any existing handlers to avoid duplicates
    for handler in log.handlers[:]:
        log.removeHandler(handler)

    # Set the base logging level
    log.setLevel(logging.INFO)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}',
                                       datefmt='%Y-%m-%d %H:%M:%S',
                                       style='{')
    console_handler.setFormatter(console_format)
    log.addHandler(console_handler)

    # File Handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename='ommiepy.log',
        encoding='utf-8',
        maxBytes=32 * 1024 * 1024,  # 32 MiB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}',
                                    datefmt='%Y-%m-%d %H:%M:%S',
                                    style='{')
    file_handler.setFormatter(file_format)
    log.addHandler(file_handler)

    # Discord.py specific logging
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.INFO)
    discord_http = logging.getLogger('discord.http')
    discord_http.setLevel(logging.WARNING)

    # Add the noise filter
    discord_logger.addFilter(RemoveNoise())

    return log


def _prefix_callable(bot: OmelettePy, msg: discord.Message):
    prefixes = ['>>']
    if msg.guild is None:
        return ['?', '!']
    return commands.when_mentioned_or(*prefixes)(bot, msg)


async def create_pool() -> asyncpg.Pool:
    try:
        return await asyncpg.create_pool(
            database=utilFunc.config.DB_NAME,
            user=utilFunc.config.DB_USER,
            password=utilFunc.config.DB_PASSWORD,
            host=utilFunc.config.DB_HOST,
            port=utilFunc.config.DB_PORT
        )
    except exception as e:
        print(f"Failed to create DB pool: {e}")


class OmelettePy(commands.AutoShardedBot):
    pool: asyncpg.Pool
    bot_app_info: discord.AppInfo
    user: discord.ClientUser

    # logging_handler: Any
    def __init__(self):
        allowed_mentions = discord.AllowedMentions(roles=False, everyone=False, users=True)
        intents = discord.Intents(
            guilds=True,
            members=True,
            messages=True,
            reactions=True,
            message_content=True
        )
        self.log = setup_logging()
        super().__init__(command_prefix=_prefix_callable,
                         description=description,
                         strip_after_prefix=True,
                         case_insensitive=True,
                         heartbeat_timeout=150.0,
                         intents=intents,
                         allowed_mentions=allowed_mentions,
                         enable_debug_events=True
                         )
        self.pool = None
        self.resumes: defaultdict[int, list[datetime.datetime]] = defaultdict(list)
        self.identifies: defaultdict[int, list[datetime.datetime]] = defaultdict(list)


    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        self.pool = await create_pool()
        self.bot_app_info = await self.application_info()
        self.owner_id = self.bot_app_info.team.owner_id


        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                self.log.info('Loaded extension %s.', extension)
            except Exception as e:
                self.log.exception('Failed to load extension %s.',
                                   extension + f'\n{e}')

    @property
    def owner(self) -> discord.User:
        return self.bot_app_info.owner

    async def on_command_error(self, ctx: Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.author.send('This command cannot be used in private messages.')
        elif isinstance(error, commands.DisabledCommand):
            await ctx.author.send('Sorry. This command is disabled and cannot be used.')
        elif isinstance(error, commands.CommandInvokeError):
            original = error.original
            if not isinstance(original, discord.HTTPException):
                log.exception('In %s:', ctx.command.qualified_name, exc_info=original)
        elif isinstance(error, commands.ArgumentParsingError):
            await ctx.send(str(error))

    async def query_member_named(
            self, guild: discord.Guild, argument: str, *, cache: bool = False
    ) -> Optional[discord.Member]:
        """Queries a member by their name, name + discrim, or nickname.

        Parameters
        ------------
        guild: Guild
            The guild to query the member in.
        argument: str
            The name, nickname, or name + discrim combo to check.
        cache: bool
            Whether to cache the results of the query.

        Returns
        ---------
        Optional[Member]
            The member matching the query or None if not found.
        """
        if len(argument) > 5 and argument[-5] == '#':
            username, _, discriminator = argument.rpartition('#')
            members = await guild.query_members(username, limit=100, cache=cache)
            return discord.utils.get(members, name=username, discriminator=discriminator)
        else:
            members = await guild.query_members(argument, limit=100, cache=cache)
            return discord.utils.find(lambda m: m.name == argument or m.nick == argument, members)

    async def get_or_fetch_member(self, guild: discord.Guild, member_id: int) -> Optional[discord.Member]:
        """Looks up a member in cache or fetches if not found.

        Parameters
        -----------
        guild: Guild
            The guild to look in.
        member_id: int
            The member ID to search for.

        Returns
        ---------
        Optional[Member]
            The member or None if not found.
        """

        member = guild.get_member(member_id)
        if member is not None:
            return member

        shard: discord.ShardInfo = self.get_shard(guild.shard_id)  # type: ignore  # will never be None
        if shard.is_ws_ratelimited():
            try:
                member = await guild.fetch_member(member_id)
            except discord.HTTPException:
                return None
            else:
                return member

        members = await guild.query_members(limit=1, user_ids=[member_id], cache=True)
        if not members:
            return None
        return members[0]

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

    async def on_ready(self):
        if not hasattr(self, 'uptime'):
            self.uptime = discord.utils.utcnow()
        self.log.info('Logged in as %s (ID: %s)', self.user.name, self.user.id)

    async def on_shard_resumed(self, shard_id: int) -> None:
        log.info('Shard ID %s has resumed...', shard_id)
        self.resumes[shard_id].append(discord.utils.utcnow())

    async def get_context(self, origin: Union[discord.Interaction, discord.Message], /, *, cls=Context) -> Context:
        return await super().get_context(origin, cls=cls)

    async def process_commands(self, message: discord.Message):
        ctx = await self.get_context(message)
        if ctx.command is None:
            return
        await self.invoke(ctx)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        await self.process_commands(message)

    async def close(self) -> None:
        self.log.info('Closing bot...')
        try:
            # cancel running tasks
            for task in asyncio.all_tasks(self.loop):
                if task is not asyncio.current_task(self.loop):
                    task.cancel()
            # close connection
            if hasattr(self, 'session'):
                await self.session.close()
            if hasattr(self, 'pool'):
                await self.pool.close()

            # call parent close
            await super().close()
            self.log.info('Bot closed.')
        except Exception as e:
            self.log.exception('Error while closing bot: %s', e)

    @property
    def config(self):
        return utilFunc.config

    @property
    def reminder(self) -> Optional[Reminder]:
        return self.get_cog('Reminders')

    @property
    def config_cog(self) -> Optional[ConfigCog]:
        return self.get_cog('Config')  # type: ignore


def main():
    log = setup_logging()
    try:
        log.info('=' * 50)  # Add separator line before session start
        log.info('Starting new bot session')
        log.info('=' * 50)
        # Initialize the bot
        bot = OmelettePy()
        # Load the GUI and start the bot
        gui = BotGUI(bot)
        gui.run()
    except KeyboardInterrupt:
        log.info('Bot stopped by user.')
    except Exception as e:
        log.exception('Fatal error: %s', e)
        return 1
    finally:
        log.info('=' * 50)  # Add separator line after session end
        log.info('End of bot session')
        log.info('=' * 50)
        handlers = log.handlers[:]
        for hdlr in handlers:
            hdlr.close()
            log.removeHandler(hdlr)
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

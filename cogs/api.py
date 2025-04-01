from __future__ import annotations

import io
import os
import re
import zlib
from typing import TYPE_CHECKING, Generator, NamedTuple, Optional, Union

import asyncpg
import discord
import lxml.etree as etree
from discord import app_commands
from discord.ext import commands

from utilFunc import fuzzy

if TYPE_CHECKING:
    from utilFunc.context import Context, GuildContext
    from asyncpg import Record

# taken from Rapptz/Robodanny, removing a lot of things I don't necessarily need however.
# Useful functions that fulfill the desired role of the bot.

DISCORD_API_ID = 81384788765712384
DISCORD_BOTS_ID = 110373943822540800
USER_BOTS_ROLE = 178558252869484544
CONTRIBUTORS_ROLE = 111173097888993280
DISCORD_PY_ID = 84319995256905728
DISCORD_PY_GUILD = 336642139381301249
DISCORD_PY_JP_CATEGORY = 490287576670928914
DISCORD_PY_JP_STAFF_ROLE = 490320652230852629
DISCORD_PY_PROF_ROLE = 381978395270971407
DISCORD_PY_HELPER_ROLE = 558559632637952010
# DISCORD_PY_HELP_CHANNELS = (381965515721146390, 738572311107469354, 985299059441025044)
DISCORD_PY_HELP_CHANNEL = 985299059441025044

RTFM_PAGE_TYPES = {
    'stable': 'https://discordpy.readthedocs.io/en/stable',
    'stable-jp': 'https://discordpy.readthedocs.io/ja/stable',
    'latest': 'https://discordpy.readthedocs.io/en/latest',
    'latest-jp': 'https://discordpy.readthedocs.io/ja/latest',
    'python': 'https://docs.python.org/3',
    'python-jp': 'https://docs.python.org/ja/3',
}


class SphinxObjectFileReader:
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer: bytes):
        self.stream = io.BytesIO(buffer)

    def readline(self) -> str:
        return self.stream.readline().decode('utf-8')

    def skipline(self) -> None:
        self.stream.readline()

    def read_compressed_chunks(self) -> Generator[bytes, None, None]:
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self) -> Generator[str, None, None]:
        buf = b''
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b'\n')
            while pos != -1:
                yield buf[:pos].decode('utf-8')
                buf = buf[pos + 1:]
                pos = buf.find(b'\n')


class BotUser(commands.Converter):
    async def convert(self, ctx: GuildContext, argument: str):
        if not argument.isdigit():
            raise commands.BadArgument('Not a valid bot user ID.')
        try:
            user = await ctx.bot.fetch_user(int(argument))
        except discord.NotFound:
            raise commands.BadArgument('Bot user not found (404).')
        except discord.HTTPException as e:
            raise commands.BadArgument(f'Error fetching bot user: {e}')
        else:
            if not user.bot:
                raise commands.BadArgument('This is not a bot.')
            return user


class RepositoryExample(NamedTuple):
    path: str
    url: str

    def to_choice(self) -> discord.app_commands.Choice[str]:
        return discord.app_commands.Choice(name=self.path, value=self.path)


class API(commands.Cog):
    """Discord API exclusive things."""

    faq_entries: dict[str, str]
    _rtfm_cache: dict[str, dict[str, str]]
    repo_examples: list[RepositoryExample]

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.issue = re.compile(r'##(?P<number>[0-9]+)')

    async def cog_load(self) -> None:
        self.db = await asyncpg.connect(database="OmelettePy",
                                        user="postgres",
                                        password="Astra",
                                        host="localhost",
                                        port="5432")


    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='\N{PERSONAL COMPUTER}')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != DISCORD_API_ID:
            return

    def parse_object_inv(self, stream: SphinxObjectFileReader, url: str) -> dict[str, str]:
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result: dict[str, str] = {}

        # first line is version info
        inv_version = stream.readline().rstrip()

        if inv_version != '# Sphinx inventory version 2':
            raise RuntimeError('Invalid objects.inv file version.')

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"
        projname = stream.readline().rstrip()[11:]
        version = stream.readline().rstrip()[11:]

        # next line says if it's a zlib header
        line = stream.readline()
        if 'zlib' not in line:
            raise RuntimeError('Invalid objects.inv file, not z-lib compatible.')

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(r'(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)')
        for line in stream.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, prio, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(':')
            if directive == 'py:module' and name in result:
                # From the Sphinx Repository:
                # due to a bug in 1.1 and below,
                # two inventory entries are created
                # for Python modules, and the first
                # one is correct
                continue

            # Most documentation pages have a label
            if directive == 'std:doc':
                subdirective = 'label'

            if location.endswith('$'):
                location = location[:-1] + name

            key = name if dispname == '-' else dispname
            prefix = f'{subdirective}:' if domain == 'std' else ''

            if projname == 'discord.py':
                key = key.replace('discord.ext.commands.', '').replace('discord.', '')

            result[f'{prefix}{key}'] = os.path.join(url, location)

        return result

    async def build_rtfm_lookup_table(self):
        cache: dict[str, dict[str, str]] = {}
        for key, page in RTFM_PAGE_TYPES.items():
            cache[key] = {}
            async with self.bot.session.get(page + '/objects.inv') as resp:
                if resp.status != 200:
                    raise RuntimeError('Cannot build rtfm lookup table, try again later.')

                stream = SphinxObjectFileReader(await resp.read())
                cache[key] = self.parse_object_inv(stream, page)

        self._rtfm_cache = cache

    async def do_rtfm(self, ctx: Context, key: str, obj: Optional[str]):
        if obj is None:
            await ctx.send(RTFM_PAGE_TYPES[key])
            return

        if not hasattr(self, '_rtfm_cache'):
            await ctx.typing()
            await self.build_rtfm_lookup_table()

        obj = re.sub(r'^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)', r'\1', obj)

        if key.startswith('latest'):
            # point the abc.Messageable types properly:
            q = obj.lower()
            for name in dir(discord.abc.Messageable):
                if name[0] == '_':
                    continue
                if q == name:
                    obj = f'abc.Messageable.{name}'
                    break

        cache = list(self._rtfm_cache[key].items())
        matches = fuzzy.finder(obj, cache, key=lambda t: t[0])[:8]

        e = discord.Embed(colour=discord.Colour.blurple())
        if len(matches) == 0:
            return await ctx.send('Could not find anything. Sorry.')

        e.description = '\n'.join(f'[`{key}`]({url})' for key, url in matches)
        await ctx.send(embed=e, reference=ctx.message.reference)

        if ctx.guild and ctx.guild.id in DISCORD_API_ID:
            query = 'INSERT INTO rtfm (user_id) VALUES ($1) ON CONFLICT (user_id) DO UPDATE SET count = rtfm.count + 1;'
            await self.db.execute(query, ctx.author.id)

    def transform_rtfm_language_key(self, ctx: Union[discord.Interaction, Context], prefix: str):
        if ctx.guild is not None:
            #                             日本語 category
            if ctx.channel.category_id == DISCORD_PY_JP_CATEGORY:  # type: ignore  # category_id is safe to access
                return prefix + '-jp'
            #                    d.py unofficial JP   Discord Bot Portal JP
            elif ctx.guild.id in (463986890190749698, 494911447420108820):
                return prefix + '-jp'
        return prefix

    async def rtfm_slash_autocomplete(
            self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:

        # Degenerate case: not having built caching yet
        if not hasattr(self, '_rtfm_cache'):
            await interaction.response.autocomplete([])
            await self.build_rtfm_lookup_table()
            return []

        if not current:
            return []

        if len(current) < 3:
            return [app_commands.Choice(name=current, value=current)]

        assert interaction.command is not None
        key = interaction.command.name
        if key in ('stable', 'python'):
            key = self.transform_rtfm_language_key(interaction, key)
        elif key == 'jp':
            key = 'latest-jp'

        matches = fuzzy.finder(current, self._rtfm_cache[key])[:10]
        return [app_commands.Choice(name=m, value=m) for m in matches]

    @commands.hybrid_group(aliases=['rtfd'], fallback='stable')
    @app_commands.describe(entity='The object to search for')
    @app_commands.autocomplete(entity=rtfm_slash_autocomplete)
    async def rtfm(self, ctx: Context, *, entity: Optional[str] = None):
        """Gives you a documentation link for a discord.py entity.

        Events, objects, and functions are all supported through
        a cruddy fuzzy algorithm.
        """
        key = self.transform_rtfm_language_key(ctx, 'stable')
        await self.do_rtfm(ctx, key, entity)

    @rtfm.command(name='jp')
    @app_commands.describe(entity='The object to search for')
    @app_commands.autocomplete(entity=rtfm_slash_autocomplete)
    async def rtfm_jp(self, ctx: Context, *, entity: Optional[str] = None):
        """Gives you a documentation link for a discord.py entity (Japanese)."""
        await self.do_rtfm(ctx, 'latest-jp', entity)

    @rtfm.command(name='python', aliases=['py'])
    @app_commands.describe(entity='The object to search for')
    @app_commands.autocomplete(entity=rtfm_slash_autocomplete)
    async def rtfm_python(self, ctx: Context, *, entity: Optional[str] = None):
        """Gives you a documentation link for a Python entity."""
        key = self.transform_rtfm_language_key(ctx, 'python')
        await self.do_rtfm(ctx, key, entity)

    @rtfm.command(name='python-jp', aliases=['py-jp', 'py-ja'])
    @app_commands.describe(entity='The object to search for')
    @app_commands.autocomplete(entity=rtfm_slash_autocomplete)
    async def rtfm_python_jp(self, ctx: Context, *, entity: Optional[str] = None):
        """Gives you a documentation link for a Python entity (Japanese)."""
        await self.do_rtfm(ctx, 'python-jp', entity)

    @rtfm.command(name='latest', aliases=['2.0', 'master'])
    @app_commands.describe(entity='The object to search for')
    @app_commands.autocomplete(entity=rtfm_slash_autocomplete)
    async def rtfm_master(self, ctx: Context, *, entity: Optional[str] = None):
        """Gives you a documentation link for a discord.py entity (master branch)"""
        await self.do_rtfm(ctx, 'latest', entity)

    @rtfm.command(name='refresh', with_app_command=False)
    @commands.is_owner()
    async def rtfm_refresh(self, ctx: Context):
        """Refreshes the RTFM and FAQ cache"""

        async with ctx.typing():
            await self.build_rtfm_lookup_table()
            await self.refresh_faq_cache()
            await self.refresh_examples()

        await ctx.send('\N{THUMBS UP SIGN}')

    async def _member_stats(self, ctx: Context, member: discord.Member, total_uses: int):
        e = discord.Embed(title='RTFM Stats')
        e.set_author(name=str(member), icon_url=member.display_avatar.url)

        query = 'SELECT count FROM rtfm WHERE user_id=$1;'
        record = await self.db.fetchrow(query, member.id)

        if record is None:
            count = 0
        else:
            count = record['count']

        e.add_field(name='Uses', value=count)
        e.add_field(name='Percentage', value=f'{count / total_uses:.2%} out of {total_uses}')
        e.colour = discord.Colour.blurple()
        await ctx.send(embed=e)

    @rtfm.command()
    @app_commands.describe(member='The member to look up stats for')
    async def stats(self, ctx: Context, *, member: discord.Member = None):
        """Shows statistics on RTFM usage on a member or the server."""
        query = 'SELECT SUM(count) AS total_uses FROM rtfm;'
        record: Record = await self.db.fetchrow(query)
        total_uses: int = record['total_uses']

        if member is not None:
            return await self._member_stats(ctx, member, total_uses)

        query = 'SELECT user_id, count FROM rtfm ORDER BY count DESC LIMIT 10;'
        records: list[Record] = await self.db.fetch(query)

        output = []
        output.append(f'**Total uses**: {total_uses}')

        # first we get the most used users
        if records:
            output.append(f'**Top {len(records)} users**:')

            for rank, (user_id, count) in enumerate(records, 1):
                user = self.bot.get_user(user_id) or (await self.bot.fetch_user(user_id))
                if rank != 10:
                    output.append(f'{rank}\u20e3 {user}: {count}')
                else:
                    output.append(f'\N{KEYCAP TEN} {user}: {count}')

        await ctx.send('\n'.join(output))

    @commands.group(name='feeds', invoke_without_command=True)
    @commands.guild_only()
    async def _feeds(self, ctx: GuildContext):
        """Shows the list of feeds that the channel has.

        A feed is something that users can opt-in to
        to receive news about a certain feed by running
        the `sub` command (and opt-out by doing the `unsub` command).
        You can publish to a feed by using the `publish` command.
        """

        feeds = await self.get_feeds(ctx.channel.id)

        if len(feeds) == 0:
            await ctx.send('This channel has no feeds.')
            return

        names = '\n'.join(f'- {r}' for r in feeds)
        await ctx.send(f'Found {len(feeds)} feeds.\n{names}')

    async def refresh_faq_cache(self):
        self.faq_entries = {}
        base_url = 'https://discordpy.readthedocs.io/en/latest/faq.html'
        async with self.bot.session.get(base_url) as resp:
            text = await resp.text(encoding='utf-8')

            root = etree.fromstring(text, etree.HTMLParser())
            nodes = root.findall(".//div[@id='questions']/ul[@class='simple']/li/ul//a")
            for node in nodes:
                self.faq_entries[''.join(node.itertext()).strip()] = base_url + node.get('href').strip()

    async def refresh_examples(self) -> None:
        dpy: Optional[DPYExclusive] = self.bot.get_cog('discord.py')  # type: ignore
        if dpy is None:
            return

        try:
            tree = await dpy.github_request('GET', 'repos/Rapptz/discord.py/git/trees/master',
                                            params={'recursive': '1'})
        except:
            return

        self.repo_examples = []
        for file in tree['tree']:
            if file['type'] != 'blob':
                continue

            path: str = file['path']
            if not path.startswith('examples/'):
                continue

            if not path.endswith('.py'):
                continue

            url = f'https://github.com/Rapptz/discord.py/blob/master/{path}'
            # 9 is the length of "examples/"
            self.repo_examples.append(RepositoryExample(path[9:], url))

    @commands.hybrid_command()
    @app_commands.describe(query='The FAQ entry to look up')
    async def faq(self, ctx: Context, *, query: Optional[str] = None):
        """Shows an FAQ entry from the discord.py documentation"""
        if not hasattr(self, 'faq_entries'):
            await self.refresh_faq_cache()

        if query is None:
            return await ctx.send('https://discordpy.readthedocs.io/en/latest/faq.html')

        matches = fuzzy.extract_matches(query, self.faq_entries, scorer=fuzzy.partial_ratio, score_cutoff=40)
        if len(matches) == 0:
            return await ctx.send('Nothing found...')

        paginator = commands.Paginator(suffix='', prefix='')
        for key, _, value in matches:
            paginator.add_line(f'**{key}**\n{value}')
        page = paginator.pages[0]
        await ctx.send(page, reference=ctx.message.reference)

    @faq.autocomplete('query')
    async def faq_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if not hasattr(self, 'faq_entries'):
            await interaction.response.autocomplete([])
            await self.refresh_faq_cache()
            return []

        if not current:
            choices = [app_commands.Choice(name=key, value=key) for key in self.faq_entries][:10]
            return choices

        matches = fuzzy.extract_matches(current, self.faq_entries, scorer=fuzzy.partial_ratio, score_cutoff=40)[:10]
        return [app_commands.Choice(name=key, value=key) for key, _, _, in matches][:10]

    @commands.hybrid_command(name='examples')
    @app_commands.describe(example='The path of the example to look for')
    async def examples(self, ctx: GuildContext, *, example: Optional[str] = None):
        """Searches and returns examples from the discord.py repository."""
        if not hasattr(self, 'repo_examples'):
            await self.refresh_examples()

        if example is None:
            return await ctx.send(f'<https://github.com/Rapptz/discord.py/tree/master/examples>')

        matches = fuzzy.finder(example, self.repo_examples, key=lambda e: e.path)[:5]
        if not matches:
            return await ctx.send('No examples found.')

        to_send = '\n'.join(f'[{e.path}](<{e.url}>)' for e in matches)
        await ctx.send(to_send, reference=ctx.message.reference)

    @examples.autocomplete('example')
    async def examples_autocomplete(self, interaction: discord.Interaction, current: str):
        if not hasattr(self, 'repo_examples'):
            await interaction.response.autocomplete([])
            await self.refresh_examples()
            return []

        matches = fuzzy.finder(current, self.repo_examples, key=lambda e: e.path)[:25]
        return [e.to_choice() for e in matches]


async def setup(bot):
    await bot.add_cog(API(bot))

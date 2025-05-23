import asyncio
import datetime
import io
import traceback
from typing import Literal, Optional, Annotated, TypedDict, TYPE_CHECKING

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import utilFunc
from utilFunc import formats, config
from utilFunc.context import GuildContext, Context
from utilFunc.paginator import SimplePages

load_dotenv()

"""
This is the tags cog.
Most information is provided in the associated
commands.

- Char.
"""

#Database connection
# db = sqlite3.connect('tags.db', timeout = 30000)
# cursor = db.cursor()
# cursor.execute(
#     'CREATE TABLE IF NOT EXISTS tag_list (tag_name TEXT NOT NULL,tag_content TEXT NOT NULL, guild_id INTEGER NOT NULL)')
# print("Loaded tags data set")
# db.commit()


if TYPE_CHECKING:
    from utilFunc.context import GuildContext, Context


class TagEntry(TypedDict):
    id: int
    name: str
    content: str


class TagAllFlags(commands.FlagConverter):
    text: bool = commands.flag(default=False, description='Whether to dump the tags as a text file.')


class TagPageEntry:
    __slots__ = ('id', 'name')

    def __init__(self, entry: TagEntry):
        self.id: int = entry['id']
        self.name: str = entry['name']

    def __str__(self) -> str:
        return f'{self.name} (ID: {self.id})'


class TagPages(SimplePages):
    def __init__(self, entries: list[TagEntry], *, ctx: Context, per_page: int = 12):
        converted = [TagPageEntry(entry) for entry in entries]
        super().__init__(converted, per_page=per_page, ctx=ctx)


class TagName(commands.clean_content):
    def __init__(self, *, lower: bool = False):
        self.lower: bool = lower
        super().__init__()

    async def convert(self, ctx: Context, argument: str) -> str:
        converted = await super().convert(ctx, argument)
        lower = converted.lower().strip()

        if not lower:
            raise commands.BadArgument('Missing tag name.')

        if len(lower) > 100:
            raise commands.BadArgument('Tag name is a maximum of 100 characters.')

        first_word, _, _ = lower.partition(' ')

        # get tag command.
        root: commands.GroupMixin = ctx.bot.get_command('tag')  # type: ignore
        if first_word in root.all_commands:
            raise commands.BadArgument('This tag name starts with a reserved word.')

        return converted.strip() if not self.lower else lower


# Modals


class TagEditModal(discord.ui.Modal, title='Edit Tag'):
    content = discord.ui.TextInput(
        label='Tag Content', required=True, style=discord.TextStyle.long, min_length=1, max_length=2000
    )

    def __init__(self, text: str) -> None:
        super().__init__()
        self.content.default = text

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.interaction = interaction
        self.text = str(self.content)
        self.stop()


class TagMakeModal(discord.ui.Modal, title='Create New Tag'):
    name = discord.ui.TextInput(label='Name', required=True, max_length=100, min_length=1)
    content = discord.ui.TextInput(
        label='Content', required=True, style=discord.TextStyle.long, min_length=1, max_length=2000
    )

    def __init__(self, cog, ctx: GuildContext, db_pool: asyncpg.Pool):
        super().__init__()
        self.db_pool = db_pool  # Assign the database pool in the constructor
        self.cog = cog
        self.ctx: GuildContext = ctx

    async def on_submit(self, interaction: discord.Interaction):
        db_pool = await asyncpg.create_pool(
            database=utilFunc.config.DB_NAME,
            user=utilFunc.config.DB_USER,
            password=utilFunc.config.DB_PASSWORD,
            host=utilFunc.config.DB_HOST,
            port=utilFunc.config.DB_PORT
        )
        tag_name = self.name.value.lower()
        query = "SELECT 1 FROM tags WHERE LOWER(name)=$1;"

        # Use the provided database pool to acquire a connection
        async with self.db_pool.acquire() as connection:
            async with connection.transaction():
                # Check if the tag already exists
                tag_exists = await connection.fetchval(query, tag_name)

                if tag_exists is not None:
                    # Inform the user that the tag already exists
                    await interaction.response.send_message(
                        f"Sorry, the tag '{self.name.value}' already exists!",
                        ephemeral=True
                    )
                    return  # Exit early if the tag already exists
                else:
                    await self.cog.create_tag(self.ctx, self.name.value, self.content.value)

                # Respond to the user that the tag was created successfully
                await interaction.response.send_message(
                    f"Thanks! The tag '{self.name.value}' has been successfully created!",
                    ephemeral=True
                )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(
            f"An error occurred: {error}",
            ephemeral=True
        )
        # Log the exception traceback for debugging
        traceback.print_exception(type(error), error, error.__traceback__)


class Tags(commands.Cog):
    def __init__(self, bot: commands.Bot, db_pool) -> None:
        self.db = db_pool
        self.bot: commands.Bot = bot

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='\N{LABEL}\ufe0f')

    async def cog_command_error(self, ctx: Context, error: commands.CommandError):
        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            if ctx.command.qualified_name == 'tag':
                await ctx.send_help(ctx.command)
            else:
                await ctx.send(str(error))
        elif isinstance(error, commands.FlagError):
            await ctx.send(str(error))

    async def setup_hook(self) -> None:
        self.db = await asyncpg.connect(database=utilFunc.config.DB_NAME,
                                        user=utilFunc.config.DB_USER,
                                        password=utilFunc.config.DB_PASSWORD,
                                        host=utilFunc.config.DB_HOST,
                                        port=utilFunc.config.DB_PORT
                                        )

    async def get_possible_tags(
            self,
            guild: discord.abc.Snowflake,
            *,
            connection: Optional[asyncpg.Connection | asyncpg.Pool] = None,
    ) -> list[TagEntry]:
        """Returns a list of Records of possible tags that the guild can execute.

        If this is a private message then only the generic tags are possible.
        Server specific tags will override the generic tags.
        """

        con = connection or self.db
        query = """SELECT name, content FROM tags WHERE location_id=$1;"""
        return await con.fetch(query, guild.id)

    async def get_random_tag(
            self,
            guild: discord.abc.Snowflake,
            *,
            connection: Optional[asyncpg.Connection | asyncpg.Pool] = None,
    ) -> Optional[TagEntry]:
        """Returns a random tag."""

        con = connection or self.db
        query = f"""SELECT name, content
                    FROM tags
                    WHERE location_id=$1
                    OFFSET FLOOR(RANDOM() * (
                        SELECT COUNT(*)
                        FROM tags
                        WHERE location_id=$1
                    ))
                    LIMIT 1;
                 """

        return await con.fetchrow(query, guild.id)  # type: ignore

    async def get_tag(
            self,
            guild_id: Optional[int],
            name: str,
            *,
            pool: Optional[asyncpg.Pool] = None,
    ) -> TagEntry:
        def disambiguate(rows, query):
            if rows is None or len(rows) == 0:
                raise RuntimeError('Tag not found.')

            names = '\n'.join(r['name'] for r in rows)
            raise RuntimeError(f'Tag not found. Did you mean...\n{names}')

        pool = pool or self.db

        query = """SELECT tags.name, tags.content
                   FROM tag_lookup
                   INNER JOIN tags ON tags.id = tag_lookup.tag_id
                   WHERE tag_lookup.location_id=$1 AND LOWER(tag_lookup.name)=$2;
                """

        row = await pool.fetchrow(query, guild_id, name)
        if row is None:
            query = """SELECT     tag_lookup.name
                       FROM       tag_lookup
                       WHERE      tag_lookup.location_id=$1 AND tag_lookup.name % $2
                       ORDER BY   similarity(tag_lookup.name, $2) DESC
                       LIMIT 3;
                    """

            return disambiguate(await pool.fetch(query, guild_id, name), name)
        else:
            return row

    async def create_tag(self, ctx: GuildContext, name: str, content: str) -> None:
        # due to our denormalized design, I need to insert the tag in two different
        # tables, make sure it's in a transaction so if one of the inserts fail I
        # can act upon it
        query = """WITH tag_insert AS (
                        INSERT INTO tags (name, content, owner_id, location_id)
                        VALUES ($1, $2, $3, $4)
                        RETURNING id
                    )
                    INSERT INTO tag_lookup (name, owner_id, location_id, tag_id)
                    VALUES ($1, $3, $4, (SELECT id FROM tag_insert));
                """

        # since I'm checking for the exception type and acting on it, I need
        # to use the manual transaction blocks

        async with self.db.acquire() as connection:
            tr = connection.transaction()
            await tr.start()

            try:
                await connection.execute(query, name, content, ctx.author.id, ctx.guild.id)
            except asyncpg.UniqueViolationError:
                await tr.rollback()
                await ctx.send('This tag already exists.')
            except:
                await tr.rollback()
                await ctx.send('Could not create tag.')
            else:
                await tr.commit()
                # await ctx.send(f'Tag {name} successfully created.')

    # These are hopefully fast enough. Through a query planner these take around ~20ms each.

    async def non_aliased_tag_autocomplete(
            self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        query = """SELECT name FROM tags WHERE location_id=$1 AND LOWER(name) % $2 LIMIT 12;"""
        results: list[tuple[str]] = await self.db.fetch(query, interaction.guild_id, current.lower())
        return [app_commands.Choice(name=a, value=a) for a, in results]

    async def aliased_tag_autocomplete(
            self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        query = """SELECT name FROM tag_lookup WHERE location_id=$1 AND LOWER(name) % $2 LIMIT 12;"""
        results: list[tuple[str]] = await self.db.fetch(query, interaction.guild_id, current.lower())
        return [app_commands.Choice(name=a, value=a) for a, in results]

    async def owned_non_aliased_tag_autocomplete(
            self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        query = """SELECT name
                   FROM tags
                   WHERE location_id=$1 AND owner_id=$2 AND name % $3
                   ORDER BY similarity(name, $3) DESC
                   LIMIT 12;
                """
        results: list[tuple[str]] = await self.db.fetch(
            query, interaction.guild_id, interaction.user.id, current.lower()
        )
        return [app_commands.Choice(name=a, value=a) for a, in results]

    async def owned_aliased_tag_autocomplete(
            self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        query = """SELECT name
                   FROM tag_lookup
                   WHERE location_id=$1 AND owner_id=$2 AND name % $3
                   ORDER BY similarity(name, $3) DESC
                   LIMIT 12;
                """
        results: list[tuple[str]] = await self.db.fetch(
            query, interaction.guild_id, interaction.user.id, current.lower()
        )
        return [app_commands.Choice(name=a, value=a) for a, in results]

    @commands.hybrid_group(fallback='get')
    @commands.guild_only()
    @app_commands.guild_only()
    @app_commands.describe(name='The tag to retrieve')
    @app_commands.autocomplete(name=aliased_tag_autocomplete)
    async def tag(self, ctx: GuildContext, *, name: Annotated[str, TagName(lower=True)]):
        """Allows you to tag text for later retrieval.

        If a subcommand is not called, then this will search the tag database
        for the tag requested.
        """

        try:
            tag = await self.get_tag(ctx.guild.id, name, pool=self.db)
        except RuntimeError as e:
            return await ctx.send(str(e))

        await ctx.send(tag['content'], reference=ctx.message.reference)

        # update the usage
        query = "UPDATE tags SET uses = uses + 1 WHERE name = $1 AND location_id=$2;"
        await self.db.execute(query, tag['name'], ctx.guild.id)

    @tag.command(aliases=['add'])
    @commands.guild_only()
    @app_commands.describe(name='The tag name', content='The tag content')
    async def create(
            self, ctx: GuildContext, name: Annotated[str, TagName], *, content: Annotated[str, commands.clean_content]
    ):
        """Creates a new tag owned by you.

        This tag is server-specific and cannot be used in other servers.

        Note that server moderators can delete your tag.
        """

        # if self.is_tag_being_made(ctx.guild.id, name):
        # return await ctx.send('This tag is currently being made by someone.')

        if len(content) > 2000:
            return await ctx.send('Tag content is a maximum of 2000 characters.')

        await self.create_tag(ctx, name, content)

    @tag.command()
    @commands.guild_only()
    @app_commands.rename(new_name='aliased-name', old_name='original-tag')
    @app_commands.describe(new_name='The name of the alias', old_name='The original tag to alias')
    @app_commands.autocomplete(old_name=non_aliased_tag_autocomplete)
    async def alias(self, ctx: GuildContext, new_name: Annotated[str, TagName], *, old_name: Annotated[str, TagName]):
        """Creates an alias for a pre-existing tag.

        You own the tag alias. However, when the original
        tag is deleted the alias is deleted as well.

        Tag aliases cannot be edited. You must delete
        the alias and remake it to point it to another
        location.
        """

        query = """INSERT INTO tag_lookup (name, owner_id, location_id, tag_id)
                   SELECT $1, $4, tag_lookup.location_id, tag_lookup.tag_id
                   FROM tag_lookup
                   WHERE tag_lookup.location_id=$3 AND LOWER(tag_lookup.name)=$2;
                """

        try:
            status = await self.db.execute(query, new_name, old_name.lower(), ctx.guild.id, ctx.author.id)
        except asyncpg.UniqueViolationError:
            await ctx.send('A tag with this name already exists.')
        else:
            # The status returns INSERT N M, where M is the number of rows inserted.
            if status[-1] == '0':
                await ctx.send(f'A tag with the name of "{old_name}" does not exist.')
            else:
                await ctx.send(f'Tag alias "{new_name}" that points to "{old_name}" successfully created.')

    @tag.command(ignore_extra=False)
    @commands.guild_only()
    async def make(self, ctx: GuildContext):
        """Interactive makes a tag for you.

        This walks you through the process of creating a tag with
        its name and its content. This works similar to the tag
        create command.
        """

        if ctx.interaction is not None:
            modal = TagMakeModal(self, ctx, db_pool=self.db)
            await ctx.interaction.response.send_modal(modal)
            return

        await ctx.send("Hello. What would you like the tag's name to be?")

        converter = TagName()
        original = ctx.message

        def check(msg):
            return msg.author == ctx.author and ctx.channel == msg.channel

        try:
            name = await self.bot.wait_for('message', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            return await ctx.send('You took long. Goodbye.')

        try:
            ctx.message = name
            name = await converter.convert(ctx, name.content)
        except commands.BadArgument as e:
            return await ctx.send(f'{e}. Redo the command "{ctx.prefix}tag make" to retry.')
        finally:
            ctx.message = original

        # if self.is_tag_being_made(ctx.guild.id, name):
        # return await ctx.send(
        #     'Sorry. This tag is currently being made by someone. ' f'Redo the command "{ctx.prefix}tag make" to retry.'
        # )

        # it's technically kind of expensive to do two queries like this
        # i.e. one to check if it exists and then another that does the insert
        # while also checking if it exists due to the constraints,
        # however for UX reasons I might as well do it.

        query = """SELECT 1 FROM tags WHERE location_id=$1 AND LOWER(name)=$2;"""
        row = await self.db.fetchrow(query, ctx.guild.id, name.lower())
        if row is not None:
            return await ctx.send(
                'Sorry. A tag with that name already exists. ' f'Redo the command "{ctx.prefix}tag make" to retry.'
            )

        self.add_in_progress_tag(ctx.guild.id, name)
        await ctx.send(
            f'Neat. So the name is {name}. What about the tag\'s content? '
            f'**You can type {ctx.prefix}abort to abort the tag make process.**'
        )

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=300.0)
        except asyncio.TimeoutError:
            self.remove_in_progress_tag(ctx.guild.id, name)
            return await ctx.send('You took too long. Goodbye.')

        if msg.content == f'{ctx.prefix}abort':
            self.remove_in_progress_tag(ctx.guild.id, name)
            return await ctx.send('Aborting.')
        elif msg.content:
            clean_content = await commands.clean_content().convert(ctx, msg.content)
        else:
            # fast path I guess?
            clean_content = msg.content

        if msg.attachments:
            clean_content = f'{clean_content}\n{msg.attachments[0].url}'

        if len(clean_content) > 2000:
            self.remove_in_progress_tag(ctx.guild.id, name)
            return await ctx.send('Tag content is a maximum of 2000 characters.')

        try:
            await self.create_tag(ctx, name, clean_content)
        finally:
            self.remove_in_progress_tag(ctx.guild.id, name)

    @make.error
    async def tag_make_error(self, ctx: GuildContext, error: commands.CommandError):
        if isinstance(error, commands.TooManyArguments):
            await ctx.send(f'Please call just {ctx.prefix}tag make')

    @tag.command()
    @commands.guild_only()
    @app_commands.describe(
        name='The tag to edit',
        content='The new content of the tag, if not given then a modal is opened',
    )
    @app_commands.autocomplete(name=owned_non_aliased_tag_autocomplete)
    async def edit(
            self,
            ctx: GuildContext,
            name: Annotated[str, TagName(lower=True)],
            *,
            content: Annotated[Optional[str], commands.clean_content] = None,
    ):
        """Modifies an existing tag that you own.

        This command completely replaces the original text. If
        you want to get the old text back, consider using the
        tag raw command.
        """

        if content is None:
            if ctx.interaction is None:
                raise commands.BadArgument('Missing content to edit tag with')
            else:
                query = "SELECT content FROM tags WHERE LOWER(name)=$1 AND location_id=$2 AND owner_id=$3"
                row: Optional[tuple[str]] = await self.db.fetchrow(query, name, ctx.guild.id, ctx.author.id)
                if row is None:
                    await ctx.send(
                        'Could not find a tag with that name, are you sure it exists or you own it?', ephemeral=True
                    )
                    return
                modal = TagEditModal(row[0])
                await ctx.interaction.response.send_modal(modal)
                await modal.wait()
                ctx.interaction = modal.interaction
                content = modal.text

        if len(content) > 2000:
            return await ctx.send('Tag content can only be up to 2000 characters')

        query = "UPDATE tags SET content=$1 WHERE LOWER(name)=$2 AND location_id=$3 AND owner_id=$4;"
        status = await self.db.execute(query, content, name, ctx.guild.id, ctx.author.id)

        # the status returns UPDATE <count>
        # if the <count> is 0, then nothing got updated
        # probably due to the WHERE clause failing

        if status[-1] == '0':
            await ctx.send('Could not edit that tag. Are you sure it exists and you own it?')
        else:
            await ctx.send('Successfully edited tag.')

    @tag.command(aliases=['delete'])
    @commands.guild_only()
    @app_commands.describe(name='The tag to remove')
    @app_commands.autocomplete(name=owned_aliased_tag_autocomplete)
    async def remove(self, ctx: GuildContext, *, name: Annotated[str, TagName(lower=True)]):
        """Removes a tag that you own.

        The tag owner can always delete their own tags. If someone requests
        deletion and has Manage Server permissions then they can also
        delete it.

        Deleting a tag will delete all of its aliases as well.
        """

        bypass_owner_check = ctx.author.id == self.bot.owner_id or ctx.author.guild_permissions.manage_messages
        clause = 'LOWER(name)=$1 AND location_id=$2'

        if bypass_owner_check:
            args = [name, ctx.guild.id]
        else:
            args = [name, ctx.guild.id, ctx.author.id]
            clause = f'{clause} AND owner_id=$3'

        query = f'DELETE FROM tag_lookup WHERE {clause} RETURNING tag_id;'
        deleted = await self.db.fetchrow(query, *args)

        if deleted is None:
            await ctx.send('Could not delete tag. Either it does not exist or you do not have permissions to do so.')
            return

        args.append(deleted[0])
        query = f'DELETE FROM tags WHERE id=${len(args)} AND {clause};'
        status = await self.db.execute(query, *args)

        # the status returns DELETE <count>, similar to UPDATE above
        if status[-1] == '0':
            # this is based on the previous delete above
            await ctx.send('Tag alias successfully deleted.')
        else:
            await ctx.send('Tag and corresponding aliases successfully deleted.')

    @tag.command(aliases=['delete_id'])
    @commands.guild_only()
    @app_commands.describe(tag_id='The internal tag ID to delete')
    @app_commands.rename(tag_id='id')
    async def remove_id(self, ctx: GuildContext, tag_id: int):
        """Removes a tag by ID.

        The tag owner can always delete their own tags. If someone requests
        deletion and has Manage Server permissions then they can also
        delete it.

        Deleting a tag will delete all of its aliases as well.
        """

        bypass_owner_check = ctx.author.id == self.bot.owner_id or ctx.author.guild_permissions.manage_messages
        clause = 'id=$1 AND location_id=$2'

        if bypass_owner_check:
            args = [tag_id, ctx.guild.id]
        else:
            args = [tag_id, ctx.guild.id, ctx.author.id]
            clause = f'{clause} AND owner_id=$3'

        query = f'DELETE FROM tag_lookup WHERE {clause} RETURNING tag_id;'
        deleted = await self.db.fetchrow(query, *args)

        if deleted is None:
            await ctx.send('Could not delete tag. Either it does not exist or you do not have permissions to do so.')
            return

        if bypass_owner_check:
            clause = 'id=$1 AND location_id=$2'
            args = [deleted[0], ctx.guild.id]
        else:
            clause = 'id=$1 AND location_id=$2 AND owner_id=$3'
            args = [deleted[0], ctx.guild.id, ctx.author.id]

        query = f'DELETE FROM tags WHERE {clause};'
        status = await self.db.execute(query, *args)

        # the status returns DELETE <count>, similar to UPDATE above
        if status[-1] == '0':
            # this is based on the previous delete above
            await ctx.send('Tag alias successfully deleted.')
        else:
            await ctx.send('Tag and corresponding aliases successfully deleted.')

    async def _send_alias_info(self, ctx: GuildContext, record: asyncpg.Record):
        embed = discord.Embed(colour=discord.Colour.blurple())

        owner_id = record['lookup_owner_id']
        embed.title = record['lookup_name']
        embed.timestamp = record['lookup_created_at'].replace(tzinfo=datetime.timezone.utc)
        embed.set_footer(text='Alias created at')

        user = self.bot.get_user(owner_id) or (await self.bot.fetch_user(owner_id))
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)

        embed.add_field(name='Owner', value=f'<@{owner_id}>')
        embed.add_field(name='Original', value=record['name'])
        await ctx.send(embed=embed)

    async def _send_tag_info(self, ctx: GuildContext, record: asyncpg.Record):
        embed = discord.Embed(colour=discord.Colour.blurple())

        owner_id = record['owner_id']
        embed.title = record['name']
        embed.timestamp = record['created_at'].replace(tzinfo=datetime.timezone.utc)
        embed.set_footer(text='Tag created at')

        user = self.bot.get_user(owner_id) or (await self.bot.fetch_user(owner_id))
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)

        embed.add_field(name='Owner', value=f'<@{owner_id}>')
        embed.add_field(name='Uses', value=record['uses'])

        query = """SELECT (
                       SELECT COUNT(*)
                       FROM tags second
                       WHERE (second.uses, second.id) >= (first.uses, first.id)
                         AND second.location_id = first.location_id
                   ) AS rank
                   FROM tags first
                   WHERE first.id=$1
                """

        rank = await self.db.fetchrow(query, record['id'])

        if rank is not None:
            embed.add_field(name='Rank', value=rank['rank'])

        await ctx.send(embed=embed)

    @tag.command(aliases=['owner'])
    @commands.guild_only()
    @app_commands.describe(name='The tag to retrieve information for')
    @app_commands.autocomplete(name=aliased_tag_autocomplete)
    async def info(self, ctx: GuildContext, *, name: Annotated[str, TagName(lower=True)]):
        """Retrieves info about a tag.

        The info includes things like the owner and how many times it was used.
        """

        query = """SELECT
                       tag_lookup.name <> tags.name AS "Alias",
                       tag_lookup.name AS lookup_name,
                       tag_lookup.created_at AS lookup_created_at,
                       tag_lookup.owner_id AS lookup_owner_id,
                       tags.*
                   FROM tag_lookup
                   INNER JOIN tags ON tag_lookup.tag_id = tags.id
                   WHERE LOWER(tag_lookup.name)=$1 AND tag_lookup.location_id=$2
                """

        record = await self.db.fetchrow(query, name, ctx.guild.id)
        if record is None:
            return await ctx.send('Tag not found.')

        if record['Alias']:
            await self._send_alias_info(ctx, record)
        else:
            await self._send_tag_info(ctx, record)

    @tag.command()
    @commands.guild_only()
    @app_commands.describe(name='The tag to retrieve raw content for')
    @app_commands.autocomplete(name=non_aliased_tag_autocomplete)
    async def raw(self, ctx: GuildContext, *, name: Annotated[str, TagName(lower=True)]):
        """Gets the raw content of the tag.

        This is with markdown escaped. Useful for editing.
        """

        try:
            tag = await self.get_tag(ctx.guild.id, name, pool=self.db)
        except RuntimeError as e:
            return await ctx.send(str(e))

        first_step = discord.utils.escape_markdown(tag['content'])
        await ctx.safe_send(first_step.replace('<', '\\<'), escape_mentions=False)

    @tag.command(name='list')
    @commands.guild_only()
    @app_commands.describe(member='The member to list tags of, if not given then it shows yours')
    async def _list(self, ctx: GuildContext, *, member: discord.User = commands.Author):
        """Lists all the tags that belong to you or someone else."""

        query = """SELECT name, id
                   FROM tag_lookup
                   WHERE location_id=$1 AND owner_id=$2
                   ORDER BY name
                """

        rows = await self.db.fetch(query, ctx.guild.id, member.id)

        if rows:
            p = TagPages(entries=rows, ctx=ctx)
            p.embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
            await p.start()
        else:
            await ctx.send(f'{member} has no tags.')

    @commands.hybrid_command()
    @commands.guild_only()
    @app_commands.guild_only()
    @app_commands.describe(member='The member to list tags of, if not given then it shows yours')
    async def tags(self, ctx: GuildContext, *, member: discord.User = commands.Author):
        """An alias for tag list command."""
        await ctx.invoke(self._list, member=member)

    async def _tag_all_text_mode(self, ctx: GuildContext):
        query = """SELECT tag_lookup.id,
                          tag_lookup.name,
                          tag_lookup.owner_id,
                          tags.uses,
                          $2 OR $3 = tag_lookup.owner_id AS "can_delete",
                          LOWER(tag_lookup.name) <> LOWER(tags.name) AS "is_alias"
                   FROM tag_lookup
                   INNER JOIN tags ON tags.id = tag_lookup.tag_id
                   WHERE tag_lookup.location_id=$1
                   ORDER BY tags.uses DESC;
                """

        bypass_owner_check = ctx.author.id == self.bot.owner_id or ctx.author.guild_permissions.manage_messages
        rows = await self.db.fetch(query, ctx.guild.id, bypass_owner_check, ctx.author.id)
        if not rows:
            return await ctx.send('This server has no server-specific tags.')

        table = formats.TabularData()
        table.set_columns(list(rows[0].keys()))
        table.add_rows(list(r.values()) for r in rows)
        fp = io.BytesIO(table.render().encode('utf-8'))
        await ctx.send(file=discord.File(fp, 'tags.txt'))

    @tag.command(name='all', usage='[text: yes|no]')
    @commands.guild_only()
    async def _all(self, ctx: GuildContext, *, flags: TagAllFlags):
        """Lists all server-specific tags for this server.

        You can pass specific flags to this command to control the output:

        `text:`: Dumps into a text file. Example: `text: yes`
        """

        if flags.text:
            return await self._tag_all_text_mode(ctx)

        query = """SELECT name, id
                   FROM tag_lookup
                   WHERE location_id=$1
                   ORDER BY name
                """

        rows = await self.db.fetch(query, ctx.guild.id)

        if rows:
            # PSQL orders this oddly for some reason
            p = TagPages(entries=rows, per_page=20, ctx=ctx)
            await p.start()
        else:
            await ctx.send('This server has no server-specific tags.')

    @tag.command()
    @commands.guild_only()
    @app_commands.describe(query='The tag name to search for')
    async def search(self, ctx: GuildContext, *, query: Annotated[str, commands.clean_content]):
        """Searches for a tag.

        The query must be at least 3 characters.
        """

        if len(query) < 3:
            return await ctx.send('The query length must be at least three characters.')

        sql = """SELECT name, id
                 FROM tag_lookup
                 WHERE location_id=$1 AND name % $2
                 ORDER BY similarity(name, $2) DESC
                 LIMIT 100;
              """

        results = await self.db.fetch(sql, ctx.guild.id, query)

        if results:
            p = TagPages(entries=results, per_page=20, ctx=ctx)
            await p.start()
        else:
            await ctx.send('No tags found.')

    @tag.command()
    @commands.guild_only()
    @app_commands.describe(tag='The tag to claim')
    @app_commands.autocomplete(tag=aliased_tag_autocomplete)
    async def claim(self, ctx: GuildContext, *, tag: Annotated[str, TagName]):
        """Claims an unclaimed tag.

        An unclaimed tag is a tag that effectively
        has no owner because they have left the server.
        """

        alias = False
        # requires 2 queries for UX
        query = "SELECT id, owner_id FROM tags WHERE location_id=$1 AND LOWER(name)=$2;"
        row = await self.db.fetchrow(query, ctx.guild.id, tag.lower())
        if row is None:
            alias_query = "SELECT tag_id, owner_id FROM tag_lookup WHERE location_id = $1 and LOWER(name) = $2;"
            row = await self.db.fetchrow(alias_query, ctx.guild.id, tag.lower())
            if row is None:
                return await ctx.send(f'A tag with the name of "{tag}" does not exist.')
            alias = True

        member = await self.bot.get_or_fetch_member(ctx.guild, row[1])
        if member is not None:
            return await ctx.send('Tag owner is still in server.')

        async with self.db.acquire() as conn:
            async with conn.transaction():
                if not alias:
                    query = "UPDATE tags SET owner_id=$1 WHERE id=$2;"
                    await conn.execute(query, ctx.author.id, row[0])
                query = "UPDATE tag_lookup SET owner_id=$1 WHERE tag_id=$2;"
                await conn.execute(query, ctx.author.id, row[0])

            await ctx.send('Successfully transferred tag ownership to you.')

    @tag.command()
    @commands.guild_only()
    @app_commands.describe(member='The member to transfer the tag to')
    @app_commands.autocomplete(tag=aliased_tag_autocomplete)
    async def transfer(self, ctx: GuildContext, member: discord.Member, *, tag: Annotated[str, TagName]):
        """Transfers a tag to another member.

        You must own the tag before doing this.
        """

        if member.bot:
            return await ctx.send('You cannot transfer a tag to a bot.')

        query = "SELECT id FROM tags WHERE location_id=$1 AND LOWER(name)=$2 AND owner_id=$3;"

        row = await self.db.fetchrow(query, ctx.guild.id, tag.lower(), ctx.author.id)
        if row is None:
            return await ctx.send(f'A tag with the name of "{tag}" does not exist or is not owned by you.')

        async with self.db.acquire() as conn:
            async with conn.transaction():
                query = "UPDATE tags SET owner_id=$1 WHERE id=$2;"
                await conn.execute(query, member.id, row[0])
                query = "UPDATE tag_lookup SET owner_id=$1 WHERE tag_id=$2;"
                await conn.execute(query, member.id, row[0])

        await ctx.send(f'Successfully transferred tag ownership to {member}.')

    @tag.command(hidden=True, with_app_command=False)
    async def config(self, ctx: Context):
        """This is a reserved tag command. Check back later."""
        pass

    @tag.command()
    async def random(self, ctx: GuildContext):
        """Displays a random tag."""

        tag = await self.get_random_tag(ctx.guild)
        if tag is None:
            return await ctx.send('This server has no tags.')

        await ctx.send(f'Random tag found: {tag["name"]}\n{tag["content"]}')

    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, guilds: commands.Greedy[discord.Object],
                   spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        """
        just syncs global commands and shit like that
        """
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")


async def setup(bot: commands.Bot):
    db_pool = await asyncpg.create_pool(
        database=utilFunc.config.DB_NAME,
        user=utilFunc.config.DB_USER,
        password=utilFunc.config.DB_PASSWORD,
        host=utilFunc.config.DB_HOST,
        port=utilFunc.config.DB_PORT
    )
    await bot.add_cog(Tags(bot, db_pool))

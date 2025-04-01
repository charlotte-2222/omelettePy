from __future__ import annotations

import asyncio
import copy
import inspect
import io
import time
import traceback
from contextlib import redirect_stdout
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Union, Optional

import discord
import requests
from discord import app_commands
from discord.ext import commands

from utilFunc.config import GITHUB_TOKEN

# to expose to the eval command

if TYPE_CHECKING:
    from typing_extensions import Self
    from asyncpg import Record
    from utilFunc.context import Context


class PerformanceMocker:
    """A mock object that can also be used in await expressions."""

    def __init__(self):
        self.loop = asyncio.get_running_loop()

    def permissions_for(self, obj: Any) -> discord.Permissions:
        # Lie and say we don't have permissions to embed
        # This makes it so pagination sessions just abruptly end on __init__
        # Most checks based on permission have a bypass for the owner anyway
        # So this lie will not affect the actual command invocation.
        perms = discord.Permissions.all()
        perms.administrator = False
        perms.embed_links = False
        perms.add_reactions = False
        return perms

    def __getattr__(self, attr: str) -> Self:
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> Self:
        return self

    def __repr__(self) -> str:
        return '<PerformanceMocker>'

    def __await__(self):
        future: asyncio.Future[Self] = self.loop.create_future()
        future.set_result(self)
        return future.__await__()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: Any) -> Self:
        return self

    def __len__(self) -> int:
        return 0

    def __bool__(self) -> bool:
        return False


class CreateIssue(discord.ui.Modal, title='Create New Issue'):
    name = discord.ui.TextInput(label='Issue Name',
                                required=True,
                                max_length=100,
                                min_length=1)
    content = discord.ui.TextInput(
        label='Issue Content',
        required=True,
        style=discord.TextStyle.long,
        min_length=1,
        max_length=2000
    )

    def __init__(self):
        super().__init__()
        self.repo_owner = None
        self.repo_name = None

    def set_repo(self, repo_owner: str, repo_name: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='stafftools', id=314348604095594498)

    async def on_submit(self, interaction: discord.Interaction):
        # GitHub API request to create an issue
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        data = {
            "title": self.name.value,  # Use the `name` input field for the issue title
            "body": self.content.value  # Use the `content` input field for the issue body
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 201:  # Issue created successfully
            issue_url = response.json().get("html_url", "Unknown URL")
            await interaction.response.send_message(
                f"Issue created successfully! [View Issue]({issue_url})",
                ephemeral=True
            )
        elif response.status_code == 404:
            await interaction.response.send_message(
                "Failed to create issue: Repository not found.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Failed to create issue: {response.status_code} {response.text}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"You fucked up! {error}", ephemeral=True)
        traceback.print_exception(type(error), error, error.__traceback__)


class Git(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self._last_result: Optional[Any] = None
        self.sessions: set[int] = set()

    def cleanup_code(self, content: str) -> str:
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])
        return content.strip('` \n')

    def get_syntax_error(self, e: SyntaxError) -> str:
        if e.text is None:
            return f'```py\n{e.__class__.__name__}: {e}\n```'
        return f'```py\n{e.text}{"^":>{e.offset}}\n{e.__class__.__name__}: {e}```'


    # Function to fetch the latest commit from a GitHub repository
    @staticmethod
    def get_latest_commit(repo_owner, repo_name):
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            commit_data = response.json()[0]  # Get the latest commit
            commit_message = commit_data['commit']['message']
            author = commit_data['commit']['author']['name']
            commit_url = commit_data['html_url']
            return f"Latest Commit: \n**Message**: {commit_message}\n**Author**: {author}\n[View Commit]({commit_url})"
        elif response.status_code == 404:
            return "Repository not found. Please check the owner and repository name."
        else:
            return f"Failed to fetch commit data. HTTP Status: {response.status_code}"

    @staticmethod
    # Function to search repositories on GitHub
    def search_repositories(query, sort="stars", order="desc"):
        url = "https://api.github.com/search/repositories"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        params = {"q": query, "sort": sort, "order": order}

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            repo_data = response.json()
            if repo_data["total_count"] == 0:
                return "No repositories found matching the search query."

            # Show the top 3 results
            result = "**Top Repositories:**\n"
            for repo in repo_data["items"][:3]:
                repo_name = repo["full_name"]
                description = repo["description"] or "No description provided."
                stars = repo["stargazers_count"]
                repo_url = repo["html_url"]
                result += f"🔹 **[{repo_name}]({repo_url})**\n⭐ {stars} stars\n📖 {description}\n\n"

            return result
        else:
            return f"Failed to search repositories. HTTP Status: {response.status_code}"

    @staticmethod
    def get_open_issues(repo_owner, repo_name):
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            issues = response.json()
            if not issues:
                return "No open issues found in this repository."

            # Format the top 5 issues
            result = "**Open Issues:**\n"
            for issue in issues[:5]:  # Limit to the top 5 issues
                issue_title = issue["title"]
                issue_number = issue["number"]
                issue_url = issue["html_url"]
                result += f"🔹 **#{issue_number}: [{issue_title}]({issue_url})**\n"

            return result
        elif response.status_code == 404:
            return "Repository not found. Please check the owner and repository name."
        else:
            return f"Failed to fetch issues. HTTP Status: {response.status_code}"

    # Define the hybrid command to get the latest commit
    @commands.hybrid_command(name="latest_commit", description="Get the latest commit from a GitHub repository")
    @app_commands.describe(owner="Owner of the repository", repo="Name of the repository")
    async def latest_commit(self, ctx: commands.Context, owner: str, repo: str):
        await ctx.defer()  # Defers the response to allow time for processing

        commit_info = self.get_latest_commit(owner, repo)  # call static func
        await ctx.send(commit_info)

    @app_commands.command(name="create_issue", description="Create a new issue")
    @commands.is_owner()  # maybe this works?
    @app_commands.describe(owner="Owner of the repository", repo="Name of the repository")
    async def create_issue(self, interaction: discord.Interaction, owner: str, repo: str):
        if not GITHUB_TOKEN:
            await interaction.response.send_message(
                "GitHub token is not configured. Cannot create issues.",
                ephemeral=True
            )
            return

        modal = CreateIssue()
        modal.set_repo(repo_owner=owner, repo_name=repo)
        await interaction.response.send_modal(modal)

    # defione the slash command to search for repos
    @app_commands.command(name="repo_search", description="Search repositories")
    @app_commands.describe(query="Search query (e.g., 'discord bot')", sort="Sort by (stars, forks, etc.)",
                           order="Order (asc, desc)")
    async def search_repos(self, interaction: discord.Interaction, query: str, sort: str = "stars",
                           order: str = "desc"):
        await interaction.response.defer()  # Defers the response to allow time for processing
        search_result = self.search_repositories(query, sort, order)
        await interaction.followup.send(search_result)

    # Define the slash command to list open issues
    @app_commands.command(name="list_issues", description="List open issues in a GitHub repository")
    @app_commands.describe(owner="Owner of the repository", repo="Name of the repository")
    async def list_issues(self, interaction: discord.Interaction, owner: str, repo: str):
        await interaction.response.defer()  # Defer response for processing time

        issues = self.get_open_issues(owner, repo)
        await interaction.followup.send(issues)

    # Show user github profile depending on whether they have it stored in user_settings or not
    @app_commands.command(name="show_profile", description="Show your github profile")
    @app_commands.describe(git="Optional: GitHub Username to lookup")
    async def show_profile(self, interaction: discord.Interaction, git: Optional[str] = None):
        await interaction.response.defer()
        if not git:
            # Check stored username first
            query = "SELECT github_username FROM user_settings WHERE id = $1;"
            record = await self.bot.pool.fetchrow(query, interaction.user.id)

            if not record or not record['github_username']:
                return await interaction.followup.send(
                    "No GitHub username stored. Run the `/settings github` command to store it! "
                    "Otherwise provide one to look up"
                )
            git = record['github_username']

        # fetch boy, fetch
        url = f"https://api.github.com/users/{git}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            if response.status_code == 200:
                data = response.json()
                embed = discord.Embed(
                    title=data['login'],
                    url=data['html_url'],
                    color=0x333333
                )
                embed.set_thumbnail(url=data['avatar_url'])

                # Add profile info
                if data.get('name'):
                    embed.add_field(name="Name", value=data['name'], inline=True)
                if data.get('location'):
                    embed.add_field(name="Location", value=data['location'], inline=True)
                if data.get('company'):
                    embed.add_field(name="Company", value=data['company'], inline=True)

                # Add stats
                embed.add_field(name="Public Repos", value=data['public_repos'], inline=True)
                embed.add_field(name="Followers", value=data['followers'], inline=True)
                embed.add_field(name="Following", value=data['following'], inline=True)

                if data.get('bio'):
                    embed.add_field(name="Bio", value=data['bio'], inline=False)

                embed.set_footer(text=f"Profile created: {data['created_at'][:10]}")

                await interaction.followup.send(embed=embed)
            elif response.status_code == 404:
                await interaction.followup.send(f"GitHub user `{git}` not found.")
            else:
                await interaction.followup.send(f"Failed to fetch GitHub profile. Status code: {response.status_code}")
        except Exception as e:
            await interaction.followup.send(f"Error occurd {str(e)}")

    @commands.group(hidden=True, invoke_without_command=True)
    @commands.is_owner()
    async def sql(self, ctx: Context, *, query: str):
        """Run some SQL."""
        # the imports are here because I imagine some people would want to use
        # this cog as a base for their other cog, and since this one is kinda
        # odd and unnecessary for most people, I will make it easy to remove
        # for those people.
        from utilFunc.formats import TabularData, plural
        import time

        query = self.cleanup_code(query)

        is_multistatement = query.count(';') > 1
        strategy: Callable[[str], Union[Awaitable[list[Record]], Awaitable[str]]]
        if is_multistatement:
            # fetch does not support multiple statements
            strategy = ctx.db.execute
        else:
            strategy = ctx.db.fetch

        try:
            start = time.perf_counter()
            results = await strategy(query)
            dt = (time.perf_counter() - start) * 1000.0
        except Exception:
            return await ctx.send(f'```py\n{traceback.format_exc()}\n```')

        rows = len(results)
        if isinstance(results, str) or rows == 0:
            return await ctx.send(f'`{dt:.2f}ms: {results}`')

        headers = list(results[0].keys())
        table = TabularData()
        table.set_columns(headers)
        table.add_rows(list(r.values()) for r in results)
        render = table.render()

        fmt = f'```\n{render}\n```\n*Returned {plural(rows):row} in {dt:.2f}ms*'
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode('utf-8'))
            await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
        else:
            await ctx.send(fmt)

    async def send_sql_results(self, ctx: Context, records: list[Any]):
        from utilFunc.formats import TabularData

        headers = list(records[0].keys())
        table = TabularData()
        table.set_columns(headers)
        table.add_rows(list(r.values()) for r in records)
        render = table.render()

        fmt = f'```\n{render}\n```'
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode('utf-8'))
            await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
        else:
            await ctx.send(fmt)

    @sql.command(name='schema', hidden=True)
    async def sql_schema(self, ctx: Context, *, table_name: str):
        """Runs a query describing the table schema."""
        query = """SELECT column_name, data_type, column_default, is_nullable
                   FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE table_name = $1
                """

        results: list[Record] = await ctx.db.fetch(query, table_name)

        if len(results) == 0:
            await ctx.send('Could not find a table with that name')
            return

        await self.send_sql_results(ctx, results)

    @sql.command(name='tables', hidden=True)
    async def sql_tables(self, ctx: Context):
        """Lists all SQL tables in the database."""

        query = """SELECT table_name
                   FROM information_schema.tables
                   WHERE table_schema='public' AND table_type='BASE TABLE'
                """

        results: list[Record] = await ctx.db.fetch(query)

        if len(results) == 0:
            await ctx.send('Could not find any tables')
            return

        await self.send_sql_results(ctx, results)

    @sql.command(name='sizes', hidden=True)
    async def sql_sizes(self, ctx: Context):
        """Display how much space the database is taking up."""

        # Credit: https://wiki.postgresql.org/wiki/Disk_Usage
        query = """
            SELECT nspname || '.' || relname AS "relation",
                pg_size_pretty(pg_relation_size(C.oid)) AS "size"
              FROM pg_class C
              LEFT JOIN pg_namespace N ON (N.oid = C.relnamespace)
              WHERE nspname NOT IN ('pg_catalog', 'information_schema')
              ORDER BY pg_relation_size(C.oid) DESC
              LIMIT 20;
        """

        results: list[Record] = await ctx.db.fetch(query)

        if len(results) == 0:
            await ctx.send('Could not find any tables')
            return

        await self.send_sql_results(ctx, results)

    @sql.command(name='explain', aliases=['analyze'], hidden=True)
    async def sql_explain(self, ctx: Context, *, query: str):
        """Explain an SQL query."""
        query = self.cleanup_code(query)
        analyze = ctx.invoked_with == 'analyze'
        if analyze:
            query = f'EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON)\n{query}'
        else:
            query = f'EXPLAIN (COSTS, VERBOSE, FORMAT JSON)\n{query}'

        json = await ctx.db.fetchrow(query)
        if json is None:
            return await ctx.send('Somehow nothing returned.')

        file = discord.File(io.BytesIO(json[0].encode('utf-8')), filename='explain.json')
        await ctx.send(file=file)

    @commands.command(hidden=True)
    async def repl(self, ctx: Context):
        """Launches an interactive REPL session."""
        variables = {
            'ctx': ctx,
            'bot': self.bot,
            'message': ctx.message,
            'guild': ctx.guild,
            'channel': ctx.channel,
            'author': ctx.author,
            '_': None,
        }

        if ctx.channel.id in self.sessions:
            await ctx.send('Already running a REPL session in this channel. Exit it with `quit`.')
            return

        self.sessions.add(ctx.channel.id)
        await ctx.send('Enter code to execute or evaluate. `exit()` or `quit` to exit.')

        def check(m):
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and m.content.startswith('`')

        while True:
            try:
                response = await self.bot.wait_for('message', check=check, timeout=10.0 * 60.0)
            except asyncio.TimeoutError:
                await ctx.send('Exiting REPL session.')
                self.sessions.remove(ctx.channel.id)
                break

            cleaned = self.cleanup_code(response.content)

            if cleaned in ('quit', 'exit', 'exit()'):
                await ctx.send('Exiting.')
                self.sessions.remove(ctx.channel.id)
                return

            executor = exec
            code = ''
            if cleaned.count('\n') == 0:
                # single statement, potentially 'eval'
                try:
                    code = compile(cleaned, '<repl session>', 'eval')
                except SyntaxError:
                    pass
                else:
                    executor = eval

            if executor is exec:
                try:
                    code = compile(cleaned, '<repl session>', 'exec')
                except SyntaxError as e:
                    await ctx.send(self.get_syntax_error(e))
                    continue

            variables['message'] = response

            fmt = None
            stdout = io.StringIO()

            try:
                with redirect_stdout(stdout):
                    result = executor(code, variables)
                    if inspect.isawaitable(result):
                        result = await result
            except Exception as e:
                value = stdout.getvalue()
                fmt = f'```py\n{value}{traceback.format_exc()}\n```'
            else:
                value = stdout.getvalue()
                if result is not None:
                    fmt = f'```py\n{value}{result}\n```'
                    variables['_'] = result
                elif value:
                    fmt = f'```py\n{value}\n```'

            try:
                if fmt is not None:
                    if len(fmt) > 2000:
                        await ctx.send('Content too big to be printed.')
                    else:
                        await ctx.send(fmt)
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                await ctx.send(f'Unexpected error: `{e}`')

    @commands.command(hidden=True)
    async def perf(self, ctx: Context, *, command: str):
        """Checks the timing of a command, attempting to suppress HTTP and DB calls."""

        msg = copy.copy(ctx.message)
        msg.content = ctx.prefix + command

        new_ctx = await self.bot.get_context(msg, cls=type(ctx))

        # Intercepts the Messageable interface a bit
        new_ctx._state = PerformanceMocker()  # type: ignore
        new_ctx.channel = PerformanceMocker()  # type: ignore

        if new_ctx.command is None:
            return await ctx.send('No command found')

        start = time.perf_counter()
        try:
            await new_ctx.command.invoke(new_ctx)
        except commands.CommandError:
            end = time.perf_counter()
            success = False
            try:
                await ctx.send(f'```py\n{traceback.format_exc()}\n```')
            except discord.HTTPException:
                pass
        else:
            end = time.perf_counter()
            success = True

        await ctx.send(f'Status: ✅ Time: {(end - start) * 1000:.2f}ms')


async def setup(bot):
    await bot.add_cog(Git(bot))

from typing import TYPE_CHECKING

from discord.ext import commands

from bot import OmelettePy
from utilFunc.context import Context

if TYPE_CHECKING:
    from utilFunc.context import Context


class User(commands.Cog):
    def __init__(self, bot: OmelettePy) -> None:
        self.bot: OmelettePy = bot
        self.pool = bot.pool

    async def can_mention(self, user_id: int) -> bool:
        """Check if a user allows mentions."""
        query = """
            SELECT allow_mentions
            FROM user_settings
            WHERE id = $1;
        """
        record = await self.pool.fetchrow(query, user_id)
        return record['allow_mentions'] if record else True

    @commands.hybrid_group()
    async def settings(self, ctx: Context):
        """Manage your bot settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @settings.command(name="github")
    async def set_github(self, ctx: Context, username: str):
        """Link your GitHub account."""
        query = """
            INSERT INTO user_settings (id, github_username)
            VALUES ($1, $2)
            ON CONFLICT (id)
            DO UPDATE SET github_username = $2;
        """
        await self.pool.execute(query, ctx.author.id, username)
        await ctx.send(f"GitHub username set to: {username}")

    @settings.command(name="mentions")
    async def toggle_mentions(self, ctx: Context, enabled: bool):
        """Toggle whether the bot can mention you."""
        query = """
            INSERT INTO user_settings (id, allow_mentions)
            VALUES ($1, $2)
            ON CONFLICT (id)
            DO UPDATE SET allow_mentions = $2;
        """
        await self.pool.execute(query, ctx.author.id, enabled)
        status = "enabled" if enabled else "disabled"
        await ctx.send(
            f"Mentions are now {status}. "
            f"{'You will' if enabled else 'You will not'} be mentioned in bot responses."
        )

    @settings.command(name="show")
    async def show_settings(self, ctx: Context):
        """Show your current settings."""
        query = """
            SELECT github_username, allow_mentions, id, timezone
            FROM user_settings
            WHERE id = $1;
        """
        record = await self.pool.fetchrow(query, ctx.author.id)
        if record:
            github = record['github_username'] or 'Not set'
            time = record['timezone'] or 'Not set'
            mentions = 'Enabled' if record['allow_mentions'] else 'Disabled'
            userID = record['id']
            await ctx.send(f"__**Settings**__\n"
                           f"`User ID: {userID}`\n"
                           f"`Time Zone: {time}`"
                           f"\n`GitHub: {github}`\n"
                           f"`Mentions: {mentions}`")
        else:
            await ctx.send("No settings found. Use the settings commands to configure.")


async def setup(bot):
    await bot.add_cog(User(bot))

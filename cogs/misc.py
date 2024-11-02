import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context


class Misc(commands.Cog, name="Misc"):
    def __init__(self, bot) -> None:
        self.bot = bot


    @commands.command(
        name="ping",
        description="this is a ping command",
    )
    async def ping(self, context: Context) -> None:
        """
        This is a ping command

        :param context: pong.
        """
        embed=discord.Embed(
            title="Pong.",
            description=f"Latency: {round(self.bot.latency * 1000)}ms.",
            color=discord.Color.magenta()
        )
        await context.send(embed=embed)



async def setup(bot) -> None:
    await bot.add_cog(Misc(bot))
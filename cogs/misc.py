from difflib import SequenceMatcher

import discord
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

        # create bot listener

    @commands.Cog.listener("on_command_error")
    async def autocorrect_command(self, ctx, error):
        if not isinstance(error, commands.CommandNotFound):
            raise error
        message = ctx.message
        used_prefix = ctx.prefix
        used_command = message.content.split()[0][len(used_prefix):]  # `!foo a b c -> foo`
        available_commands = [cmd.name for cmd in self.bot.commands]
        matches = {
            cmd: SequenceMatcher(None, cmd, used_command).ratio()
            for cmd in available_commands
        }
        command = max(matches.items(), key=lambda x: x[1])[0]  # most similar command
        await ctx.send(f"{used_command!r} not found, did you mean {command!r}? (y/n)")
        m = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author)
        if m.content.lower() not in ("y", "yes"):
            # help_cmd=self.bot.get_command("help")
            await ctx.send(f"Sorry I couldn't find that for you. Please run the **`^help`** command!\n\n"
                           f"Error message: **`{error}`**")
            # await ctx.send_help(ctx.command)
            return
        try:
            args = message.content.split(" ", 1)[1]
        except IndexError:
            args = ""
        new_content = f"{used_prefix}{command} {args}".strip()
        message.content = new_content
        await self.bot.process_commands(message)


async def setup(bot) -> None:
    await bot.add_cog(Misc(bot))
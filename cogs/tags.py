import sqlite3
import traceback
from typing import Literal, Optional

import discord
import numpy as np
from discord import app_commands
from discord.ext import commands

"""
This is the tags cog.
Most information is provided in the associated
commands.

- Char.
"""

#Database connection
db = sqlite3.connect('tags.db', timeout = 30000)
cursor = db.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS tag_list (tag_name TEXT NOT NULL,tag_content TEXT NOT NULL)')
print("Loaded tags data set")
db.commit()


class TagMakeModal(discord.ui.Modal, title='Create New Tag'):
    name = discord.ui.TextInput(label='Name', required=True, max_length=100, min_length=1)
    content = discord.ui.TextInput(
        label='Content', required=True, style=discord.TextStyle.long, min_length=1, max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        cursor.execute("SELECT tag_name FROM tag_list WHERE tag_name=?", (self.name.value,))
        does_exist = cursor.fetchone()
        if does_exist is None:
            cursor.execute('insert into tag_list (tag_name, tag_content) values (?,?)',
                           (self.name.value, self.content.value))
            db.commit()  # commit new tag / content
            await interaction.response.send_message(f"Thanks! {self.name.value} has been created!", ephemeral=True)
        else:
            return

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(f"You fucked up! {error}", ephemeral=True)
        traceback.print_exception(type(error), error, error.__traceback__)





class tags(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

    def convertTuple(self, tup):
        str=''.join(tup)
        return str

    @app_commands.command(name="new-tag")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def tag_create(self, interaction: discord.Interaction) -> None:
        """
        This command will open a modal for you to create a new tag.
        """
        await interaction.response.send_modal(TagMakeModal())

    @commands.hybrid_command(name="tag")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def tag_find(self, ctx: commands.Context, tag_name: str):
        """
        This is the command you will use to find a tag from the database.
        Context: ^tag <name_of_tag>

        :param tag_name: The name of the tag you want to find
        """
        try:
            cursor.execute("SELECT tag_content FROM tag_list WHERE (tag_name)=? LIMIT 1 COLLATE NOCASE", (tag_name,))
            query = cursor.fetchone() # search db for tag name.
            output="\"" + str(query[0]) + "\""
            np_output=(output.replace('"', ''))
            # embed = discord.Embed(description=f"{np_output}\n\n"
            #                                   f"-# **`Tag:` {tag_name}**",
            #                       colour=discord.Colour.random())
            # await ctx.send(f"{np_output}\n\n"
            #                f"-# **`Tag: {tag_name}`**")
            await ctx.send(f"{np_output}\n"
                           f"-# **`Tag:` {tag_name}**")
        except Exception as e:
            cursor.execute("SELECT tag_name FROM tag_list WHERE tag_name LIKE (?) LIMIT 4", ('%' + tag_name + '%',))
            query = cursor.fetchall()
            # Limiting to 4 so it isn't damn near ridiculous

            #begin converting tuple to string via numpy
            #ive found this is the most efficient method for removing
            # the extra shit in a tuple while also keeping the whole list.
            np_query=np.array(query)
            np_str_query=np.array2string(np_query, separator=', ')
            np_str_clean=((np_str_query.replace('[', '').
                          replace(']', '')).
                          replace("'", ''))
            if np_str_clean=="":
                return
            else:
                #fucking convoluted as hell
                await ctx.send(f"**No tags corresponding to `{tag_name}` were found.**\n"
                               f"***Did you mean...***\n"
                               f"{np_str_clean}")
        db.commit()


    @tag_create.error #error catching for tag creation
    async def tag_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send('Please provide a tag name and tag content\n'
                           'Tag name should follow this format:\n'
                           '**`^tag_create <tag_name> <tag_content>`**\n'
                           '`<tag_name>` should not include any spaces, inclusion of a space will result'
                           'in an erroneous database commit.\n'
                           'Instead use hyphenation, underscore, and numbering.')

    @tag_find.error # error catching for tag finding
    async def tag_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send('Please provide a tag name')

    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, guilds: commands.Greedy[discord.Object],
                   spec: Optional[Literal["~", "*", "^"]] = None) -> None:
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(tags(bot))
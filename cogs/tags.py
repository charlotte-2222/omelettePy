import numpy as np

import discord
from discord.ext import commands

import sqlite3


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


class tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    def convertTuple(self, tup):
        str=''.join(tup)
        return str

    @commands.command(description="This command will create a new tag.\n"
                                  "Context: ^tag_create <tag_name> <tag_content>\n"
                                  "Warning: <tag_name> should not include any spaces, inclusion of a space "
                                  "will begin creation of <tag_content>. Instead, use hyphenation, underscore, and numbering.",
                      aliases=['create_tag', 'newTag'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def tag_create(self, ctx, *, first_string:str):
        """
        This command will create a new tag.
        Context: ^tag_create <tag_name> <tag_content>^

        Warning: <tag_name> should not include any spaces, inclusion of a space
        will begin creation of <tag_content>. Instead, use hyphenation, underscore, and numbering.

        :param first_string: The string that will be used as a tag.
        """
        new_tag, new_content = first_string.split(" ", 1)
        cursor.execute("SELECT tag_name FROM tag_list WHERE tag_name=?", (new_tag,))
        does_exist = cursor.fetchone()

        if does_exist is None:
            cursor.execute('insert into tag_list (tag_name, tag_content) values (?,?)', (new_tag, new_content))
            db.commit() #commit new tag / content
            await ctx.send(f"**`Tag for {new_tag}`** created!")
        else:
            await ctx.send("**`Tag already exists`**") #error.


    @commands.command(description="This is the command you will use to find a tag from the database.\n"
                                  "Context: ^tag <name_of_tag>",
                      aliases=['tag'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def tag_find(self, ctx, tag_name:str):
        """
        This is the command you will use to find a tag from the database.
        Context: ^tag <name_of_tag>

        :param tag_name: The name of the tag you want to find
        """
        try:
            cursor.execute("SELECT tag_content FROM tag_list WHERE (tag_name)=? LIMIT 1 COLLATE NOCASE", (tag_name,))
            query = cursor.fetchone() # search db for tag name.
            output="\"" + str(query[0]) + "\""
            embed = discord.Embed(title=f"**{tag_name}**",
                                  description=f"{output}",
                                  colour=discord.Colour.random())
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"**No tags corresponding to `{tag_name}` were found, **")
            cursor.execute("SELECT tag_name FROM tag_list WHERE tag_name LIKE (?)", ('%'+tag_name+'%',))
            query = cursor.fetchall()
            #begin converting tuple to string via numpy
            #ive found this is the most efficient method for removing
            # the extra shit in a tuple while also keeping the whole list.
            np_query=np.array(query)
            np_str_query=np.array2string(np_query, separator=', ')
            np_str_clean=((np_str_query.replace('[', '').
                          replace(']', '')).
                          replace("'", ''))
            #fucking convoluted as hell
            embed = discord.Embed(title=f"**Did you mean...**",
                                  description=f"{np_str_clean}",
                                  colour=discord.Colour.random())
            await ctx.send(embed=embed)
        db.commit()

    @tag_create.error #error catching for tag creation
    async def tag_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send('Please provide a tag name and tag content\n'
                           'Tag name should follow this format:\n'
                           '^tag_create <tag_name> <tag_content>\n'
                           '<tag_name> should not include any spaces, inclusion of a space will result'
                           'in an erroneous database commit.\n'
                           'Instead use hyphenation, underscore, and numbering.')

    @tag_find.error # error catching for tag finding
    async def tag_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send('Please provide a tag name')





async def setup(bot):
    await bot.add_cog(tags(bot))
import sqlite3
import time
import traceback
from datetime import datetime

import discord
import numpy as np
from discord import app_commands
from discord.ext import commands

db = sqlite3.connect('quotes.db', timeout=30000)
cursor = db.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS quotes(hash TEXT primary key, '
               'user TEXT, message TEXT, date_added TEXT, guild_id INT)')
print("Loaded Quotes database")
db.commit()

def to_emoji(c):
    base = 0x1f1e6
    return chr(base + c)

def error_filing():
    try:
        print(4 / 0)
    except ZeroDivisionError:
        print(traceback.format_exc())


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("egg thing online\n")
        print(f"Logged in as {self.bot.user} - {self.bot.user.id}\n")
        print("--------------")
        print(time.strftime(f"Time at start:\n"
                            "%H:%M:%S\n"
                            "%m/%d/%Y\n"))

    @app_commands.command(name="quote")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def quote(self, interaction: discord.Interaction, user: str, message: str):
        """
        This command will quote a user's message
        :param user: The user being quoted (use @)
        :param message: The message being quoted
        """
        # converted to slash commands
        guild = interaction.guild
        uniqueID = hash(user + message)

        # date and time of the message
        time = datetime.now()
        formatted_time = str(time.strftime("%a, %d %b %Y %H:%M:%S"))

        # find if message is in the db already
        cursor.execute("SELECT count(*) FROM quotes WHERE hash = ? AND guild_id = ?",
                       (uniqueID, guild.id))
        find = cursor.fetchone()[0]

        if find > 0:
            return

        # insert into database
        cursor.execute("INSERT INTO quotes VALUES(?,?,?,?,?)",
                       (uniqueID, user, message, formatted_time, guild.id))
        await interaction.response.send_message("Quote added!", ephemeral=True)

        db.commit()

        # number of words in the database
        rows = cursor.execute("SELECT * from quotes")
        # print logging
        print(str(len(rows.fetchall())) + ". added - " + str(user) + ": \"" + str(
            message) + "\" to database at " + formatted_time)

    @commands.hybrid_command(name="get-quote")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def gq(self, ctx: commands.Context, user: str):
        """
        This command will get a random quote from a specific user
        :param user: The user you wish to get a quote from.
        """
        # sanitise name
        user = (user,)
        guild = ctx.guild

        try:
            # query random quote from user
            cursor.execute(
                "SELECT message,date_added FROM quotes WHERE user=(?) AND guild_id=(?) ORDER BY RANDOM() LIMIT 1", user,
                guild.id)
            query = cursor.fetchone()

            # adds quotes to message
            output = "\"" + str(query[0]) + "\""

            np_query = np.array(user)
            np_str_query = np.array2string(np_query, separator=', ')
            np_str_clean = (((((np_str_query.
                                replace('(', '').
                                replace('])', '')).
                               replace("'", '')).
                              replace(",", "")).
                             replace("[", "")).
                            replace("]", ""))

            # embeds the output to make it pretty
            style = discord.Embed(description=f"{output}" + f"\n\n- {np_str_clean} \n" + str(query[1]),
                                  colour=discord.Color.random())
            #style.set_author(name=output)
            await ctx.reply(embed=style)

        except Exception:

            await ctx.reply("No quotes of that user found")

        db.commit()

    @commands.hybrid_command(name="random-quote")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def rq(self, ctx: commands.Context):
        """
        This command will get a random quote from a random user.
        """
        guild = ctx.guild
        cursor.execute("SELECT user,message,date_added FROM quotes WHERE guild_id=(?) ORDER BY RANDOM() LIMIT 1",
                       guild.id)
        query = cursor.fetchone()

        # log
        print(query[0] + ": \"" + query[1] + "\" printed to the screen " + str(query[2]))

        # embeds the output
        style = discord.Embed(title="responding quote",
                              description=str(query[1]) +
                                          "\n\n- "+ str(query[0]) + " " + "\n"+str(query[2]),
                              colour=discord.Color.random())
        await ctx.reply(embed=style)

    @quote.error
    async def quote_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("Missing required argument\n"
                            "Please follow correct syntax: **`^qt <@user> <message>`**")

    @gq.error
    async def getquote_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("Missing required argument\n"
                            "Please follow correct syntax: **`^gq <@user>`**")

    @rq.error
    async def randomquote_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("Missing required argument\n"
                            "Literally just use `^rq`")


async def setup(bot):
    await bot.add_cog(Events(bot))
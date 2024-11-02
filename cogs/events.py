import logging
import sqlite3
import time
from datetime import datetime
from dbm import error

import discord
from discord.ext import commands

import traceback
import sys, os

db = sqlite3.connect('quotes.db', timeout=30000)
cursor = db.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS quotes(hash TEXT primary key, user TEXT, message TEXT, date_added TEXT)')
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
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("egg thing online\n")
        print(f"Logged in as {self.bot.user} - {self.bot.user.id}\n")
        print("--------------")
        print(time.strftime(f"Time at start:\n"
                            "%H:%M:%S\n"
                            "%m/%d/%Y\n"))


    # @commands.Cog.listener()
    # async def on_command_error(self, ctx, error):
    #     try:
    #         raise isinstance(error, commands.CheckFailure)
    #     except Exception as e:
    #         exc_type, exc_obj, exc_tb = sys.exc_info()
    #         fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    #
    #     errorEm = discord.Embed(title="FUCKKEINF",
    #                             description=f"i make fuck\n\n"
    #                                         f"the fuck: \n**{error}**\n\n"
    #                                         f"**Additional Information**\n\n"
    #                                         f"{exc_type}\n{fname}\n{exc_tb.tb_lineno}\n",
    #                             colour=discord.Colour.magenta())
    #     errorEm.set_footer(text="im gonna kms")
    #     await ctx.send(embed=errorEm)

    @commands.command(help="Adds a quote of the mentioned user to Fembot's Database",
                      hidden=False,
                      aliases=['qt'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def quote(self, ctx, *, message: str):
        # split the message into words
        string = str(message)
        temp = string.split()

        # take the username out
        user = temp[0]
        del temp[0]

        # join the message back together
        text = " ".join(temp)

        if user[1] != '@':
            await ctx.reply("Use ```@[user] [message]``` to quote a person")
            return

        uniqueID = hash(user + message)

        # date and time of the message
        time = datetime.now()
        formatted_time = str(time.strftime("%a, %d %b %Y %H:%M:%S"))

        # find if message is in the db already
        cursor.execute("SELECT count(*) FROM quotes WHERE hash = ?", (uniqueID,))
        find = cursor.fetchone()[0]

        if find > 0:
            return

        # insert into database
        cursor.execute("INSERT INTO quotes VALUES(?,?,?,?)", (uniqueID, user, text, formatted_time))
        await ctx.reply("Quote successfully added")

        db.commit()

        # number of words in the database
        rows = cursor.execute("SELECT * from quotes")

        # log to terminal
        print(str(len(rows.fetchall())) + ". added - " + str(user) + ": \"" + str(
            text) + "\" to database at " + formatted_time)

    @commands.command(help="Tag a user to pull one of their quotes from the database (randomly chosen)",
                      aliases=['gq'],
                      hidden=False)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def getquote(self, ctx, message: str):
        # sanitise name
        user = (message,)

        try:
            # query random quote from user
            cursor.execute("SELECT message,date_added FROM quotes WHERE user=(?) ORDER BY RANDOM() LIMIT 1", user)
            query = cursor.fetchone()

            # adds quotes to message
            output = "\"" + str(query[0]) + "\""

            # log
            print(message + ": \"" + output + "\" printed to the screen " + str(query[1]))

            # embeds the output to make it pretty
            style = discord.Embed(title="responding quote",
                                  description=f"{output}"+"\n\n- " + message + " \n" + str(query[1]),
                                  colour=discord.Color.random())
            #style.set_author(name=output)
            await ctx.reply(embed=style)

        except Exception:

            await ctx.reply("No quotes of that user found")

        db.commit()

    @commands.command(help="Pull a random quote from the database (across all users)",
                      aliases=['rq'],
                      hidden=False)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def randomquote(self, ctx):

        cursor.execute("SELECT user,message,date_added FROM quotes ORDER BY RANDOM() LIMIT 1")
        query = cursor.fetchone()

        # log
        print(query[0] + ": \"" + query[1] + "\" printed to the screen " + str(query[2]))

        # embeds the output
        style = discord.Embed(title="responding quote",
                              description=str(query[1]) +
                                          "\n\n- "+ str(query[0]) + " " + "\n"+str(query[2]),
                              colour=discord.Color.random())
        #style.set_author(name=str(query[1]))
        await ctx.reply(embed=style)

    @quote.error
    async def quote_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("Missing required argument\n"
                            "Please follow correct syntax: **`^qt <@user> <message>`**")
    @getquote.error
    async def getquote_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("Missing required argument\n"
                            "Please follow correct syntax: **`^gq <@user>`**")
    @randomquote.error
    async def randomquote_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("Missing required argument\n"
                            "Literally just use `^rq`")


async def setup(bot):
    await bot.add_cog(Events(bot))
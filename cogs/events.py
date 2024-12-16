import re
import sqlite3
import time
import traceback
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utilFunc.context import GuildContext, Context

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


class DisambiguateMember(commands.IDConverter, app_commands.Transformer):
    async def convert(self, ctx: Context, argument: str) -> discord.abc.User:
        # check if it's a user ID or mention
        match = self._get_id_match(argument) or re.match(r'<@!?([0-9]+)>$', argument)

        if match is not None:
            # exact matches, like user ID + mention should search
            # for every member we can see rather than just this guild.
            user_id = int(match.group(1))
            result = ctx.bot.get_user(user_id)
            if result is None:
                try:
                    result = await ctx.bot.fetch_user(user_id)
                except discord.HTTPException:
                    raise commands.BadArgument("Could not find this member.") from None
            return result

        # check if we have a discriminator:
        if len(argument) > 5 and argument[-5] == '#':
            # note: the above is true for name#discrim as well
            name, _, discriminator = argument.rpartition('#')
            pred = lambda u: u.name == name and u.discriminator == discriminator
            result = discord.utils.find(pred, ctx.bot.users)
        else:
            matches: list[discord.Member | discord.User]
            # disambiguate I guess
            if ctx.guild is None:
                matches = [user for user in ctx.bot.users if user.name == argument]
                entry = str
            else:
                matches = [
                    member
                    for member in ctx.guild.members
                    if member.name == argument or (member.nick and member.nick == argument)
                ]

                def to_str(m):
                    if m.nick:
                        return f'{m} (a.k.a {m.nick})'
                    else:
                        return str(m)

                entry = to_str

            try:
                result = await ctx.disambiguate(matches, entry)
            except Exception as e:
                raise commands.BadArgument(f'Could not find this member. {e}') from None

        if result is None:
            raise commands.BadArgument("Could not find this member. Note this is case sensitive.")
        return result

    @property
    def type(self) -> discord.AppCommandOptionType:
        return discord.AppCommandOptionType.user

    async def transform(self, interaction: discord.Interaction, value: discord.abc.User) -> discord.abc.User:
        return value






class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Logged in as {self.bot.user} - {self.bot.user.id}\n")
        print("--------------")
        print(time.strftime(f"Time at start:\n"
                            "%H:%M:%S\n"
                            "%m/%d/%Y\n"))

    @app_commands.command(name="quote")
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def quote(self, interaction: discord.Interaction, user: str, message: str):
        """
        This command will quote a user's message
        :param user: The user being quoted (use @)
        :param message: The message being quoted
        """
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
    async def gq(self, ctx, user: str):
        """
        This command will get a random quote from a specific user
        :param ctx: guild context
        :param user: The user you wish to get a quote from.
        """
        guild = ctx.guild
        # user=(user,) <-- Unnecessary, but keeping
        try:

            cursor.execute(
                "SELECT message,date_added FROM quotes WHERE user=? AND guild_id=? ORDER BY RANDOM() LIMIT 1",
                (user, guild.id))  # pass parameters as tuple
            query = cursor.fetchone()

            if query is None:
                await ctx.reply("No quotes found for this user.")
                return

            # Adds quotes to message
            output = f"\"{query[0]}\""
            # embeds the output to make it pretty
            style = discord.Embed(description=f"**{output}**" + f"\n\n*Quoted User:*  {user} \n" + str(query[1]),
                                  colour=discord.Color.random())
            # style.set_author(name=output)
            await ctx.reply(embed=style)

        except Exception as e:
            await ctx.reply(f"Error occurred in command: \n`{str(e)}`")

        db.commit()

    @commands.hybrid_command(name="random-quote")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def rq(self, ctx: GuildContext):
        """
        This command will get a random quote from a random user.
        """
        guild = ctx.guild
        cursor.execute("SELECT user,message,date_added FROM quotes WHERE guild_id=(?) ORDER BY RANDOM() LIMIT 1",
                       (guild.id,))  # tuple parameter for guild ID
        query = cursor.fetchone()

        # log
        print(query[0] + ": \"" + query[1] + "\" printed to the screen " + str(query[2]))

        # embeds the output
        style = discord.Embed(title="responding quote",
                              description=str(query[1]) +
                                          "\n\n- "+ str(query[0]) + " " + "\n"+str(query[2]),
                              colour=discord.Color.random())
        await ctx.reply(embed=style)



async def setup(bot):
    await bot.add_cog(Events(bot))
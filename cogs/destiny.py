import discord
from discord.ext import commands, tasks
import bungio
from bungio.models import DestinyPublicVendorComponent, VendorItemStatus, DestinyPublicVendorsResponse, \
    DestinyVendorSaleItemSetComponentOfDestinyPublicVendorSaleItemComponent, VendorDisplayCategorySortOrder, \
    SingleComponentResponseOfDestinyStringVariablesComponent

import datetime

est=datetime.timezone.utc
# time=datetime.time(hour=13,minute=20,second=00)

class Destiny(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # @tasks.loop(time=time)
    # async def d_vendor_upd(self, ctx):
    #     channel= discord.utils.get(ctx.guild.text_channels, name="d2-stuff")
    #     await channel.send(DestinyPublicVendorsResponse.vendors.data)

    # @commands.command()
    # async def destiny_test(self, ctx):
    #     b=
    #
    #     await ctx.send(f"{b}")



async def setup(bot):
    await bot.add_cog(Destiny(bot))
import discord
import openai
from discord import app_commands
from discord.ext import commands

from bot import chatgpt
from utilFunc.config import OPEN_AI_KEY

# from GPT.api_access import *

openai.api_key = OPEN_AI_KEY

if not OPEN_AI_KEY:
    raise ValueError("OPEN_AI_KEY environment variable not set")


class ChatGPTCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

    @app_commands.command(name='ask-ai', description='Talk with the AI version of Ommie')
    async def ask_ai(self, interaction: discord.Interaction, message: str):
        user_id = interaction.user.id
        await interaction.response.defer()

        # Ensure you get the response from ChatGPT
        response = chatgpt.get_response(user_id, message)
        await interaction.followup.send(response)  # Send the response from ChatGPT


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ChatGPTCog(bot))

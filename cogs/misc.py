import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import utilFunc.config


class Misc(commands.Cog, name="Misc"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.weather_cache = {}
        self.cach_timeout = 300  # 5 minutes

    @commands.hybrid_command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        """
        This is a ping command

        :param context: pong.
        """
        embed=discord.Embed(
            title="Pong.",
            description=f"Latency: {round(self.bot.latency * 1000)}ms.",
            color=discord.Color.magenta()
        )
        await ctx.send(embed=embed)

    @app_commands.command(name="weather")
    @app_commands.describe(city="The city to get the weather for",
                           units="The units to get the weather for",
                           detailed="Whether to get detailed weather or not")
    @app_commands.choices(units=[
        app_commands.Choice(name="Imperial (°F)", value="imperial"),
        app_commands.Choice(name="Metric (°C)", value="metric")
    ])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def weather(self, interaction: discord.Interaction,
                      city: str,
                      units: app_commands.Choice[str] = None,
                      detailed: bool = False):
        """
        This command will get the weather for a city
        :param city: The city to get the weather for
        :param units: The units to get the weather for
        :param detailed: Whether to get detailed weather or not
        """

        unit_system = "imperial" if units is None else units.value

        # check if the city is in the cache
        cache_key = f"{city}_{unit_system}"
        if cache_key in self.weather_cache:
            cached_data = self.weather_cache[cache_key]
            if (discord.utils.utcnow() - cached_data['timestamp']).total_seconds() < self.cach_timeout:
                await interaction.response.send_message(embed=cached_data['embed'])
                return

        async with aiohttp.ClientSession() as session:
            async with session.get(
                    f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={utilFunc.config.OW_API}&units={unit_system}") as response:
                data = await response.json()

                if data['cod'] == 200:
                    temp_unit = "°F" if unit_system == "imperial" else "°C"
                    speed_unit = "mph" if unit_system == "imperial" else "km/h"

                    weather_description = data['weather'][0]['description']
                    temperature = data['main']['temp']
                    humidity = data['main']['humidity']
                    wind_speed = data['wind']['speed']

                    embed = discord.Embed(
                        title=f"Weather in {data['name']} {data.get('sys', {}).get('country', '')}",
                        color=self._get_weather_color(data['weather'][0]['id'])
                    )

                    # Basic weather info reply
                    embed.add_field(
                        name="Current Conditions",
                        value=f"Temperature: {data['main']['temp']}{temp_unit}\n"
                              f"Feels like: {data['main']['feels_like']}{temp_unit}\n"
                              f"Wind Speed: {data['wind']['speed']}{speed_unit}\n"
                              f"Humidity: {data['main']['humidity']}%\n",
                        inline=False

                    )

                    # Weather iconm
                    icon_code = data['weather'][0]['icon']
                    embed.set_thumbnail(url=f"http://openweathermap.org/img/wn/{icon_code}.png")

                    if detailed:
                        # Convert visibility from meters
                        visibility = data.get('visibility', 0)
                        if visibility:
                            if unit_system == "imperial":
                                # Convert meters to miles
                                visibility_converted = round(visibility * 0.000621371, 2)
                                visibility_unit = "mi"
                            else:
                                # Convert meters to kilometers
                                visibility_converted = round(visibility / 1000, 2)
                                visibility_unit = "km"

                            visibility_text = f"{visibility_converted} {visibility_unit}"
                        else:
                            visibility_text = "N/A"

                    # Detailed weather info
                    if detailed:
                        embed.add_field(
                            name="Additional Details",
                            value=f"Sunrise: <t:{data['sys']['sunrise']}:t>\n"
                                  f"Sunset: <t:{data['sys']['sunset']}:t>\n"
                                  f"Min Temperature: {data['main']['temp_min']}{temp_unit}\n"
                                  f"Max Temperature: {data['main']['temp_max']}{temp_unit}\n"
                                  f"Visibility: {visibility_text}\n"
                                  f"Cloudiness: {data['clouds']['all']}%\n",
                            inline=False
                        )
                        if 'rain' in data:
                            embed.add_field(
                                name="Rain",
                                value=f"1h: {data['rain'].get('1h', 'N/A')}mm\n"
                                      f"3h: {data['rain'].get('3h', 'N/A')}mm\n",
                                inline=False
                            )
                    embed.set_footer(text=f"Last updated: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

                    if 'alerts' in data:
                        alerts = data['alerts']
                        alert_text = '\n'.join(f"⚠️ {alert['event']}" for alert in alerts[:3])
                        embed.add_field(name="Weather Alerts", value=alert_text, inline=False)

                    # Cache the data
                    self.weather_cache[cache_key] = {
                        'embed': embed,
                        'timestamp': discord.utils.utcnow()
                    }

                    await interaction.response.send_message(embed=embed)
                else:
                    # Handle error response
                    await interaction.response.send_message(f"Could not find data for {city}", ephemeral=True)

    def _get_weather_color(self, weather_id: int) -> discord.Color:
        """Return color based on weather condition code"""
        if weather_id < 300:  # Thunderstorm
            return discord.Color.dark_grey()
        elif weather_id < 400:  # Drizzle
            return discord.Color.blue()
        elif weather_id < 600:  # Rain
            return discord.Color.dark_blue()
        elif weather_id < 700:  # Snow
            return discord.Color.light_grey()
        elif weather_id < 800:  # Atmosphere
            return discord.Color.dark_grey()
        elif weather_id == 800:  # Clear
            return discord.Color.gold()
        else:  # Clouds
            return discord.Color.light_grey()




async def setup(bot) -> None:
    await bot.add_cog(Misc(bot))
import os

from discord import Member
from discord.ext import commands

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.send_welcome_message(member)

    async def send_welcome_message(self, member: Member) -> None:
        channel_id = self.bot.get_settings(member.guild.id).greeting_channel_id
        channel = await self.bot.fetch_channel(channel_id)

        # Built line by line so no indentation leaks into the message. The trailing rule keeps
        # consecutive welcome posts apart when several members join within a few minutes.
        welcome_message = "\n".join([
            f"Hey {member.mention},",
            "schön, dass du hergefunden hast :nerd:",
            "",
            f"Unsere Serverregeln findest du hier: <#{os.getenv('DISCORD_RULE_CHANNEL')}>",
            f"Antworten auf häufig gestellte Fragen findest du hier: <#{os.getenv('DISCORD_FAQ_CHANNEL')}>",
            f"Weitere Informationen zu den Funktionen des Servers und des Bots findest du hier: "
            f"<#{os.getenv('DISCORD_BOT_MANUAL_CHANNEL')}>",
            f"Zur Lerngruppen-Suche geht es hier lang: <#{os.getenv('DISCORD_LEARNINGGROUPS_POST')}>",
            f"Quatschen kannst du hier: <#{os.getenv('DISCORD_CHATTING_CHANNEL_1')}> oder "
            f"<#{os.getenv('DISCORD_CHATTING_CHANNEL_2')}>",
            f"Stelle gerne Fragen an die Admins/Moderation per DM an {self.bot.user.mention} oder einfach hier: "
            f"<#{os.getenv('DISCORD_QUESTIONS_AND_ANSWERS_CHANNEL')}>",
            "─────────────────────────",
        ])

        await channel.send(welcome_message)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))

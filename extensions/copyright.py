import discord
from discord import app_commands, Interaction, Message
from discord.ext import commands

COPYRIGHT_TEXT = (
    "Hallo. Gemäß unserer Serverregeln bitten wir darum vom Erfragen und Teilen urheberrechtsgeschützter "
    "Inhalte abzusehen. Hierzu gehören auch Altklausuren, die nicht offiziell vom Lehrstuhl zur Verfügung "
    "gestellt werden. Wenn in Moodle wirklich keine Altklausuren zur Verfügung gestellt werden, gibt es oft "
    "entsprechendes Übungsmaterial in den Mentoriaten.\n\n"
    "Weiter viel Erfolg und viele Grüße, das Admin-Team. 🙂"
)


class Copyright(commands.Cog):
    """Standardhinweis zu urheberrechtsgeschützten Inhalten, nur für Rollen mit Manage Messages."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Kontextmenü: Rechtsklick auf eine Nachricht → Apps → Urheberrecht-Hinweis
        self.ctx_menu = app_commands.ContextMenu(name="Urheberrecht-Hinweis", callback=self.reply_with_notice)
        self.ctx_menu.default_permissions = discord.Permissions(manage_messages=True)
        self.ctx_menu.guild_only = True
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @app_commands.command(name="copyright", description="Postet den Hinweis zu urheberrechtsgeschützten Inhalten.")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def cmd_copyright(self, interaction: Interaction) -> None:
        await interaction.response.send_message(COPYRIGHT_TEXT)

    async def reply_with_notice(self, interaction: Interaction, message: Message) -> None:
        await message.reply(COPYRIGHT_TEXT, mention_author=True)
        await interaction.response.send_message("Hinweis als Antwort gesendet.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Copyright(bot))

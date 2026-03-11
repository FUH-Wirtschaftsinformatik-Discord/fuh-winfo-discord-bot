import discord
from discord.ext import commands
import json

ITEMS_PER_PAGE = 25

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# JSON LADEN
# =========================
with open("modules3.json", "r", encoding="utf-8") as f:
    CATEGORIES = json.load(f)["categories"]

# =========================
# SELECT MENU
# =========================
class ModuleSelect(discord.ui.Select):
    def __init__(self, modules, page, title):
        self.modules = modules
        self.page = page
        self.title = title

        start = page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = modules[start:end]

        options = [
            discord.SelectOption(
                label=f"{m['id']} – {m['description'][:40]}",
                value=m["id"]
            )
            for m in page_items
        ]

        super().__init__(
            placeholder=f"📚 {title} (Seite {page + 1})",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        module = next(m for m in self.modules if m["id"] == self.values[0])
        channel = interaction.guild.get_channel(module["channel_id"])

        if not channel:
            await interaction.followup.send("❌ Kanal nicht gefunden.", ephemeral=True)
            return

        await interaction.followup.send(
            f"🔗 **Modul {module['id']}**\n➡️ {channel.mention}",
            ephemeral=True
        )

# =========================
# BUTTONS
# =========================
class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="➡️", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        view = interaction.message.view
        await interaction.response.edit_message(
            view=ModuleView(view.title, view.modules, view.page + 1)
        )

class PrevButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⬅️", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        view = interaction.message.view
        await interaction.response.edit_message(
            view=ModuleView(view.title, view.modules, view.page - 1)
        )

# =========================
# VIEW
# =========================
class ModuleView(discord.ui.View):
    def __init__(self, title, modules, page=0):
        super().__init__(timeout=None)

        self.title = title
        self.modules = modules
        self.page = page

        self.add_item(ModuleSelect(modules, page, title))

        if page > 0:
            self.add_item(PrevButton())

        if (page + 1) * ITEMS_PER_PAGE < len(modules):
            self.add_item(NextButton())

# =========================
# READY
# =========================
@bot.event
async def on_ready():
    print(f"✅ Eingeloggt als {bot.user}")
    await bot.tree.sync()
    print("✅Slash Commands synchronisiert")

# =========================
# COMMAND FACTORY
# =========================
def create_command(cmd_name, title, key):
    @bot.tree.command(
        name=cmd_name,
        description=f"Module anzeigen: {title}"
    )
    async def cmd(interaction: discord.Interaction):
        modules = CATEGORIES.get(key, [])

        if not modules:
            await interaction.response.send_message(
                "❌ Keine Module vorhanden.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"📚 **{title}**\nSeite 1 von {(len(modules)-1)//ITEMS_PER_PAGE + 1}",
            view=ModuleView(title, modules),
        )

# =========================
# SLASH COMMANDS
# =========================
create_command("module_pflicht", "Wiinfo Pflichtmodule", "Wiinfo Pflichtmodule")
create_command("module_wahl_3", "Wahlpflichtmodule 3xxxx", "Wahlpflichtmodule 3xxxx")
create_command("module_wahl_6", "Wahlpflichtmodule 6xxxx", "Wahlpflichtmodule 6xxxx")
create_command("module_master", "Wiinfo Mastermodule 32xxx", "Wiinfo Mastermodule 32xxx")

# =========================
# START
# =========================
bot.run("BOT_TOKEN")
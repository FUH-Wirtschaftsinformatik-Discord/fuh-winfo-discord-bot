import discord

class ModuleView(discord.ui.View):
    def __init__(self, title, modules, page=0):
        super().__init__(timeout=None)

        self.title = title
        self.modules = modules
        self.page = page

        self.add_item(ModuleSelect(modules, page, title))

        if page > 0:
            self.add_item(PrevButton())

        if (page + 1) * 25 < len(modules):
            self.add_item(NextButton())

class ModuleSelect(discord.ui.Select):
    def __init__(self, modules, page, title):
        self.modules = modules
        self.page = page
        self.title = title

        start = page * 25
        end = start + 25
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

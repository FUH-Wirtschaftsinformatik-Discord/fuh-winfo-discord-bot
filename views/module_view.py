import discord


class ModuleView(discord.ui.View):
    def __init__(self, title, modules, menu_key: str, page=0):
        super().__init__(timeout=None)

        self.title = title
        self.modules = modules
        self.page = page
        self.menu_key = menu_key

        self.add_item(ModuleSelect(modules, page, title, self.menu_key))

        if page > 0:
            self.add_item(PrevButton(self.menu_key))

        if (page + 1) * 25 < len(modules):
            self.add_item(NextButton(self.menu_key))


class ModuleSelect(discord.ui.Select):
    def __init__(self, modules, page, title, menu_key: str):
        self.modules = modules
        self.page = page
        self.title = title
        self.menu_key = menu_key

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

        # Fallback option so discord.py doesn't crash on an empty list during setup_hook
        if not options:
            options = [discord.SelectOption(label="Lädt...", value="loading")]

        super().__init__(
            placeholder=f"📚 {title} (Seite {page + 1})",
            options=options,
            custom_id=f"persistent_view:{self.menu_key}:module_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            module = next(m for m in self.modules if str(
                m["id"]) == self.values[0])
        except StopIteration:
            await interaction.followup.send("❌ Bot wurde neu gestartet. Bitte rufe das Menü mit dem Befehl neu auf.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(module["channel_id"])

        if not channel:
            await interaction.followup.send("❌ Kanal nicht gefunden.", ephemeral=True)
            return

        await interaction.followup.send(
            f"🔗 **Modul {module['id']}**\n➡️ {channel.mention}",
            ephemeral=True
        )


class NextButton(discord.ui.Button):
    def __init__(self, menu_key: str):
        self.menu_key = menu_key
        super().__init__(label="➡️",
                         style=discord.ButtonStyle.primary,
                         custom_id=f"persistent_view:{self.menu_key}:module_next")

    async def callback(self, interaction: discord.Interaction):
        view: ModuleView = self.view

        if not hasattr(view, 'modules') or not view.modules:
            await interaction.response.send_message("❌ Menü abgelaufen (Bot Neustart). Bitte neu laden.", ephemeral=True)
            return

        await interaction.response.edit_message(
            view=ModuleView(view.title, view.modules, view.page + 1)
        )


class PrevButton(discord.ui.Button):
    def __init__(self, menu_key: str):
        self.menu_key = menu_key
        super().__init__(
            label="➡️",
            style=discord.ButtonStyle.primary,
            custom_id=f"persistent_view:{self.menu_key}:module_prev"
        )

    async def callback(self, interaction: discord.Interaction):
        view: ModuleView = self.view

        if not hasattr(view, 'modules') or not view.modules:
            await interaction.response.send_message("❌ Menü abgelaufen (Bot Neustart). Bitte neu laden.", ephemeral=True)
            return

        await interaction.response.edit_message(
            view=ModuleView(view.title, view.modules, view.page + 1)
        )

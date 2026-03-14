import re

import discord

class QuickMenuView(discord.ui.View):
    
    def __init__(self, title, modules, menu_key: str, page=0):
        super().__init__(timeout=None)

        self.title = title
        self.modules = modules
        self.page = page
        self.menu_key = menu_key

        # 1. Add the Select Menu
        self.add_item(QuickMenuSelect(modules, page, title, self.menu_key))

        # 2. Previous Button
        prev_button = QuickMenuPreviousButton(self.menu_key)
        if page <= 0:
            prev_button.disabled = True # Gray it out on the first page
        self.add_item(prev_button)

        # 3. Next Button
        next_button = QuickMenuNextButton(self.menu_key)
        if (page + 1) * 25 >= len(modules):
            next_button.disabled = True # Gray it out on the last page
        self.add_item(next_button)

class QuickMenuSelect(discord.ui.Select):
    
    def __init__(self, modules, page, title, menu_key: str):
        self.modules = modules
        self.page = page
        self.title = title
        self.menu_key = menu_key

        # execute pagination logic here to determine which modules to show on this page
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
            await interaction.followup.send("Bot wurde neu gestartet. Bitte rufe das Menü mit dem Befehl neu auf.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(module["channel_id"])

        if not channel:
            await interaction.followup.send("Kanal nicht gefunden.", ephemeral=True)
            return

        await interaction.followup.send(
            f"🔗 **Modul: {module['description'][:40]} ({module['id']})**\nKlicke auf die Schaltfläche: ➡️{channel.mention}",
            ephemeral=True
        )


class QuickMenuNextButton(discord.ui.Button):
    def __init__(self, menu_key: str):
        self.menu_key = menu_key
        super().__init__(label="➡️",
                         style=discord.ButtonStyle.primary,
                         custom_id=f"persistent_view:{self.menu_key}:module_next")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view: QuickMenuView = self.view

        if not hasattr(view, 'modules') or not view.modules:
            await interaction.response.send_message("❌ Menü abgelaufen (Bot Neustart). Bitte neu laden.", ephemeral=True)
            return

        current_page = 0
        try:
            # The Select Menu is always the first item in the first Action Row
            placeholder = interaction.message.components[0].children[0].placeholder
            
            # Extract the number from "(Seite X)"
            match = re.search(r'Seite (\d+)', placeholder)
            if match:
                current_page = int(match.group(1)) - 1
        except Exception:
            pass # Fallback to 0 if something goes wrong

        next_page = current_page + 1

        await interaction.message.edit(
            view=QuickMenuView(view.title, view.modules, self.menu_key, next_page)
        )


class QuickMenuPreviousButton(discord.ui.Button):
    def __init__(self, menu_key: str):
        self.menu_key = menu_key
        super().__init__(
            label="⬅️", 
            style=discord.ButtonStyle.primary,
            custom_id=f"persistent_view:{self.menu_key}:module_prev"
        )

    async def callback(self, interaction: discord.Interaction):
        # 1. INSTANTLY catch the interaction so Discord doesn't timeout!
        # Do not use ephemeral=True here, because we want to edit the public message.
        await interaction.response.defer()

        view: QuickMenuView = self.view

        if not hasattr(view, 'modules') or not view.modules:
            # Because we deferred, we must use followup.send() instead of response.send_message()
            await interaction.followup.send("❌ Menü abgelaufen (Bot Neustart). Bitte neu laden.", ephemeral=True)
            return

        current_page = 0
        try:
            placeholder = interaction.message.components[0].children[0].placeholder
            match = re.search(r'Seite (\d+)', placeholder)
            if match:
                current_page = int(match.group(1)) - 1
        except Exception:
            pass

        prev_page = max(current_page - 1, 0)

        # 2. Use message.edit() instead of response.edit_message() because we deferred!
        await interaction.message.edit(
            view=QuickMenuView(view.title, view.modules, self.menu_key, prev_page)
        )
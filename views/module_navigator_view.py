import re
from dataclasses import dataclass
import discord
from models import CustomMenuItem, ItemType, ModuleItem


@dataclass
class DisplayableMenuItem:
    label: str
    value: str
    type: str
    item: ModuleItem | CustomMenuItem


class ModuleNavigatorView(discord.ui.View):

    def __init__(self, title, modules: list[ModuleItem | CustomMenuItem], menu_key: str, page=0):
        super().__init__(timeout=None)

        self.title = title
        self.modules = modules
        self.page = page
        self.menu_key = menu_key

        displayable_items = []
        for m in modules:
            if isinstance(m, ModuleItem):
                displayable_items.append(DisplayableMenuItem(
                    label=f"{m.module_number} – {m.description[:40]}",
                    value=str(m.module_number),
                    type='module',
                    item=m
                ))
            elif isinstance(m, CustomMenuItem):
                displayable_items.append(DisplayableMenuItem(
                    label=m.label,
                    value=m.value,
                    type=m.item_type,
                    item=m
                ))

        self.displayable_items = displayable_items

        # 1. Add the Select Menu
        self.add_item(ModuleNavigatorMenuSelect(
            self.displayable_items, page, title, self.menu_key))

        # 2. Previous Button
        prev_button = ModuleNavigatorMenuPreviousButton(self.menu_key)
        if page <= 0:
            prev_button.disabled = True
        self.add_item(prev_button)

        # 3. Next Button
        next_button = ModuleNavigatorMenuNextButton(self.menu_key)
        if (page + 1) * 25 >= len(self.displayable_items):
            next_button.disabled = True
        self.add_item(next_button)


class ModuleNavigatorMenuSelect(discord.ui.Select):

    def __init__(self, items: list[DisplayableMenuItem], page, title, menu_key: str):
        self.items = items
        self.page = page
        self.title = title
        self.menu_key = menu_key

        start = page * 25
        end = start + 25
        page_items = items[start:end]

        options = [
            discord.SelectOption(
                label=item.label,
                value=item.value
            )
            for item in page_items
        ]

        if not options:
            options = [discord.SelectOption(label="Lädt...", value="loading")]

        super().__init__(
            placeholder=f"📚 {title} (Seite {page + 1})",
            options=options,
            custom_id=f"persistent_view:{self.menu_key}:module_select"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            selected_item = next(
                item for item in self.items if item.value == self.values[0])
        except StopIteration:
            await interaction.response.send_message("Bot wurde neu gestartet. Bitte rufe das Menü mit dem Befehl neu auf.", ephemeral=True)
            return

        if selected_item.type == 'module':
            channel = interaction.guild.get_channel(
                selected_item.item.module_channel_id)
            if not channel:
                await interaction.response.send_message("Kanal nicht gefunden.", ephemeral=True)
                return
            await interaction.response.send_message(
                f"🔗 **Modul: {selected_item.label}**\nKlicke auf die Schaltfläche um zum Kanal zu gelangen: ➡️{channel.mention}",
                ephemeral=True
            )
        elif selected_item.type == ItemType.URL:
            await interaction.response.send_message(f"🔗 **{selected_item.label}**\n{selected_item.value}", ephemeral=True)
        elif selected_item.type == ItemType.CHANNEL:
            channel = interaction.guild.get_channel(int(selected_item.value))
            if not channel:
                await interaction.response.send_message("Kanal nicht gefunden.", ephemeral=True)
                return
            await interaction.response.send_message(f"🔗 **{selected_item.label}**\n➡️{channel.mention}", ephemeral=True)
        elif selected_item.type == ItemType.POST:
            channel_id, message_id = selected_item.value.split('/')
            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.response.send_message("Kanal nicht gefunden.", ephemeral=True)
                return
            message = await channel.fetch_message(int(message_id))
            if not message:
                await interaction.response.send_message("Nachricht nicht gefunden.", ephemeral=True)
                return
            await interaction.response.send_message(f"🔗 **{selected_item.label}**\n{message.jump_url}", ephemeral=True)


class ModuleNavigatorMenuNextButton(discord.ui.Button):
    def __init__(self, menu_key: str):
        self.menu_key = menu_key
        super().__init__(label="➡️",
                         style=discord.ButtonStyle.primary,
                         custom_id=f"persistent_view:{self.menu_key}:module_next")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view: ModuleNavigatorView = self.view

        if not hasattr(view, 'modules') or not view.modules:
            await interaction.response.send_message("Menü abgelaufen (Bot Neustart). Bitte neu laden.", ephemeral=True)
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
            pass  # Fallback to 0 if something goes wrong

        next_page = current_page + 1

        await interaction.message.edit(
            view=ModuleNavigatorView(view.title, view.modules,
                                     self.menu_key, next_page)
        )


class ModuleNavigatorMenuPreviousButton(discord.ui.Button):
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

        view: ModuleNavigatorView = self.view

        if not hasattr(view, 'modules') or not view.modules:
            # Because we deferred, we must use followup.send() instead of response.send_message()
            await interaction.followup.send("Menü abgelaufen (Bot Neustart). Bitte neu laden.", ephemeral=True)
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
            view=ModuleNavigatorView(view.title, view.modules,
                                     self.menu_key, prev_page)
        )

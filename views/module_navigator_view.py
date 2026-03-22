import re
from dataclasses import dataclass
import discord
from models import ModuleNavigatorCustomMenuItem, ModuleNavigatorMenuItemLinkType, ModuleNavigatorModuleItem


@dataclass
class DisplayableMenuItem:
    """A helper dataclass to standardize module and custom items for display in the UI."""
    label: str
    value: str
    type: str
    item: ModuleNavigatorModuleItem | ModuleNavigatorCustomMenuItem


class ModuleNavigatorView(discord.ui.View):
    """
    The main persistent view for the module navigator.

    This class is responsible for rendering the select menu and the pagination buttons.
    It is re-constructed for each interaction (e.g., button click) to display a new state (page).
    The state (list of modules) is passed in during initialization.
    """

    def __init__(self, title: str, modules: list[ModuleNavigatorModuleItem | ModuleNavigatorCustomMenuItem], menu_key: str, page: int = 0):
        super().__init__(timeout=None)  # Persistent view

        self.title = title
        self.modules = modules
        self.page = page
        self.menu_key = menu_key  # Unique identifier for this menu instance.

        # Convert all raw module/custom items into a standardized format for easier UI handling.
        displayable_items = []
        for m in modules:
            if isinstance(m, ModuleNavigatorModuleItem):
                displayable_items.append(DisplayableMenuItem(
                    label=f"{m.module_number} – {m.description[:40]}",
                    value=str(m.module_number),
                    type='module',
                    item=m
                ))
            elif isinstance(m, ModuleNavigatorCustomMenuItem):
                displayable_items.append(DisplayableMenuItem(
                    label=m.label,
                    value=m.value,
                    type=m.link_type,
                    item=m
                ))
        self.displayable_items = displayable_items

        # 1. Add the main dropdown (Select Menu) for module selection.
        self.add_item(ModuleNavigatorMenuSelect(
            self.displayable_items, page, title, self.menu_key))

        # 2. Add the "Previous Page" button, disabling it if on the first page.
        prev_button = ModuleNavigatorMenuPreviousButton(self.menu_key)
        if page <= 0:
            prev_button.disabled = True
        self.add_item(prev_button)

        # 3. Add the "Next Page" button, disabling it if on the last page.
        next_button = ModuleNavigatorMenuNextButton(self.menu_key)
        if (page + 1) * 25 >= len(self.displayable_items):
            next_button.disabled = True
        self.add_item(next_button)

    @staticmethod
    def get_page_from_message(message: discord.Message) -> int:
        """
        Safely extracts the current page number from the view's placeholder text in a message.
        This is a workaround for the fact that custom attributes of a persistent view
        are not preserved across bot restarts. The state is read from the message itself.

        Args:
            message: The Discord message containing the view.

        Returns:
            The current page number (0-indexed) or 0 if not found.
        """
        try:
            # The Select Menu is assumed to be the first item in the first Action Row.
            placeholder = message.components[0].children[0].placeholder
            # Extract the number from "(Seite X)"
            match = re.search(r'Seite (\d+)', placeholder)
            if match:
                return int(match.group(1)) - 1
        except (IndexError, AttributeError):
            # If components are not as expected, or placeholder is missing, default to page 0.
            return 0
        return 0


class ModuleNavigatorMenuSelect(discord.ui.Select):
    """The dropdown menu that displays the list of modules for the current page."""

    def __init__(self, items: list[DisplayableMenuItem], page: int, title: str, menu_key: str):
        self.items = items
        self.page = page
        self.title = title
        self.menu_key = menu_key

        # Paginate the items to show only the 25 for the current page.
        start = page * 25
        end = start + 25
        page_items = items[start:end]

        options = [
            discord.SelectOption(label=item.label, value=item.value)
            for item in page_items
        ]

        # Show a loading message if there are no options to display.
        if not options:
            options = [discord.SelectOption(label="Lädt...", value="loading")]

        super().__init__(
            placeholder=f"📚 {title} (Seite {page + 1})",
            options=options,
            custom_id=f"persistent_view:{self.menu_key}:module_select"
        )

    async def callback(self, interaction: discord.Interaction):
        """
        Handles a user selecting an item from the dropdown menu.
        It sends an ephemeral message with a link corresponding to the selected item.
        """
        # Find the selected item from the full list of items.
        selected_item = next(
            (item for item in self.items if item.value == self.values[0]), None)

        if not selected_item:
            await interaction.response.send_message("Das Menü wurde aktualisiert. Bitte wähle erneut.", ephemeral=True)
            return

        # Handle 'module' items, which link to a channel.
        if selected_item.type == 'module':
            channel = interaction.guild.get_channel(selected_item.item.module_channel_id)
            if not channel:
                await interaction.response.send_message("Kanal nicht gefunden.", ephemeral=True)
                return
            await interaction.response.send_message(
                f"🔗 **Modul: {selected_item.label}**\nZum Kanal: {channel.mention}",
                ephemeral=True
            )
        
        # Handle custom 'URL' items.
        elif selected_item.type == ModuleNavigatorMenuItemLinkType.URL:
            await interaction.response.send_message(f"🔗 **{selected_item.label}**\n{selected_item.value}", ephemeral=True)
        
        # Handle custom 'Channel' items.
        elif selected_item.type == ModuleNavigatorMenuItemLinkType.CHANNEL:
            try:
                channel = interaction.guild.get_channel(int(selected_item.value))
                if not channel:
                    await interaction.response.send_message("Kanal nicht gefunden.", ephemeral=True)
                    return
                await interaction.response.send_message(f"🔗 **{selected_item.label}**\nZum Kanal: {channel.mention}", ephemeral=True)
            except (ValueError, TypeError):
                await interaction.response.send_message("Ungültige Kanal-ID konfiguriert.", ephemeral=True)

        # Handle custom 'Post' items, which can be a URL or 'channel/message' ID string.
        elif selected_item.type == ModuleNavigatorMenuItemLinkType.POST:
            channel_id = None
            message_id = None

            # Try to parse a full Discord message URL (e.g., https://discord.com/channels/guild/channel/message)
            match = re.search(r"channels/\d+/(\d+)/(\d+)", selected_item.value)
            if match:
                channel_id, message_id = match.groups()
            else:
                # Fallback to the 'channel_id/message_id' format
                try:
                    channel_id, message_id = selected_item.value.split('/')
                except ValueError:
                    pass  # Value is not in a recognized format

            if not channel_id or not message_id:
                await interaction.response.send_message(
                    "Ungültige Post-ID oder URL konfiguriert. Erwartet wird entweder ein Link zur Nachricht oder 'channel_id/message_id'.",
                    ephemeral=True)
                return

            try:
                channel = interaction.guild.get_channel(int(channel_id))
                if not channel:
                    channel = await interaction.guild.fetch_channel(int(channel_id))

                message = await channel.fetch_message(int(message_id))
                await interaction.response.send_message(f"🔗 **{selected_item.label}**\n{message.jump_url}", ephemeral=True)
            except (ValueError, TypeError):
                await interaction.response.send_message("Ungültige Post-ID oder URL konfiguriert.", ephemeral=True)
            except discord.NotFound:
                await interaction.response.send_message("Kanal oder Nachricht nicht gefunden.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("Ich habe keine Berechtigung, auf diesen Kanal oder diese Nachricht zuzugreifen.", ephemeral=True)
            except Exception:
                await interaction.response.send_message("Ein unerwarteter Fehler ist aufgetreten.", ephemeral=True)


class ModuleNavigatorMenuNextButton(discord.ui.Button):
    """The 'Next Page' button for the navigator."""

    def __init__(self, menu_key: str):
        self.menu_key = menu_key
        super().__init__(label="➡️",
                         style=discord.ButtonStyle.primary,
                         custom_id=f"persistent_view:{self.menu_key}:module_next")

    async def callback(self, interaction: discord.Interaction):
        """
        When clicked, this button re-creates the main view with the page number incremented.
        """
        await interaction.response.defer()  # Defer response as we are editing the original message.
        
        view: ModuleNavigatorView = self.view
        if not hasattr(view, 'modules') or not view.modules:
            await interaction.followup.send("Menü abgelaufen (Bot Neustart). Bitte lade das Menü mit dem /add Befehl neu.", ephemeral=True)
            return

        current_page = ModuleNavigatorView.get_page_from_message(interaction.message)
        next_page = current_page + 1

        # Edit the original message with a new view object for the next page.
        await interaction.message.edit(
            view=ModuleNavigatorView(view.title, view.modules, self.menu_key, next_page)
        )


class ModuleNavigatorMenuPreviousButton(discord.ui.Button):
    """The 'Previous Page' button for the navigator."""

    def __init__(self, menu_key: str):
        self.menu_key = menu_key
        super().__init__(
            label="⬅️",
            style=discord.ButtonStyle.primary,
            custom_id=f"persistent_view:{self.menu_key}:module_prev"
        )

    async def callback(self, interaction: discord.Interaction):
        """
        When clicked, this button re-creates the main view with the page number decremented.
        """
        await interaction.response.defer()
        
        view: ModuleNavigatorView = self.view
        if not hasattr(view, 'modules') or not view.modules:
            await interaction.followup.send("Menü abgelaufen (Bot Neustart). Bitte lade das Menü mit dem /add Befehl neu.", ephemeral=True)
            return

        current_page = ModuleNavigatorView.get_page_from_message(interaction.message)
        prev_page = max(current_page - 1, 0) # Ensure page number doesn't go below 0.

        await interaction.message.edit(
            view=ModuleNavigatorView(view.title, view.modules, self.menu_key, prev_page)
        )

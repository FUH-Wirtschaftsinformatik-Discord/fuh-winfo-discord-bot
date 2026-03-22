import logging
from dataclasses import dataclass

from discord import app_commands, Interaction
import discord
from discord.ext import commands, tasks

from models import ModuleNavigatorCustomMenuItem, ModuleNavigatorMenuItemLinkType, ModuleNavigatorMenuConfig, ModuleNavigatorModuleItem
from views.module_navigator_view import ModuleNavigatorView
from . import db
from . import helpers

# Pre-defined choices for the 'menu_type' command option to reduce code duplication.
MENU_TYPE_CHOICES = [
    app_commands.Choice(
        name="📚 Pflichtmodule Bereich Wirtschaftsinformatik", value="pflicht-winfo"),
    app_commands.Choice(
        name="💻 Pflichtmodule Bereich Informatik", value="pflicht-info"),
    app_commands.Choice(
        name="📊 Pflichtmodule Bereich Wirtschaftswissenschaften", value="pflicht-wiwi"),
    app_commands.Choice(
        name="📐 Pflichtmodule Bereich Mathematik", value="pflicht-mathe"),
    app_commands.Choice(
        name="📚 Wahlpflichtmodule Bereich Wirtschaftsinformatik", value="wahl-winfo"),
    app_commands.Choice(
        name="💻 Wahlpflichtmodule Bereich Informatik", value="wahl-info"),
    app_commands.Choice(
        name="📊 Wahlpflichtmodule Bereich Wirtschaftswissenschaften", value="wahl-wiwi"),
]


@dataclass(frozen=True, eq=True)
class MenuKey:
    """A type-safe, hashable key for identifying a menu."""
    guild_id: int
    channel_id: int
    menu_type: str


@app_commands.guild_only()
class ModuleNavigator(commands.GroupCog, name="module-navigator",
                      description="Erstellt und verwaltet Menüs, um Module in Discord-Kanälen zu navigieren."):
    """
    This cog manages the module navigation menus. It includes commands to create
    and customize the menus, and a background task to keep them updated.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        # A runtime cache for menu content hashes to avoid unnecessary updates.
        self.menu_hashes: dict[MenuKey, str] = {}

        # Load all existing menu configurations from the database on startup.
        self.menus: dict[MenuKey, ModuleNavigatorMenuConfig] = {
            MenuKey(cfg.guild_id, cfg.channel_id, cfg.menu_type): cfg
            for cfg in db.load_menu_config()
        }

        # Start the background task to periodically update the menus.
        self.update.start()

    @app_commands.command(name="add-custom-item", description="Fügt einen benutzerdefinierten Eintrag zu einem Menü hinzu.")
    @app_commands.choices(menu_type=MENU_TYPE_CHOICES)
    @app_commands.choices(link_type=[
        app_commands.Choice(
            name="URL", value=ModuleNavigatorMenuItemLinkType.URL.value),
        app_commands.Choice(
            name="Channel", value=ModuleNavigatorMenuItemLinkType.CHANNEL.value),
        app_commands.Choice(
            name="Post", value=ModuleNavigatorMenuItemLinkType.POST.value),
    ])
    async def cmd_add_custom_item(self, interaction: Interaction, menu_type: app_commands.Choice[str], label: str,
                                  link_type: app_commands.Choice[str], value: str):
        """
        Slash command to add a custom, non-module link to a navigation menu.
        This allows for adding links to important resources, channels, or specific posts.
        """
        ModuleNavigatorCustomMenuItem.create(
            guild_id=interaction.guild.id,
            menu_channel_id=interaction.channel.id,
            menu_type=menu_type.value,
            label=label,
            link_type=link_type.value,
            value=value
        )

        # Trigger an immediate update for all menus of this type in the current channel.
        key_to_update = MenuKey(interaction.guild.id,
                                interaction.channel.id, menu_type.value)
        if key_to_update in self.menus:
            await self._update_menu(self.menus[key_to_update])

        await interaction.response.send_message("Benutzerdefinierter Eintrag hinzugefügt!", ephemeral=True)

    @app_commands.command(name="add", description="Erstellt ein neues Modulnavigationsmenü in diesem Kanal.")
    @app_commands.choices(menu_type=MENU_TYPE_CHOICES)
    async def cmd_setup_menu(self, interaction: Interaction, menu_type: app_commands.Choice[str]):
        """
        Slash command to create a new module navigation menu in the current channel.
        It scans the guild's categories, generates the menu content, and posts it.
        """
        parent_category_name = helpers.get_parent_category_name(
            menu_type.value)
        if not parent_category_name:
            return await interaction.response.send_message("Ungültiger Menü-Typ.", ephemeral=True)

        menu_items: list[ModuleNavigatorModuleItem | ModuleNavigatorCustomMenuItem] = helpers.get_module_categories(
            interaction.guild.categories,
            helpers.convert_to_clean_string(parent_category_name)
        )

        custom_items = db.fetch_custom_menu_items_from_db(
            interaction.guild.id, interaction.channel.id, menu_type.value)
        menu_items.extend(custom_items)

        if not menu_items:
            return await interaction.response.send_message("Keine passenden Modul-Kanäle für dieses Menü gefunden.", ephemeral=True)

        for item in menu_items:
            if isinstance(item, ModuleNavigatorModuleItem):
                item.guild_id = interaction.guild.id
                item.menu_channel_id = interaction.channel.id
                item.menu_type = menu_type.value

        # If a menu of this type already exists in this channel, delete the old one first.
        key_to_delete = MenuKey(interaction.guild.id,
                                interaction.channel.id, menu_type.value)
        if key_to_delete in self.menus:
            existing_config = self.menus[key_to_delete]
            try:
                msg = await interaction.channel.fetch_message(existing_config.message_id)
                await msg.delete()
                db.delete_menu_config(
                    key_to_delete.guild_id, key_to_delete.channel_id, key_to_delete.menu_type)
                db.delete_module_items(
                    key_to_delete.guild_id, key_to_delete.channel_id, key_to_delete.menu_type)
            except discord.NotFound:
                self.logger.warning(
                    f"Could not find old menu message {existing_config.message_id} to delete. It might have been deleted manually.")
            except discord.HTTPException as e:
                self.logger.error(
                    f"Failed to delete old menu message {existing_config.message_id}: {e}")

        # Post the new menu message with the view.
        menu_key_str = f"{interaction.guild.id}:{interaction.channel.id}:{menu_type.value}"
        view = ModuleNavigatorView(
            parent_category_name, menu_items, menu_key_str, page=0)
        msg_content = f"Kategorie: 📚 **{parent_category_name}**\nWähle ein Modul:"
        message = await interaction.channel.send(content=msg_content, view=view)

        # --- Update State & Persist ---
        new_key = MenuKey(interaction.guild.id,
                          interaction.channel.id, menu_type.value)

        db.save_menu_config(new_key.menu_type, new_key.guild_id,
                            new_key.channel_id, message.id)
        self.menu_hashes[new_key] = helpers.generate_data_hash(menu_items)
        self.menus[new_key] = ModuleNavigatorMenuConfig(
            guild_id=new_key.guild_id, channel_id=new_key.channel_id, message_id=message.id,
            menu_type=new_key.menu_type)

        await interaction.response.send_message("Menü erstellt!", ephemeral=True)

    @app_commands.command(name="remove-custom-item", description="Entfernt einen benutzerdefinierten Eintrag aus einem Menü.")
    @app_commands.choices(menu_type=MENU_TYPE_CHOICES)
    async def cmd_remove_custom_item(self, interaction: Interaction, menu_type: app_commands.Choice[str], label: str):
        """
        Slash command to remove a custom item from a menu, identified by its label.
        """
        deleted_count = ModuleNavigatorCustomMenuItem.delete().where(
            (ModuleNavigatorCustomMenuItem.guild_id == interaction.guild.id) &
            (ModuleNavigatorCustomMenuItem.menu_channel_id == interaction.channel.id) &
            (ModuleNavigatorCustomMenuItem.menu_type == menu_type.value) &
            (ModuleNavigatorCustomMenuItem.label == label)
        ).execute()

        if deleted_count == 0:
            return await interaction.response.send_message("Benutzerdefinierter Eintrag mit diesem Label nicht gefunden.", ephemeral=True)

        key_to_update = MenuKey(interaction.guild.id,
                                interaction.channel.id, menu_type.value)
        if key_to_update in self.menus:
            await self._update_menu(self.menus[key_to_update])

        await interaction.response.send_message("Benutzerdefinierter Eintrag entfernt!", ephemeral=True)

    @tasks.loop(minutes=5)
    async def update(self):
        """A background task that runs every 5 minutes to keep menus in sync."""
        for menu_config in list(self.menus.values()):
            await self._update_menu(menu_config)

    async def _update_menu(self, menu_config: ModuleNavigatorMenuConfig):
        """
        The core logic for updating a single menu. It re-scans the channels,
        compares the content hash, and edits the message if changes are detected.
        """
        guild = self.bot.get_guild(menu_config.guild_id)
        menu_key = MenuKey(menu_config.guild_id,
                           menu_config.channel_id, menu_config.menu_type)
        if not guild:
            self.logger.warning(
                f"Guild {menu_config.guild_id} not found for menu {menu_key}, skipping update.")
            return


        title = helpers.get_parent_category_name(menu_config.menu_type)
        live_data: list[ModuleNavigatorModuleItem | ModuleNavigatorCustomMenuItem] = helpers.get_module_categories(
            guild.categories, helpers.convert_to_clean_string(title))

        custom_items = db.fetch_custom_menu_items_from_db(
            menu_config.guild_id, menu_config.channel_id, menu_config.menu_type)
        live_data.extend(custom_items)

        new_hash = helpers.generate_data_hash(live_data)

        module_items = [item for item in live_data if isinstance(
            item, ModuleNavigatorModuleItem)]
        for item in module_items:
            item.guild_id = menu_config.guild_id
            item.menu_channel_id = menu_config.channel_id
            item.menu_type = menu_config.menu_type
        db.save_modules_to_db(
            menu_config.guild_id, menu_config.channel_id, menu_config.menu_type, module_items)

        if self.menu_hashes.get(menu_key) == new_hash:
            return

        self.logger.info(f"Menu {menu_key} has changed, updating message...")
        try:
            channel = self.bot.get_channel(menu_config.channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(menu_config.channel_id)

            message = await channel.fetch_message(menu_config.message_id)
            menu_key_str = f"{menu_config.guild_id}:{menu_config.channel_id}:{menu_config.menu_type}"
            view = ModuleNavigatorView(
                title=title, modules=live_data, menu_key=menu_key_str, page=0)
            await message.edit(view=view)

            self.menu_hashes[menu_key] = new_hash
        except discord.NotFound:
            self.logger.warning(
                f"Channel {menu_config.channel_id} or Message {menu_config.message_id} for menu {menu_key} not found. Skipping update.")
        except discord.HTTPException as e:
            self.logger.error(f"Failed to update menu {menu_key}: {e}")

    @update.before_loop
    async def before_updater(self):
        """Waits for the bot to be ready before starting the update loop."""
        await self.bot.wait_until_ready()

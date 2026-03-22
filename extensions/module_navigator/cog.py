import logging
from typing import List

from discord import app_commands, Interaction
import discord
from discord.ext import commands, tasks

from models import ModuleNavigatorCustomMenuItem, ModuleNavigatorMenuItemLinkType, ModuleNavigatorMenuConfig, ModuleNavigatorModuleItem
from views.module_navigator_view import ModuleNavigatorView
from . import db
from . import helpers

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


@app_commands.guild_only()
class ModuleNavigator(commands.GroupCog, name="module-navigator",
                      description="Erstellt und verwaltet Menüs, um Module in Discord-Kanälen zu navigieren."):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.menu_hashes = {}
        self.menus = {(cfg.guild_id, cfg.channel_id, cfg.menu_type)
                       : cfg for cfg in db.load_menu_config()}
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
        ModuleNavigatorCustomMenuItem.create(
            guild_id=interaction.guild.id,
            menu_channel_id=interaction.channel.id,
            menu_type=menu_type.value,
            label=label,
            link_type=link_type.value,
            value=value
        )

        for menu_key, menu_config in self.menus.items():
            if menu_key[0] == interaction.guild.id and menu_key[1] == interaction.channel.id and menu_key[
                    2] == menu_type.value:
                await self._update_menu(menu_key, menu_config)

        await interaction.response.send_message("Benutzerdefinierter Eintrag hinzugefügt!", ephemeral=True)

    @app_commands.command(name="add", description="Erstellt ein neues Modulnavigationsmenü in diesem Kanal.")
    @app_commands.choices(menu_type=MENU_TYPE_CHOICES)
    async def cmd_setup_menu(self, interaction: Interaction, menu_type: app_commands.Choice[str]):
        parent_category_name = helpers.get_parent_category_name(
            menu_type.value)
        if not parent_category_name:
            return await interaction.response.send_message("Ungültiger Typ.", ephemeral=True)

        menu_items: list[ModuleNavigatorModuleItem | ModuleNavigatorCustomMenuItem] = helpers.get_module_categories(
            interaction.guild.categories,
            helpers.convert_to_clean_string(parent_category_name)
        )

        custom_items = db.fetch_custom_menu_items_from_db(
            interaction.guild.id, interaction.channel.id, menu_type.value)
        menu_items.extend(custom_items)

        if not menu_items:
            return await interaction.response.send_message("Keine Kategorien gefunden.", ephemeral=True)

        for item in menu_items:
            if isinstance(item, ModuleNavigatorModuleItem):
                item.guild_id = interaction.guild.id
                item.menu_channel_id = interaction.channel.id
                item.menu_type = menu_type.value

        # Cleanup existing menu of this type in this channel
        for k, existing in self.menus.items():
            if k[0] == interaction.guild.id and k[1] == interaction.channel.id and k[2] == menu_type.value:
                try:
                    msg = await interaction.channel.fetch_message(existing.message_id)
                    await msg.delete()
                    db.delete_menu_config(k[0], k[1], k[2])
                    db.delete_module_items(k[0], k[1], k[2])
                except discord.NotFound:
                    self.logger.warning(
                        f"Could not find message for menu {k} to delete. It might have been deleted manually.")
                except discord.HTTPException as e:
                    self.logger.error(
                        f"Failed to delete old menu message for {k}: {e}")

        # Send New Menu
        menu_key_str = f"{interaction.guild.id}:{interaction.channel.id}:{menu_type.value}"
        view = ModuleNavigatorView(
            parent_category_name, menu_items, menu_key_str, page=0)
        msg_content = f"📚 **{parent_category_name}**\nWähle ein Modul:"
        message = await interaction.channel.send(content=msg_content, view=view)

        menu_key = (interaction.guild.id,
                    interaction.channel.id, menu_type.value)

        # Update State & Persist
        self.menu_hashes[menu_key] = helpers.generate_data_hash(menu_items)
        db.save_menu_config(menu_type.value, interaction.guild.id,
                            interaction.channel.id, message.id)

        # Refresh local cache
        self.menus[menu_key] = ModuleNavigatorMenuConfig(
            guild_id=interaction.guild.id, channel_id=interaction.channel.id, message_id=message.id,
            menu_type=menu_type.value)

        await interaction.response.send_message("Menü erstellt!", ephemeral=True)

    @app_commands.command(name="remove-custom-item", description="Entfernt einen benutzerdefinierten Eintrag aus einem Menü.")
    @app_commands.choices(menu_type=MENU_TYPE_CHOICES)
    async def cmd_remove_custom_item(self, interaction: Interaction, menu_type: app_commands.Choice[str], label: str):
        deleted_count = ModuleNavigatorCustomMenuItem.delete().where(
            (ModuleNavigatorCustomMenuItem.guild_id == interaction.guild.id) &
            (ModuleNavigatorCustomMenuItem.menu_channel_id == interaction.channel.id) &
            (ModuleNavigatorCustomMenuItem.menu_type == menu_type.value) &
            (ModuleNavigatorCustomMenuItem.label == label)
        ).execute()

        if deleted_count == 0:
            return await interaction.response.send_message("Benutzerdefinierter Eintrag nicht gefunden.", ephemeral=True)

        for menu_key, menu_config in self.menus.items():
            if menu_key[0] == interaction.guild.id and menu_key[1] == interaction.channel.id and menu_key[
                    2] == menu_type.value:
                await self._update_menu(menu_key, menu_config)

        await interaction.response.send_message("Benutzerdefinierter Eintrag entfernt!", ephemeral=True)

    @tasks.loop(minutes=5)
    async def update(self):
        for menu_key, menu_config in self.menus.items():
            await self._update_menu(menu_key, menu_config)

    async def _update_menu(self, menu_key, menu_config):
        guild_id, menu_channel_id, menu_type = menu_key
        guild = self.bot.get_guild(menu_config.guild_id)
        if not guild:
            return

        title = helpers.get_parent_category_name(menu_type)
        live_data: list[ModuleNavigatorModuleItem | ModuleNavigatorCustomMenuItem] = helpers.get_module_categories(
            guild.categories, helpers.convert_to_clean_string(title))

        custom_items = db.fetch_custom_menu_items_from_db(
            guild_id, menu_channel_id, menu_type)
        live_data.extend(custom_items)

        for item in live_data:
            if isinstance(item, ModuleNavigatorModuleItem):
                item.guild_id = guild_id
                item.menu_channel_id = menu_channel_id
                item.menu_type = menu_type

        new_hash = helpers.generate_data_hash(live_data)

        module_items = [
            item for item in live_data if isinstance(item, ModuleNavigatorModuleItem)]
        db.save_modules_to_db(
            guild_id, menu_channel_id, menu_type, module_items)

        if self.menu_hashes.get(menu_key) == new_hash:
            return

        try:
            channel = self.bot.get_channel(menu_config.channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(menu_config.channel_id)
                except discord.NotFound:
                    self.logger.warning(
                        f"Channel {menu_config.channel_id} for menu {menu_type} not found. Skipping...")
                    return

            message = await channel.fetch_message(menu_config.message_id)
            menu_key_str = f"{guild_id}:{menu_channel_id}:{menu_type}"
            view = ModuleNavigatorView(
                title=title, modules=live_data, menu_key=menu_key_str, page=0)
            await message.edit(view=view)
            self.menu_hashes[menu_key] = new_hash
        except discord.NotFound:
            self.logger.warning(
                f"Message {menu_config.message_id} for menu {menu_type} not found. Skipping...")
        except discord.HTTPException as e:
            self.logger.error(f"Failed to update menu {menu_type}: {e}")

    @update.before_loop
    async def before_updater(self):
        await self.bot.wait_until_ready()

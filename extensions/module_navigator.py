import logging
import re
from typing import List

from discord import CategoryChannel, app_commands, Interaction
import discord
from discord.ext import commands

from models import CustomMenuItem, ItemType, MenuConfig, ModuleItem, ModuleMenuType
from views.module_navigator_view import ModuleNavigatorView

import hashlib
import json
from discord.ext import tasks
from playhouse.shortcuts import model_to_dict


def get_parent_category_name(menu_type: str) -> str | None:

    try:
        menu_type = ModuleMenuType(menu_type)

        if menu_type == ModuleMenuType.PFLICHT_WIWI:
            return "Pflichtmodule Wirtschaftswissenschaften"
        elif menu_type == ModuleMenuType.PFLICHT_INFO:
            return "Pflichtmodule Informatik"
        elif menu_type == ModuleMenuType.PFLICHT_WINFO:
            return "Pflichtmodule Wirtschaftsinformatik"
        elif menu_type == ModuleMenuType.PFLICHT_MATHE:
            return "Pflichtmodule Mathematik"
        elif menu_type == ModuleMenuType.WAHL_WIWI:
            return "Wahlpflichtmodule Wirtschaftswissenschaften"
        elif menu_type == ModuleMenuType.WAHL_INFO:
            return "Wahlpflichtmodule Informatik"
        elif menu_type == ModuleMenuType.WAHL_WINFO:
            return "Wahlpflichtmodule Wirtschaftsinformatik"

        return None
    except:
        return None


def generate_data_hash(modules_list: list[ModuleItem | CustomMenuItem]):
    """Converts the modules list into a unique hash string."""
    dict_list = []
    for item in modules_list:
        d = model_to_dict(item)
        d.pop('id', None)  # ensure hash ignores DB primary keys
        dict_list.append(d)
    data_string = json.dumps(dict_list, sort_keys=True)
    return hashlib.md5(data_string.encode()).hexdigest()


def convert_to_clean_string(input_str: str):
    return input_str.lower().strip()


def fetch_modules_from_db() -> list[ModuleItem]:
    """Loads modules as a flattened list."""
    return list(ModuleItem.select())


def fetch_custom_menu_items_from_db(guild_id: int, menu_channel_id: int, menu_type: str) -> list[CustomMenuItem]:
    """Loads custom menu items as a flattened list."""
    return list(CustomMenuItem.select().where(
        (CustomMenuItem.guild_id == guild_id) &
        (CustomMenuItem.menu_channel_id == menu_channel_id) &
        (CustomMenuItem.menu_type == menu_type)
    ))


def load_menu_config() -> list[MenuConfig]:
    """Loads menu configurations as a flattened list."""
    return list(MenuConfig.select())


def save_menu_config(menu_type: str, guild_id: int, menu_channel_id: int, message_id: int):
    """Updates a specific config in the flattened list and saves."""
    MenuConfig.delete().where(
        (MenuConfig.menu_type == menu_type) &
        (MenuConfig.id == menu_channel_id) &
        (MenuConfig.guild_id == guild_id)
    ).execute()
    MenuConfig.create(guild_id=guild_id, id=menu_channel_id,
                      message_id=message_id, menu_type=menu_type)


@app_commands.guild_only()
class ModuleNavigator(commands.GroupCog, name="module-navigator",
                      description="Erstellt und verwaltet Menüs, um Module in Discord-Kanälen zu navigieren."):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.menu_hashes = {}

        # We still keep a runtime dict for O(1) access during the loop.
        self.menus = {(cfg.guild_id, cfg.id, cfg.menu_type)                      : cfg for cfg in load_menu_config()}
        self.update.start()

    def save_modules_to_db_by_key(self, guild_id: int, menu_channel_id: int, menu_type: str, new_modules: list[ModuleItem]):
        """Helper to update subset of modules in the flat list."""
        with ModuleItem._meta.database.atomic():
            ModuleItem.delete().where(
                (ModuleItem.guild_id == guild_id) &
                (ModuleItem.menu_channel_id == menu_channel_id) &
                (ModuleItem.menu_type == menu_type)
            ).execute()
            ModuleItem.bulk_create(new_modules)

    @app_commands.command(name="add-custom-item", description="Fügt einen benutzerdefinierten Eintrag zu einem Menü hinzu.")
    @app_commands.choices(menu_type=[
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
    ])
    @app_commands.choices(item_type=[
        app_commands.Choice(name="URL", value=ItemType.URL.value),
        app_commands.Choice(name="Channel", value=ItemType.CHANNEL.value),
        app_commands.Choice(name="Post", value=ItemType.POST.value),
    ])
    async def cmd_add_custom_item(self, interaction: Interaction, menu_type: app_commands.Choice[str], label: str, item_type: app_commands.Choice[str], value: str):
        CustomMenuItem.create(
            guild_id=interaction.guild.id,
            menu_channel_id=interaction.channel.id,
            menu_type=menu_type.value,
            label=label,
            item_type=item_type.value,
            value=value
        )
        await interaction.response.send_message("Benutzerdefinierter Eintrag hinzugefügt!", ephemeral=True)

    @app_commands.command(name="add", description="Erstellt ein neues Modulnavigationsmenü in diesem Kanal.")
    @app_commands.choices(menu_type=[
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
    ])
    async def cmd_setup_menu(self, interaction: Interaction, menu_type: app_commands.Choice[str]):
        parent_category_name = get_parent_category_name(menu_type.value)
        if not parent_category_name:
            return await interaction.response.send_message("Ungültiger Typ.", ephemeral=True)

        menu_items: list[ModuleItem | CustomMenuItem] = self.get_module_categories(
            interaction.guild.categories,
            convert_to_clean_string(parent_category_name)
        )

        custom_items = fetch_custom_menu_items_from_db(
            interaction.guild.id, interaction.channel.id, menu_type.value)
        menu_items.extend(custom_items)

        if not menu_items:
            return await interaction.response.send_message("Keine Kategorien gefunden.", ephemeral=True)

        for item in menu_items:
            if isinstance(item, ModuleItem):
                item.guild_id = interaction.guild.id
                item.menu_channel_id = interaction.channel.id
                item.menu_type = menu_type.value

        # Cleanup existing menu of this type in this channel
        for k, existing in self.menus.items():
            if k[0] == interaction.guild.id and k[1] == interaction.channel.id and k[2] == menu_type.value:
                try:
                    msg = await interaction.channel.fetch_message(existing.message_id)
                    await msg.delete()

                    MenuConfig.delete().where((MenuConfig.guild_id == k[0]) & (
                        MenuConfig.id == k[1]) & (MenuConfig.menu_type == k[2])).execute()
                    ModuleItem.delete().where((ModuleItem.guild_id == k[0]) & (
                        ModuleItem.menu_channel_id == k[1]) & (ModuleItem.menu_type == k[2])).execute()
                except Exception:
                    pass

        # Send New Menu
        menu_key_str = f"{interaction.guild.id}:{interaction.channel.id}:{menu_type.value}"
        view = ModuleNavigatorView(parent_category_name,
                                   menu_items, menu_key_str, page=0)
        msg_content = f"📚 **{parent_category_name}**\nWähle ein Modul:"
        message = await interaction.channel.send(content=msg_content, view=view)

        menu_key = (interaction.guild.id,
                    interaction.channel.id, menu_type.value)
        # Update State & Persist
        self.menu_hashes[menu_key] = generate_data_hash(menu_items)
        save_menu_config(menu_type.value, interaction.guild.id,
                         interaction.channel.id, message.id)

        # Refresh local cache
        self.menus[menu_key] = MenuConfig(
            guild_id=interaction.guild.id, menu_channel_id=interaction.channel.id, message_id=message.id, menu_type=menu_type.value)

        await interaction.response.send_message("Menü erstellt!", ephemeral=True)

    @tasks.loop(minutes=5)
    async def update(self):
        for menu_key, menu_config in self.menus.items():
            guild_id, menu_channel_id, menu_type = menu_key
            guild = self.bot.get_guild(menu_config.guild_id)
            if not guild:
                continue

            title = get_parent_category_name(menu_type)
            live_data: list[ModuleItem | CustomMenuItem] = self.get_module_categories(
                guild.categories, convert_to_clean_string(title))

            custom_items = fetch_custom_menu_items_from_db(
                guild_id, menu_channel_id, menu_type)
            live_data.extend(custom_items)

            for item in live_data:
                if isinstance(item, ModuleItem):
                    item.guild_id = guild_id
                    item.menu_channel_id = menu_channel_id
                    item.menu_type = menu_type

            new_hash = generate_data_hash(live_data)

            module_items = [
                item for item in live_data if isinstance(item, ModuleItem)]
            self.save_modules_to_db_by_key(
                guild_id, menu_channel_id, menu_type, module_items)

            if self.menu_hashes.get(menu_key) == new_hash:
                continue

            try:
                channel = self.bot.get_channel(menu_config.id)
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(menu_config.id)
                    except discord.NotFound:
                        self.logger.warning(
                            f"Kanal {menu_config.id} für Menü {menu_type} nicht gefunden. Überspringe...")
                        continue

                message = await channel.fetch_message(menu_config.message_id)
                menu_key_str = f"{guild_id}:{menu_channel_id}:{menu_type}"
                view = ModuleNavigatorView(
                    title=title, modules=live_data, menu_key=menu_key_str, page=0)
                await message.edit(view=view)
                self.menu_hashes[menu_key] = new_hash
            except Exception as e:
                self.logger.error(f"Loop error for {menu_type}: {e}")

    @update.before_loop
    async def before_updater(self):
        await self.bot.wait_until_ready()

    def get_module_categories(self, all_categories: List[CategoryChannel],
                              parent_category: str,
                              default_channel: str = "diskussion-und-infos") -> list[ModuleItem]:
        # First filter categories to those that are under the specified parent category
        all_module_categories = self.get_module_categories_of_parent_category(
            all_categories, parent_category)
        public_categories = self.filter_public_categories_and_channels(
            all_module_categories)

        menu_items: list[ModuleItem] = []

        for category in public_categories:
            # Extract the module number from the category name, if it exists
            module_number = ""
            has_module_number = re.search(r'\d+', category.name)
            if has_module_number and has_module_number.group():
                module_number = has_module_number.group(0).strip()

            # Remove the module number and any non-ASCII characters to get a cleaner module name
            module_name = "".join(char for char in category.name.replace(
                module_number, "") if char.isascii()).strip()

            # Skip categories that don't have any channels, as they likely aren't actual modules
            if len(category.channels) == 0:
                continue

            # Try to find a channel in this category, or fallback to the first public channel if it doesn't exist
            channel = self.get_channel_or_first_public_of_category(
                category, default_channel)
            if channel is None:
                continue

            module_item = ModuleItem(
                module_channel_id=channel.id, description=module_name, module_number=module_number)
            menu_items.append(module_item)

        return menu_items

    def get_channel_or_first_public_of_category(self, category: discord.CategoryChannel, target_name: str) -> discord.TextChannel:
        """
        Finds a public channel named like in parameter 'target_name' in a category. 
        Returns the first public channel if the target name is not found, or None if no public channels exist.
        """
        # The default role represents the @everyone role
        everyone_role = category.guild.default_role
        # This variable will hold the first public channel we find, in case we don't find one named like the target name.
        fallback_channel = None

        # Iterate through text channels in this category.
        # (Change to category.channels if you also want voice/stage channels)
        for channel in category.text_channels:

            # Check if the @everyone role is allowed to view this channel
            if channel.permissions_for(everyone_role).view_channel:

                # Save the very first public channel we find as our fallback
                if fallback_channel is None:
                    fallback_channel = channel

                # If we find the exact match, we can stop searching and return it immediately
                if channel.name == target_name:
                    return channel

        return fallback_channel

    def get_module_categories_of_parent_category(self,
                                                 categories: list[discord.CategoryChannel],
                                                 parent_category: str) -> list[discord.CategoryChannel]:

        if not categories:
            return []

        if not parent_category:
            return categories

        start_index = -1
        end_index = -1

        for i in range(len(categories)):
            category = categories[i]

            category_name = category.name.lower().strip()

            if start_index > -1:
                starts_as_number = not re.match(r'^\d', category_name)
                if starts_as_number:
                    end_index = i
                    break

            if start_index == -1 and parent_category in category_name:
                start_index = i
                continue

        test_channels = categories

        if start_index != -1 and start_index + 1 < len(categories):
            start_index += 1

        if start_index == -1 and end_index == -1:
            return []
        elif start_index == -1:
            test_channels = categories[:end_index]
            return test_channels
        elif end_index == -1:
            test_channels = categories[start_index:]
            return test_channels

        return categories[start_index:end_index]

    def filter_public_categories_and_channels(self, categories: list[discord.CategoryChannel]) -> list[discord.CategoryChannel]:
        """
        Filters a list of categories to return only those that are public
        and contain at least one public text channel.
        """
        public_categories = []
        for category in categories:
            everyone_role = category.guild.default_role
            if category.permissions_for(everyone_role).view_channel:
                has_public_channel = any(
                    channel.permissions_for(everyone_role).view_channel
                    for channel in category.text_channels
                )
                if has_public_channel:
                    public_categories.append(category)
        return public_categories


async def setup(bot: commands.Bot) -> None:
    cog = ModuleNavigator(bot)

    # 1. Load flattened data
    all_modules = fetch_modules_from_db()

    # 2. Group modules by type for view registration
    from collections import defaultdict
    grouped = defaultdict(list)
    for m in all_modules:
        grouped[(m.guild_id, m.menu_channel_id, m.menu_type)].append(m)

    # 3. Register persistent views
    for (g_id, c_id, m_type), m_list in grouped.items():
        title = get_parent_category_name(m_type) or "Modulübersicht"
        menu_key_str = f"{g_id}:{c_id}:{m_type}"
        bot.add_view(ModuleNavigatorView(title=title, modules=m_list,
                     menu_key=menu_key_str, page=0))

    await bot.add_cog(cog)

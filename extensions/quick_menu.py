import logging
import re
from typing import List

from discord import CategoryChannel, app_commands, Interaction
import discord
from discord.ext import commands

from models import MenuConfig, ModuleItem, ModuleMenuType
from views.quick_menu_view import QuickMenuView

import hashlib
import json
from discord.ext import tasks
from playhouse.shortcuts import model_to_dict


# --- UTILS ---

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


def generate_data_hash(modules_list: list[ModuleItem]):
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

# --- MODULE PERSISTENCE (FLATTENED) ---


def fetch_modules_from_db() -> list[ModuleItem]:
    """Loads modules as a flattened list."""
    return list(ModuleItem.select())

# --- CONFIG PERSISTENCE (FLATTENED) ---


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


# --- COG ---

@app_commands.guild_only()
class QuickMenu(commands.GroupCog, name="quickmenu", description="Quick Navigation Menus"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.menu_hashes = {}

        # We still keep a runtime dict for O(1) access during the loop.
        self.menus = {(cfg.guild_id, cfg.id, cfg.menu_type)                      : cfg for cfg in load_menu_config()}
        self.menu_updater_loop.start()

    def save_modules_to_db_by_key(self, guild_id: int, menu_channel_id: int, menu_type: str, new_modules: list[ModuleItem]):
        """Helper to update subset of modules in the flat list."""
        with ModuleItem._meta.database.atomic():
            ModuleItem.delete().where(
                (ModuleItem.guild_id == guild_id) &
                (ModuleItem.menu_channel_id == menu_channel_id) &
                (ModuleItem.menu_type == menu_type)
            ).execute()
            ModuleItem.bulk_create(new_modules)

    @app_commands.command(name="setup-menu", description="Erstellt ein Modul-Menü.")
    @app_commands.choices(menu_type=[
        app_commands.Choice(
            name="📚 Pflichtmodule Wirtschaftsinformatik", value="pflicht-wiwi"),
        app_commands.Choice(
            name="💻 Pflichtmodule Informatik", value="pflicht-info")
    ])
    async def cmd_setup_menu(self, interaction: Interaction, menu_type: app_commands.Choice[str]):
        await interaction.response.defer()

        parent_category_name = get_parent_category_name(menu_type.value)
        if not parent_category_name:
            return await interaction.followup.send("Ungültiger Typ.", ephemeral=True)

        menu_items = self.get_module_categories(
            interaction.guild.categories,
            convert_to_clean_string(parent_category_name)
        )

        if not menu_items:
            return await interaction.followup.send("Keine Kategorien gefunden.", ephemeral=True)

        for item in menu_items:
            item.guild_id = interaction.guild.id
            item.menu_channel_id = interaction.channel.id
            item.menu_type = menu_type.value

        # Cleanup all existing menus in this channel
        for k, existing in self.menus.items():
            if k[0] == interaction.guild.id and k[1] == interaction.channel.id:
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
        view = QuickMenuView(parent_category_name,
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

        await interaction.followup.send("Menü erstellt!", ephemeral=True)

    @tasks.loop(minutes=5)
    async def menu_updater_loop(self):
        for menu_key, menu_config in self.menus.items():
            guild_id, menu_channel_id, menu_type = menu_key
            guild = self.bot.get_guild(menu_config.guild_id)
            if not guild:
                continue

            title = get_parent_category_name(menu_type)
            live_data = self.get_module_categories(
                guild.categories, convert_to_clean_string(title))

            for item in live_data:
                item.guild_id = guild_id
                item.menu_channel_id = menu_channel_id
                item.menu_type = menu_type

            new_hash = generate_data_hash(live_data)
            self.save_modules_to_db_by_key(
                guild_id, menu_channel_id, menu_type, live_data)

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
                view = QuickMenuView(
                    title=title, modules=live_data, menu_key=menu_key_str, page=0)
                await message.edit(view=view)
                self.menu_hashes[menu_key] = new_hash
            except Exception as e:
                self.logger.error(f"Loop error for {menu_type}: {e}")

    @menu_updater_loop.before_loop
    async def before_updater(self):
        await self.bot.wait_until_ready()

    def get_module_categories(self, all_categories: List[CategoryChannel],
                              parent_category: str,
                              default_channel: str = "diskussion-und-infos") -> list[ModuleItem]:
        module_categories = self.get_module_categories_of_parent_category(
            all_categories, parent_category)

        menu_items: list[ModuleItem] = []

        for category in module_categories:
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


async def setup(bot: commands.Bot) -> None:
    cog = QuickMenu(bot)

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
        bot.add_view(QuickMenuView(title=title, modules=m_list,
                     menu_key=menu_key_str, page=0))

    await bot.add_cog(cog)

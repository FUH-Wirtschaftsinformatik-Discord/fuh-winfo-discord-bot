from dataclasses import asdict
import logging
import os
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

MODULES_DB_FILE = "data/modules_db.json"
CONFIG_FILE = "data/menu_config.json"

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
    dict_list = [asdict(item) for item in modules_list]
    data_string = json.dumps(dict_list, sort_keys=True)
    return hashlib.md5(data_string.encode()).hexdigest()

def convert_to_clean_string(input_str: str):
    return input_str.lower().strip()

# --- MODULE PERSISTENCE (FLATTENED) ---

def fetch_modules_from_db() -> list[ModuleItem]:
    """Loads modules as a flattened list."""
    if os.path.exists(MODULES_DB_FILE):
        with open(MODULES_DB_FILE, "r", encoding="utf-8") as f:
            the_json = json.load(f)
            return [ModuleItem(**item) for item in the_json]
    return []

def save_modules_to_db(modules_list: list[ModuleItem]):
    """Saves a flattened list of modules."""
    serializable_data = [asdict(module) for module in modules_list]
    with open(MODULES_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(serializable_data, f, indent=4, ensure_ascii=False)

# --- CONFIG PERSISTENCE (FLATTENED) ---

def load_menu_config() -> list[MenuConfig]:
    """Loads menu configurations as a flattened list."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            raw_data = json.load(f)
            return [MenuConfig(**data) for data in raw_data]
    return []

def save_menu_config(menu_type: str, guild_id: int, channel_id: int, message_id: int):
    """Updates a specific config in the flattened list and saves."""
    configs = load_menu_config()
    
    # Remove existing entry for this type if it exists
    configs = [c for c in configs if c.menu_type != menu_type]
    
    # Add new config
    new_cfg = MenuConfig(guild_id, channel_id, message_id, menu_type)
    configs.append(new_cfg)

    serializable_data = [asdict(cfg) for cfg in configs]
    with open(CONFIG_FILE, "w") as f:
        json.dump(serializable_data, f, indent=4, sort_keys=True)
        
        

# --- COG ---

@app_commands.guild_only()
class QuickMenu(commands.GroupCog, name="quickmenu", description="Quick Navigation Menus"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.menu_hashes = {}
        
        # We still keep a runtime dict for O(1) access during the loop, 
        # but the source of truth (file) is flat.
        self.menus = {cfg.menu_type: cfg for cfg in load_menu_config()}
        self.menu_updater_loop.start()

    def save_modules_to_db_by_key(self, menu_type: str, new_modules: list[ModuleItem]):
        """Helper to update subset of modules in the flat list."""
        all_modules = fetch_modules_from_db()
        filtered = [m for m in all_modules if m.menu_type != menu_type]
        filtered.extend(new_modules)
        save_modules_to_db(filtered)

    @app_commands.command(name="setup-menu", description="Erstellt ein Modul-Menü.")
    @app_commands.choices(menu_type=[
        app_commands.Choice(name="📚 Pflicht Wiwi", value="pflicht-wiwi"),
        app_commands.Choice(name="💻 Pflicht Info", value="pflicht-info")
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

        # Cleanup existing message if it exists
        existing = self.menus.get(menu_type.value)
        if existing:
            try:
                ch = interaction.guild.get_channel(existing.channel_id)
                msg = await ch.fetch_message(existing.message_id)
                await msg.delete()
            except: pass

        # Send New Menu
        view = QuickMenuView(parent_category_name, menu_items, menu_type.value, page=0)
        msg_content = f"📚 **{parent_category_name}**\nWähle ein Modul:"
        message = await interaction.channel.send(content=msg_content, view=view)

        # Update State & Persist
        self.menu_hashes[menu_type.value] = generate_data_hash(menu_items)
        save_menu_config(menu_type.value, interaction.guild.id, interaction.channel.id, message.id)
        
        # Refresh local cache
        self.menus[menu_type.value] = MenuConfig(interaction.guild.id, interaction.channel.id, message.id, menu_type.value)
        
        await interaction.followup.send("Menü erstellt!", ephemeral=True)

    @tasks.loop(minutes=5)
    async def menu_updater_loop(self):
        for menu_type, menu_config in self.menus.items():
            guild = self.bot.get_guild(menu_config.guild_id)
            if not guild: continue

            title = get_parent_category_name(menu_type)
            live_data = self.get_module_categories(guild.categories, convert_to_clean_string(title))
            
            new_hash = generate_data_hash(live_data)
            self.save_modules_to_db_by_key(menu_type, live_data)

            if self.menu_hashes.get(menu_type) == new_hash:
                continue

            try:
                channel = self.bot.get_channel(menu_config.channel_id)
                message = await channel.fetch_message(message_id=menu_config.message_id)
                view = QuickMenuView(title=title, modules=live_data, menu_type=menu_type, page=0)
                await message.edit(view=view)
                self.menu_hashes[menu_type] = new_hash
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
                channel_id=channel.id, description=module_name, module_number=module_number, menu_type=ModuleMenuType.PFLICHT_WIWI)
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
        grouped[m.menu_type].append(m)
        
    # 3. Register persistent views
    for m_type, m_list in grouped.items():
        cog.menu_hashes[m_type] = generate_data_hash(m_list)
        title = get_parent_category_name(m_type) or "Modulübersicht"
        bot.add_view(QuickMenuView(title=title, modules=m_list, menu_type=m_type, page=0))

    await bot.add_cog(cog)
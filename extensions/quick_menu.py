from dataclasses import asdict
import os
import re
from typing import List

from discord import CategoryChannel, app_commands, Interaction
import discord
from discord.ext import commands

from models import MenuConfig, ModuleItem, ModuleType
from views.quick_menu_view import QuickMenuView

import hashlib
import json
from discord.ext import tasks

MODULES_DB_FILE = "data/modules_db.json"
CONFIG_FILE = "data/menu_config.json"


def generate_data_hash(modules_list: list[ModuleItem]):
    """Converts the modules list into a unique hash string to detect changes."""
    dict_list = [asdict(item) for item in modules_list]

    data_string = json.dumps(dict_list, sort_keys=True)
    return hashlib.md5(data_string.encode()).hexdigest()


def save_modules_to_db_by_key(menu_type: str, modules_list: list):
    """Saves the scraped module data to our local JSON database."""
    modules = fetch_modules_from_db()

    modules[menu_type] = modules_list
    save_modules_to_db(modules)


def save_modules_to_db(complete_database: dict[str, list['ModuleItem']]):
    """Saves the scraped module data to our local JSON database."""

    # 1. Iterate through the dictionary, AND iterate through the lists
    serializable_data = {
        menu_key: [asdict(module) for module in module_list]
        for menu_key, module_list in complete_database.items()
    }

    # 2. Save to JSON
    with open(MODULES_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(serializable_data, f, indent=4, ensure_ascii=False)

    # 3. Accurately count the items (summing the length of all lists)
    total_modules = sum(len(module_list)
                        for module_list in complete_database.values())
    print(
        f"Saved {total_modules} modules across {len(complete_database)} categories to the database.")


def fetch_modules_from_db() -> dict[str, list[ModuleItem]]:
    """Loads the module data from the local JSON database."""
    if os.path.exists(MODULES_DB_FILE):
        with open(MODULES_DB_FILE, "r", encoding="utf-8") as f:
            deserialized_menus = {}
            the_json = json.load(f)

            for menu_key, module_list in the_json.items():
                # Loop through the list and convert each dictionary into a ModuleItem
                # The ** operator unpacks the dictionary keys directly into the dataclass parameters
                deserialized_menus[menu_key] = [
                    ModuleItem(**item) for item in module_list]

            return deserialized_menus
    return {}


def save_menu_config(menu_type: str, guild_id: int, channel_id: int, message_id: int):
    """Saves the guild, channel, and message IDs to a JSON file."""

    existing_config = load_menu_config()
    existing_config[menu_type] = MenuConfig(guild_id, channel_id, message_id)

    # asdict() automatically converts your dataclass into a JSON-safe dictionary
    serializable_data = {
        menu_key: asdict(config_object) for menu_key, config_object in existing_config.items()
    }

    with open(CONFIG_FILE, "w") as f:
        json.dump(serializable_data, f, indent=4)


def load_menu_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            raw_data = json.load(f)

            return {
                menu_key: MenuConfig(**data) for menu_key, data in raw_data.items()
            }
    return {}


def get_parent_category_name(menu_type: str):
    parent_category = ""

    if menu_type == "pflicht-wiwi":
        return "Pflichtmodule Wirtschaftswissenschaften"

    choice1 = "Wahlpflichmodule Informatik"
    choice2 = "Wahlpflichtmodule Wirtschaftswissenschaften"
    choice3 = "Pflichtmodule Informatik"
    choice4 = "Pflichtmodule Wirtschaftswissenschaften"
    choice5 = "Pflichtmodule Wirtschaftswissenschaften"
    choice6 = "Wahlpflichmodule Wirtschaftsinformatik"
    choice6 = "Pflichtmodule Mathematik"

    return parent_category


def convert_to_clean_string(input: str):
    return input.lower().strip()


@app_commands.guild_only()
class QuickMenu(commands.GroupCog, name="quickmenu", description="Dies ist ein Text"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # --- Hashing ---
        self.menu_hashes = {}

        # --- Load the config file ---
        self.menus = load_menu_config()

        self.menu_updater_loop.start()

    @app_commands.command(name="pflichtmodule-wiwi", description="Zeigt ein Menü der Pflichtmodule für Wiwi an.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.choices(menu_type=[
        app_commands.Choice(
            name="📚 Pflichtmodule - Wirtschaftswissenschaften (Wiwi)", value="pflicht-wiwi"),
        app_commands.Choice(
            name="💻 Pflichtmodule - Informatik (Info)", value="pflicht-info")
    ])
    async def cmd_pflichtmodule_wiwi(self, interaction: Interaction, menu_type: app_commands.Choice[str]):
        await interaction.response.defer()

        parent_category = get_parent_category_name(menu_type.value)
        clean_parent_category = convert_to_clean_string(parent_category)

        if not parent_category or len(parent_category) == 0:
            await interaction.followup.send("Unbekannter Menütyp. Bitte wähle einen gültigen Typ aus.", ephemeral=True)
            return

        # Fetch data (wrap in try/except in case your parsing logic hits an unexpected server error)
        try:
            menu_items = self.get_module_categories(
                interaction.guild.categories, clean_parent_category)
        except Exception as e:
            await interaction.followup.send(f"Fehler beim Laden der Kategorien: {e}", ephemeral=True)
            return

        if not menu_items:
            await interaction.followup.send("Keine Module vorhanden.", ephemeral=True)
            return

        # ==========================================
        # UPGRADE 1: CLEANUP GHOST MENUS
        # ==========================================
        if self.menus.get(menu_type.value) and self.menus[menu_type.value].message_id and self.menus[menu_type.value].channel_id:
            try:
                old_channel = interaction.guild.get_channel(
                    self.menus[menu_type.value].channel_id)
                if old_channel:
                    old_message = await old_channel.fetch_message(self.menus[menu_type.value].message_id)
                    await old_message.delete()
            except discord.NotFound:
                pass  # Old message was already deleted by a user, which is fine!
            except discord.HTTPException:
                pass  # Ignore other API errors so it doesn't stop the new menu from spawning

        # ==========================================
        # UPGRADE 2: SEND AS A STANDARD MESSAGE
        # ==========================================
        try:
            # Send a brand new message to the channel, completely separate from the slash command
            title = get_parent_category_name(menu_type.value)
            view = QuickMenuView(title, menu_items, menu_type.value, page=0)
            msg = f"📚 **{title}**\nKlicke auf das Menü um zu einem Modulchannel zu gelangen!"
            message = await interaction.channel.send(content=msg, view=view)
        except discord.Forbidden:
            await interaction.followup.send("Mir fehlen die Rechte, um in diesen Kanal zu senden.", ephemeral=True)
            return

        # ==========================================
        # UPGRADE 3: UPDATE STATE *AFTER* SUCCESS
        # ==========================================
        self.menu_hashes[menu_type.value] = generate_data_hash(menu_items)

        self.menus[menu_type.value] = MenuConfig(
            interaction.guild.id, interaction.channel.id, message.id)

        try:
            save_menu_config(menu_type.value, interaction.guild.id,
                             interaction.channel.id, message.id)
            # Send a private success confirmation to the admin who ran the command
            await interaction.followup.send("Menü erfolgreich erstellt und alte Version bereinigt!", ephemeral=True)
        except Exception as e:
            # If the hard drive is full or file is locked, warn the admin but don't crash
            await interaction.followup.send(f"Menü ist online, aber lokales Speichern fehlgeschlagen: {e}", ephemeral=True)

    def get_module_categories(self, all_categories: List[CategoryChannel], parent_category: str) -> list[ModuleItem]:
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

            # Try to find a channel named "diskussion-und-infos" in this category, or fallback to the first public channel if it doesn't exist
            channel = self.get_channel_or_first_public_of_category(
                category, "diskussion-und-infos")
            if channel is None:
                continue

            module_item = ModuleItem(
                channel_id=channel.id, description=module_name, id=module_number, module_type=ModuleType.LECTURE)
            menu_items.append(module_item)

        return menu_items

    @tasks.loop(minutes=5)
    async def menu_updater_loop(self):

        for menu_type, menu_config in self.menus.items():

            if menu_config.channel_id is None:
                return

            guild = self.bot.get_guild(menu_config.guild_id)

            if not guild:
                return

            menu_title = get_parent_category_name(menu_type)
            clean_parent_category = convert_to_clean_string(menu_title)

            # 1. Scrape the live data from Discord categories
            live_modules_data = self.get_module_categories(
                guild.categories, clean_parent_category)

            # 2. Generate the hash to check if anything actually changed
            new_hash = generate_data_hash(live_modules_data)

            # 3. SAVE the data to our local database!
            save_modules_to_db_by_key(menu_type, live_modules_data)

            # 4. Compare with the currently displayed menu
            if hasattr(self.menu_hashes, 'menu_hashes') and new_hash == self.menu_hashes[menu_type]:
                # Nothing changed, skip the Discord API call
                return

            # ... (The rest of the update/self-healing logic remains exactly the same) ...
            channel = self.bot.get_channel(
                self.menus[menu_type].channel_id)

            try:
                message = await channel.fetch_message(self.menus[menu_type].message_id)
                view = QuickMenuView(title="Modulübersicht",
                                     modules=live_modules_data,
                                     menu_type=menu_type,
                                     page=0)
                await message.edit(view=view)

                self.menu_hashes[menu_type] = new_hash
                print("Menu automatically updated with new database data.")

            except discord.NotFound:
                # Handle deleted message...
                self.menus[menu_type].message_id = None
                pass

    @menu_updater_loop.before_loop
    async def before_updater(self):
        # Wait until the bot is fully logged in before starting the loop
        await self.bot.wait_until_ready()

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
            return test_channels
        if end_index == -1:
            test_channels = categories[start_index:]
            return test_channels
        if start_index == -1:
            test_channels = categories[:end_index]
            return test_channels

        return categories[start_index:end_index]


async def setup(bot: commands.Bot) -> None:
    text_commands = QuickMenu(bot)

    # 1. Instantly load the last known good state from our local database!
    saved_modules = fetch_modules_from_db()

    # 2. Register the view so buttons work instantly after a reboot
    for menu_key, modules_list in saved_modules.items():
        # Register a view for EACH menu!
        title = "Modulübersicht"  # Or map this dynamically based on menu_key

        # 3. Calculate the hash so the loop knows where we left off
        text_commands.menu_hashes[menu_key] = generate_data_hash(
            saved_modules[menu_key])

        bot.add_view(QuickMenuView(
            title=title, modules=modules_list, menu_type=menu_key, page=0))

    await bot.add_cog(text_commands)

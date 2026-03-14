import os
import re
from typing import List

from discord import CategoryChannel, app_commands, Interaction
import discord
from discord.ext import commands

from views.module_view import ModuleView

import hashlib
import json
from discord.ext import tasks

MODULES_DB_FILE = "data/modules_db.json"
CONFIG_FILE = "data/menu_config.json"

def generate_data_hash(modules_list):
    """Converts the modules list into a unique hash string to detect changes."""
    data_string = json.dumps(modules_list, sort_keys=True)
    return hashlib.md5(data_string.encode()).hexdigest()


def save_modules_to_db(modules_list: list):
    """Saves the scraped module data to our local JSON database."""
    with open(MODULES_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(modules_list, f, indent=4, ensure_ascii=False)
    print(f"💾 Saved {len(modules_list)} modules to the database.")

def fetch_modules_from_db():
    """Loads the module data from the local JSON database."""
    if os.path.exists(MODULES_DB_FILE):
        with open(MODULES_DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [] # Return empty if the database doesn't exist yet

def save_menu_config(guild_id: int, channel_id: int, message_id: int):
    """Saves the guild, channel, and message IDs to a JSON file."""
    data = {
        "guild_id": guild_id,
        "channel_id": channel_id,
        "message_id": message_id
    }
    # Write the data to the file with a nice indent for readability
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_menu_config():
    """Loads the config from the JSON file. Returns Nones if it doesn't exist."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
            
    # Fallback if the bot is starting fresh without a file
    return {
        "guild_id": None, 
        "channel_id": None, 
        "message_id": None
    }    

@app_commands.guild_only()
class QuickMenu(commands.GroupCog, name="quickmenu", description="Dies ist ein Text"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # --- NEW: State Tracking Variables ---
        self.current_menu_hash = None
        
        # # In a real bot, you should save these IDs to a JSON file or Database 
        # # so they survive a bot restart!
        # self.menu_channel_id = None 
        # self.menu_message_id = None  
        
        
        # --- Load the config file ---
        config = load_menu_config()
        self.menu_guild_id = config.get("guild_id")
        self.menu_channel_id = config.get("channel_id")
        self.menu_message_id = config.get("message_id")
        
        if self.menu_message_id:
            print(f"📁 Loaded existing config! Guild: {self.menu_guild_id}, Message: {self.menu_message_id}")           
        
        self.menu_updater_loop.start()   

    @app_commands.command(name="pflichtmodule-wiwi", description="Zeigt ein Menü der Pflichtmodule für Wiwi an.")
    @app_commands.default_permissions(administrator=True)
    async def cmd_pflichtmodule_wiwi(self, interaction: Interaction):
        # 1. Defer EPHEMERALLY. The "bot is thinking" message is only visible to the admin.
        await interaction.response.defer()        
        # await interaction.response.defer(ephemeral=True)        
        
        title = "Pflichtmodule Wirtschaftswissenschaften"
        start_string = title.lower().strip()

        # Fetch data (wrap in try/except in case your parsing logic hits an unexpected server error)
        try:
            menu_items = self.get_module_categories(interaction.guild.categories, start_string)
        except Exception as e:
            await interaction.followup.send(f"❌ Fehler beim Laden der Kategorien: {e}", ephemeral=True)
            return

        if not menu_items:
            await interaction.followup.send("❌ Keine Module vorhanden.", ephemeral=True)
            return

        # ==========================================
        # UPGRADE 1: CLEANUP GHOST MENUS
        # ==========================================
        if getattr(self, "menu_message_id", None) and getattr(self, "menu_channel_id", None):
            try:
                old_channel = interaction.guild.get_channel(self.menu_channel_id)
                if old_channel:
                    old_message = await old_channel.fetch_message(self.menu_message_id)
                    await old_message.delete()
            except discord.NotFound:
                pass # Old message was already deleted by a user, which is fine!
            except discord.HTTPException:
                pass # Ignore other API errors so it doesn't stop the new menu from spawning

        # ==========================================
        # UPGRADE 2: SEND AS A STANDARD MESSAGE
        # ==========================================
        msg = f"📚 **{title}**\nSeite 1 von {(len(menu_items)-1)//25 + 1}"
        view = ModuleView(title, menu_items, page=0)

        try:
            # Send a brand new message to the channel, completely separate from the slash command
            message = await interaction.channel.send(content=msg, view=view)
        except discord.Forbidden:
            await interaction.followup.send("❌ Mir fehlen die Rechte, um in diesen Kanal zu senden.", ephemeral=True)
            return

        # ==========================================
        # UPGRADE 3: UPDATE STATE *AFTER* SUCCESS
        # ==========================================
        self.current_menu_hash = generate_data_hash(menu_items)
        self.menu_guild_id = interaction.guild.id 
        self.menu_channel_id = interaction.channel.id
        self.menu_message_id = message.id 

        try:
            save_menu_config(interaction.guild.id, interaction.channel.id, message.id)
            # Send a private success confirmation to the admin who ran the command
            await interaction.followup.send("✅ Menü erfolgreich erstellt und alte Version bereinigt!", ephemeral=True)
        except Exception as e:
            # If the hard drive is full or file is locked, warn the admin but don't crash
            await interaction.followup.send(f"⚠️ Menü ist online, aber lokales Speichern fehlgeschlagen: {e}", ephemeral=True)    

    def get_module_categories(self, all_categories : List[CategoryChannel], start_string: str):
        module_categories = self.get_module_categories_of_parent_category(
            all_categories, start_string)

        menu_items = []

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

            menu_items.append({
                "id": module_number,
                "description": module_name,
                "channel_id": channel.id
            })
            
        return menu_items

    # --- NEW: The Background Updater Task ---
    @tasks.loop(minutes=5)
    async def menu_updater_loop(self):
        if not self.menu_channel_id or not self.menu_guild_id:
            return 

        guild = self.bot.get_guild(self.menu_guild_id)
        if not guild:
            return

        title = "Pflichtmodule Wirtschaftswissenschaften"
        start_string = title.lower().strip()        

        # 1. Scrape the live data from Discord categories
        live_modules_data = self.get_module_categories(guild.categories, start_string)
        
        # 2. Generate the hash to check if anything actually changed
        new_hash = generate_data_hash(live_modules_data)

        # 3. Compare with the currently displayed menu
        if new_hash == self.current_menu_hash:
            return # Nothing changed, skip the Discord API call
        
        # 4. SAVE the data to our local database!
        save_modules_to_db(live_modules_data)

        # ... (The rest of the update/self-healing logic remains exactly the same) ...
        channel = self.bot.get_channel(self.menu_channel_id)
        
        try:
            message = await channel.fetch_message(self.menu_message_id)
            view = ModuleView(title="Modulübersicht", modules=live_modules_data, page=0)
            await message.edit(view=view)
            self.current_menu_hash = new_hash
            print("✅ Menu automatically updated with new database data.")
            
        except discord.NotFound:
            # Handle deleted message...
            self.menu_message_id = None
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
                                                 parent_category_name: str) -> list[discord.CategoryChannel]:

        if not categories:
            return []

        if not parent_category_name:
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

            if start_index == -1 and parent_category_name in category_name:
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
        
    # 2. Calculate the hash so the loop knows where we left off
    text_commands.current_menu_hash = generate_data_hash(saved_modules)   
    
    # 3. Register the view so buttons work instantly after a reboot
    bot.add_view(ModuleView(title="Modulübersicht", modules=saved_modules, page=0))
        
    # 4. Start the background loop to watch for future changes
    print("✅ Boot sequence complete. Loaded modules from DB.")     
    
    await bot.add_cog(text_commands)
    


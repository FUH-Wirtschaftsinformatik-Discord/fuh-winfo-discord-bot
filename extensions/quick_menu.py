import re

from discord import app_commands, Interaction
import discord
from discord.ext import commands

from views.module_view import ModuleView


@app_commands.guild_only()
class QuickMenu(commands.GroupCog, name="quickmenu", description="Dies ist ein Text"):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pflichtmodule-wiwi", description="Zeigt ein Menü der Pflichtmodule für Wiwi an.")
    async def cmd_pflichtmodule_wiwi(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        title = "Pflichtmodule Wirtschaftswissenschaften"
        start_string = title.lower().strip()

        module_categories = self.get_module_categories_of_parent_category(
            interaction.guild.categories, start_string)

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

        if not menu_items:
            await interaction.edit_original_response(content="❌ Keine Module vorhanden.")
            return

        msg = f"📚 **{title}**\nSeite 1 von {(len(menu_items)-1)//25 + 1}"

        await interaction.edit_original_response(content=msg, view=ModuleView(title, menu_items))

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
    await bot.add_cog(text_commands)
    bot.add_view(ModuleView(title="Dummy", modules=[], page=0))

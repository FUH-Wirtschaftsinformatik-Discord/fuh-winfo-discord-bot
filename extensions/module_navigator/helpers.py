import hashlib
import json
import re
from typing import List

import discord
from discord import CategoryChannel
from playhouse.shortcuts import model_to_dict

from models import ModuleNavigatorCustomMenuItem, ModuleNavigatorModuleItem, ModuleNavigatorMenuType

# This dictionary maps the internal menu type enum to the human-readable name
# that is used to find the "parent" category in the Discord channel list.
_MENU_TYPE_TO_CATEGORY_NAME = {
    ModuleNavigatorMenuType.PFLICHT_WIWI: "Pflichtmodule Wirtschaftswissenschaften",
    ModuleNavigatorMenuType.PFLICHT_INFO: "Pflichtmodule Informatik",
    ModuleNavigatorMenuType.PFLICHT_WINFO: "Pflichtmodule Wirtschaftsinformatik",
    ModuleNavigatorMenuType.PFLICHT_MATHE: "Pflichtmodule Mathematik",
    ModuleNavigatorMenuType.WAHL_WIWI: "Wahlpflichtmodule Wirtschaftswissenschaften",
    ModuleNavigatorMenuType.WAHL_INFO: "Wahlpflichtmodule Informatik",
    ModuleNavigatorMenuType.WAHL_WINFO: "Wahlpflichtmodule Wirtschaftsinformatik",
}


def get_parent_category_name(menu_type: str) -> str | None:
    """
    Returns the human-readable category name for a given menu type string.

    Args:
        menu_type: The string identifier for the menu type (e.g., 'pflicht-info').

    Returns:
        The corresponding category name or None if the type is invalid.
    """
    try:
        menu_type_enum = ModuleNavigatorMenuType(menu_type)
        return _MENU_TYPE_TO_CATEGORY_NAME.get(menu_type_enum)
    except ValueError:
        return None


def generate_data_hash(modules_list: list[ModuleNavigatorModuleItem | ModuleNavigatorCustomMenuItem]) -> str:
    """
    Converts a list of menu items into a unique MD5 hash string.
    This hash is used to detect if the menu content has changed.

    Args:
        modules_list: A list of ModuleNavigatorModuleItem or ModuleNavigatorCustomMenuItem objects.

    Returns:
        A hexadecimal MD5 hash string.
    """
    instances = []
    
    for module in modules_list:
        # Convert model object to dictionary, to ensure the hash is based on content
        instance_dictionary = model_to_dict(module)       
        instances.append(instance_dictionary)
        
    data_string = json.dumps(instances, sort_keys=True)
    return hashlib.md5(data_string.encode()).hexdigest()


def convert_to_clean_string(input_str: str) -> str:
    """
    Standardizes a string by converting it to lowercase and stripping whitespace.

    Args:
        input_str: The string to clean.

    Returns:
        The cleaned string.
    """
    return input_str.lower().strip()


def get_module_categories(all_categories: List[CategoryChannel],
                          parent_category: str,
                          default_channel: str = "diskussion-und-infos") -> list[ModuleNavigatorModuleItem]:
    """
    Scans a list of guild categories to find module channels that logically belong
    to a specific parent category. It extracts module information from their names
    and returns them as a list of ModuleNavigatorModuleItem objects.

    Args:
        all_categories: A list of all CategoryChannel objects in the guild.
        parent_category: The name of the parent category to search under.
        default_channel: The preferred name of the channel to link to within a module category.

    Returns:
        A list of ModuleNavigatorModuleItem objects representing the found module channels.
    """
    # 1. Find the group of categories that fall under the parent category header.
    module_category_group = get_module_categories_of_parent_category(
        all_categories, parent_category)

    # 2. Filter this group to only include categories visible to @everyone.
    public_categories = filter_public_categories_and_channels(
        module_category_group)

    menu_items: list[ModuleNavigatorModuleItem] = []
    for category in public_categories:
        # 3. For each public category, extract module details from its name.
        module_number_match = re.search(r'\d+', category.name)
        module_number = module_number_match.group(0).strip(
        ) if module_number_match and module_number_match.group() else ""

        # Remove module number and any non-ASCII characters for a clean name.
        module_name = "".join(char for char in category.name.replace(
            module_number, "") if char.isascii()).strip()

        # A category without channels is not a real module, so we skip it.
        if not category.channels:
            continue

        # 4. Find a suitable channel to link to within the category.
        # It prefers a channel with a specific name (default: "diskussion-und-infos")
        # but falls back to the first available public channel.
        target_channel = get_channel_or_first_public_of_category(
            category, default_channel)

        if not target_channel:
            continue

        # 5. Create the menu item object.
        module_item = ModuleNavigatorModuleItem(
            module_channel_id=target_channel.id, description=module_name, module_number=module_number)
        menu_items.append(module_item)

    return menu_items


def get_channel_or_first_public_of_category(category: discord.CategoryChannel, target_name: str) -> discord.TextChannel | None:
    """
    Finds a public text channel within a category that matches a target name.
    If no exact match is found, it returns the first public channel found in that category.
    Returns None if no public channels exist.

    Args:
        category: The CategoryChannel to search within.
        target_name: The desired name of the channel.

    Returns:
        The found discord.TextChannel or None.
    """
    everyone_role = category.guild.default_role
    fallback_channel = None

    for channel in category.text_channels:
        # Check if the @everyone role can view the channel.
        if channel.permissions_for(everyone_role).view_channel:
            # If it's the first public channel we've found, keep it as a fallback.
            if fallback_channel is None:
                fallback_channel = channel

            # If we find a channel with the exact target name, we're done.
            if channel.name == target_name:
                return channel

    # If no exact match was found, return the fallback (which can be None).
    return fallback_channel


def get_module_categories_of_parent_category(
        categories: list[discord.CategoryChannel],
        parent_category_name_query: str) -> list[discord.CategoryChannel]:
    """
    Finds a slice of categories that logically fall under a 'parent' category.
    This logic is based on a visual convention in the Discord server where channels
    are grouped under a non-functional category that acts as a header.

    The slice starts AFTER the parent category and ends right BEFORE the next
    category that does not look like a module (i.e., its name doesn't start with a number).

    Args:
        categories: A list of all categories in the guild, assumed to be in correct order.
        parent_category_name_query: A string to search for in the parent category's name.

    Returns:
        A list slice of CategoryChannel objects.
    """
    if not categories or not parent_category_name_query:
        return []

    start_index = -1
    end_index = -1

    # Find the index of the "parent" category, which marks the start of our slice.
    for i, category in enumerate(categories):
        if parent_category_name_query in category.name.lower().strip():
            start_index = i
            break

    if start_index == -1:
        return []  # Parent category not found.

    # Starting from the item after the parent, find where the module category list ends.
    # We assume the list ends when we hit a category whose name does NOT start with a digit.
    for i in range(start_index + 1, len(categories)):
        category_name = categories[i].name.lower().strip()
        if not re.match(r'^\d', category_name):
            end_index = i
            break

    # The slice of module categories is from after the parent up to the end marker.
    slice_start = start_index + 1

    if end_index != -1:
        # An end marker was found, so slice up to it.
        return categories[slice_start:end_index]
    else:
        # No end marker was found, so assume all subsequent channels belong to the group.
        return categories[slice_start:]


def filter_public_categories_and_channels(categories: list[discord.CategoryChannel]) -> list[discord.CategoryChannel]:
    """
    Filters a list of categories, returning only those that are public AND
    contain at least one public text channel.

    Args:
        categories: A list of CategoryChannel objects to filter.

    Returns:
        A filtered list of public CategoryChannel objects.
    """
    public_categories = []
    for category in categories:
        everyone_role = category.guild.default_role
        # Check if the category itself is public.
        if category.permissions_for(everyone_role).view_channel:
            # Check if it has at least one public text channel.
            has_public_channel = any(
                channel.permissions_for(everyone_role).view_channel
                for channel in category.text_channels
            )
            
            if has_public_channel:
                public_categories.append(category)
    return public_categories

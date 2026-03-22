import hashlib
import json
import re
from typing import List

import discord
from discord import CategoryChannel
from playhouse.shortcuts import model_to_dict

from models import ModuleNavigatorCustomMenuItem, ModuleNavigatorModuleItem, ModuleNavigatorMenuType

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
    """Returns the human-readable category name for a given menu type."""
    try:
        menu_type_enum = ModuleNavigatorMenuType(menu_type)
        return _MENU_TYPE_TO_CATEGORY_NAME.get(menu_type_enum)
    except ValueError:
        return None


def generate_data_hash(modules_list: list[ModuleNavigatorModuleItem | ModuleNavigatorCustomMenuItem]):
    """Converts the modules list into a unique hash string to detect changes."""
    dict_list = []
    for item in modules_list:
        d = model_to_dict(item)
        d.pop('id', None)  # ensure hash ignores DB primary keys
        dict_list.append(d)
    data_string = json.dumps(dict_list, sort_keys=True)
    return hashlib.md5(data_string.encode()).hexdigest()


def convert_to_clean_string(input_str: str) -> str:
    """Converts a string to lowercase and strips whitespace."""
    return input_str.lower().strip()


def get_module_categories(all_categories: List[CategoryChannel],
                          parent_category: str,
                          default_channel: str = "diskussion-und-infos") -> list[ModuleNavigatorModuleItem]:
    """
    Scans guild categories to find module channels that belong to a specific parent category,
    extracts module information from their names, and returns them as a list of items.
    """
    # First filter categories to those that are under the specified parent category
    all_module_categories = get_module_categories_of_parent_category(
        all_categories, parent_category)
    public_categories = filter_public_categories_and_channels(
        all_module_categories)

    menu_items: list[ModuleNavigatorModuleItem] = []

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
        if not category.channels:
            continue

        # Try to find a channel in this category, or fallback to the first public channel if it doesn't exist
        channel = get_channel_or_first_public_of_category(
            category, default_channel)
        if channel is None:
            continue

        module_item = ModuleNavigatorModuleItem(
            module_channel_id=channel.id, description=module_name, module_number=module_number)
        menu_items.append(module_item)

    return menu_items


def get_channel_or_first_public_of_category(category: discord.CategoryChannel, target_name: str) -> discord.TextChannel:
    """
    Finds a public channel named like in parameter 'target_name' in a category.
    Returns the first public channel if the target name is not found, or None if no public channels exist.
    """
    # The default role represents the @everyone role
    everyone_role = category.guild.default_role
    # This variable will hold the first public channel we find, in case we don't find one named like the target name.
    fallback_channel = None

    # Iterate through text channels in this category.
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


def get_module_categories_of_parent_category(
        categories: list[discord.CategoryChannel],
        parent_category_name_query: str) -> list[discord.CategoryChannel]:
    """
    Finds a slice of categories that logically fall under a 'parent' category.
    This logic assumes that channels are visually grouped under a non-functional
    category channel that acts as a header. The slice starts after the parent
    and ends when a category is found that doesn't look like a module category
    (i.e., its name doesn't start with a number).
    """
    if not categories or not parent_category_name_query:
        return []

    start_index = -1
    end_index = -1

    # Find the index of the parent category, which marks the start of our slice.
    for i, category in enumerate(categories):
        if parent_category_name_query in category.name.lower().strip():
            start_index = i
            break

    # If the parent category wasn't found, there's nothing to do.
    if start_index == -1:
        return []

    # Starting from the parent, find where the module category list ends.
    # We assume it ends when we hit a category that doesn't start with a number.
    for i in range(start_index + 1, len(categories)):
        category_name = categories[i].name.lower().strip()
        # This regex checks if the category name does NOT start with a digit.
        if not re.match(r'^\d', category_name):
            end_index = i
            break

    # The slice of module categories is from after the parent to the end marker.
    slice_start = start_index + 1

    if end_index != -1:
        return categories[slice_start:end_index]
    else:
        # If no end marker was found, assume all subsequent channels are part of the group.
        return categories[slice_start:]


def filter_public_categories_and_channels(categories: list[discord.CategoryChannel]) -> list[discord.CategoryChannel]:
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

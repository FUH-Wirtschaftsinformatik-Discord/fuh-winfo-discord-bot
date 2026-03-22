from typing import List
from models import ModuleNavigatorCustomMenuItem, ModuleNavigatorMenuConfig, ModuleNavigatorModuleItem


def fetch_modules_from_db() -> list[ModuleNavigatorModuleItem]:
    """Loads modules as a flattened list."""
    return list(ModuleNavigatorModuleItem.select())


def fetch_custom_menu_items_from_db(guild_id: int, menu_channel_id: int, menu_type: str) -> list[ModuleNavigatorCustomMenuItem]:
    """Loads custom menu items as a flattened list."""
    return list(ModuleNavigatorCustomMenuItem.select().where(
        (ModuleNavigatorCustomMenuItem.guild_id == guild_id) &
        (ModuleNavigatorCustomMenuItem.menu_channel_id == menu_channel_id) &
        (ModuleNavigatorCustomMenuItem.menu_type == menu_type)
    ))


def load_menu_config() -> list[ModuleNavigatorMenuConfig]:
    """Loads menu configurations as a flattened list."""
    return list(ModuleNavigatorMenuConfig.select())


def save_menu_config(menu_type: str, guild_id: int, menu_channel_id: int, message_id: int):
    """Saves or updates a menu configuration in the database."""
    ModuleNavigatorMenuConfig.replace(
        guild_id=guild_id,
        channel_id=menu_channel_id,
        message_id=message_id,
        menu_type=menu_type
    ).execute()


def save_modules_to_db(guild_id: int, menu_channel_id: int, menu_type: str, new_modules: list[ModuleNavigatorModuleItem]):
    """
    Deletes all existing module items for a specific menu and bulk-inserts new ones.
    """
    with ModuleNavigatorModuleItem._meta.database.atomic():
        ModuleNavigatorModuleItem.delete().where(
            (ModuleNavigatorModuleItem.guild_id == guild_id) &
            (ModuleNavigatorModuleItem.menu_channel_id == menu_channel_id) &
            (ModuleNavigatorModuleItem.menu_type == menu_type)
        ).execute()
        ModuleNavigatorModuleItem.bulk_create(new_modules)


def delete_menu_config(guild_id: int, channel_id: int, menu_type: str):
    """Deletes a menu configuration from the database."""
    ModuleNavigatorMenuConfig.delete().where((ModuleNavigatorMenuConfig.guild_id == guild_id) & (
        ModuleNavigatorMenuConfig.channel_id == channel_id) & (ModuleNavigatorMenuConfig.menu_type == menu_type)).execute()


def delete_module_items(guild_id: int, menu_channel_id: int, menu_type: str):
    """Deletes all module items for a specific menu."""
    ModuleNavigatorModuleItem.delete().where((ModuleNavigatorModuleItem.guild_id == guild_id) & (
        ModuleNavigatorModuleItem.menu_channel_id == menu_channel_id) & (ModuleNavigatorModuleItem.menu_type == menu_type)).execute()

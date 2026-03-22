from models import ModuleNavigatorCustomMenuItem, ModuleNavigatorMenuConfig, ModuleNavigatorModuleItem


def fetch_modules_from_db() -> list[ModuleNavigatorModuleItem]:
    """
    Retrieves all module navigator items from the database.

    Returns:
        A list of all ModuleNavigatorModuleItem objects.
    """
    return list(ModuleNavigatorModuleItem.select())


def fetch_custom_menu_items_from_db(guild_id: int, menu_channel_id: int, menu_type: str) -> list[ModuleNavigatorCustomMenuItem]:
    """
    Retrieves all custom menu items for a specific menu from the database.

    Args:
        guild_id: The ID of the guild where the menu resides.
        menu_channel_id: The ID of the channel where the menu resides.
        menu_type: The type of the menu (e.g., 'pflicht-info').

    Returns:
        A list of ModuleNavigatorCustomMenuItem objects matching the criteria.
    """
    return list(ModuleNavigatorCustomMenuItem.select().where(
        (ModuleNavigatorCustomMenuItem.guild_id == guild_id) &
        (ModuleNavigatorCustomMenuItem.menu_channel_id == menu_channel_id) &
        (ModuleNavigatorCustomMenuItem.menu_type == menu_type)
    ))


def load_menu_config() -> list[ModuleNavigatorMenuConfig]:
    """
    Loads all menu configurations from the database.

    Returns:
        A list of all ModuleNavigatorMenuConfig objects.
    """
    return list(ModuleNavigatorMenuConfig.select())


def save_menu_config(menu_type: str, guild_id: int, menu_channel_id: int, message_id: int):
    """
    Saves or updates (upserts) a menu configuration in the database.
    It uses Peewee's `replace` method to either insert a new record or
    replace an existing one based on the primary key.

    Args:
        menu_type: The type of the menu.
        guild_id: The ID of the guild.
        menu_channel_id: The ID of the channel containing the menu.
        message_id: The ID of the message that displays the menu.
    """
    ModuleNavigatorMenuConfig.replace(
        guild_id=guild_id,
        channel_id=menu_channel_id,
        message_id=message_id,
        menu_type=menu_type
    ).execute()


def save_modules_to_db(guild_id: int, menu_channel_id: int, menu_type: str, new_modules: list[ModuleNavigatorModuleItem]):
    """
    Atomically replaces the module items for a specific menu in the database.
    It first deletes all existing items for the menu and then bulk-inserts the new ones.

    Args:
        guild_id: The ID of the guild.
        menu_channel_id: The ID of the channel containing the menu.
        menu_type: The type of the menu.
        new_modules: A list of ModuleNavigatorModuleItem objects to save.
    """
    with ModuleNavigatorModuleItem._meta.database.atomic():
        ModuleNavigatorModuleItem.delete().where(
            (ModuleNavigatorModuleItem.guild_id == guild_id) &
            (ModuleNavigatorModuleItem.menu_channel_id == menu_channel_id) &
            (ModuleNavigatorModuleItem.menu_type == menu_type)
        ).execute()
        ModuleNavigatorModuleItem.bulk_create(new_modules)


def delete_menu_config(guild_id: int, channel_id: int, menu_type: str):
    """
    Deletes a specific menu configuration from the database.

    Args:
        guild_id: The ID of the guild.
        channel_id: The ID of the channel containing the menu.
        menu_type: The type of the menu.
    """
    ModuleNavigatorMenuConfig.delete().where((ModuleNavigatorMenuConfig.guild_id == guild_id) & (
        ModuleNavigatorMenuConfig.channel_id == channel_id) & (ModuleNavigatorMenuConfig.menu_type == menu_type)).execute()


def delete_module_items(guild_id: int, menu_channel_id: int, menu_type: str):
    """
    Deletes all module items associated with a specific menu from the database.

    Args:
        guild_id: The ID of the guild.
        menu_channel_id: The ID of the channel containing the menu.
        menu_type: The type of the menu.
    """
    ModuleNavigatorModuleItem.delete().where((ModuleNavigatorModuleItem.guild_id == guild_id) & (
        ModuleNavigatorModuleItem.menu_channel_id == menu_channel_id) & (ModuleNavigatorModuleItem.menu_type == menu_type)).execute()

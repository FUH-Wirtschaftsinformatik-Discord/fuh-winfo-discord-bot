from collections import defaultdict
from discord.ext import commands
from views.module_navigator_view import ModuleNavigatorView
from . import db
from . import helpers
from .cog import ModuleNavigator


async def setup(bot: commands.Bot) -> None:
    """Sets up the ModuleNavigator cog and registers persistent views."""
    cog = ModuleNavigator(bot)

    # Load all module items from the database to register the persistent views
    all_modules = db.fetch_modules_from_db()

    # Group modules by menu to set up each view
    grouped_by_menu = defaultdict(list)
    for module_item in all_modules:
        key = (module_item.guild_id, module_item.menu_channel_id,
               module_item.menu_type)
        grouped_by_menu[key].append(module_item)

    # Re-register a persistent view for each menu found in the database
    for (guild_id, channel_id, menu_type), module_list in grouped_by_menu.items():
        title = helpers.get_parent_category_name(menu_type) or "Modulübersicht"
        menu_key_str = f"{guild_id}:{channel_id}:{menu_type}"
        view = ModuleNavigatorView(title=title, modules=module_list,
                                   menu_key=menu_key_str, page=0)
        bot.add_view(view)

    # Finally, add the cog to the bot
    await bot.add_cog(cog)

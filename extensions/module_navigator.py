from collections import defaultdict
from discord.ext import commands
from views.module_navigator_view import ModuleNavigatorView
from .module_navigator import db, helpers
from .module_navigator.cog import ModuleNavigator


async def setup(bot: commands.Bot) -> None:
    cog = ModuleNavigator(bot)

    all_modules = db.fetch_modules_from_db()

    grouped = defaultdict(list)
    for m in all_modules:
        grouped[(m.guild_id, m.menu_channel_id, m.menu_type)].append(m)

    for (g_id, c_id, m_type), m_list in grouped.items():
        title = helpers.get_parent_category_name(m_type) or "Modulübersicht"
        menu_key_str = f"{g_id}:{c_id}:{m_type}"
        bot.add_view(ModuleNavigatorView(title=title, modules=m_list,
                                         menu_key=menu_key_str, page=0))

    await bot.add_cog(cog)

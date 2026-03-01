import logging
import os

import discord
from discord import app_commands, Interaction
from discord.ext import commands

from models import GradeStatisticsImage

class ModuleInformationNotFoundError(Exception):
    pass

class GradeStatistics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    @app_commands.command(name="klausurstatistiken",
                          description="Erhalte eine Grafik der Klausurstatistiken für ein Modul.")
    @app_commands.describe(modul_nummer="Nummer des Moduls, das dich interessiert.",
                           public="Sichtbarkeit der Ausgabe: für alle Mitglieder oder nur für dich."
                           )
    async def cmd_module(self,
                         interaction: Interaction, 
                         modul_nummer: int = None,
                         public: bool = False):       

        self.logger.debug(f"Received request for grade statistics for module {modul_nummer} from a user (public: {public})")
        try:
            await interaction.response.defer(ephemeral=not public)
            module = await self.get_statistics_data(modul_nummer)

            self.logger.debug(f"Successfully retrieved statistics for module {modul_nummer}, sending response...")

            with open(module.path, 'rb') as target_file:
                self.logger.debug(f"File {module.path} opened successfully, sending file...")
                discord_file = discord.File(target_file, filename=f"klausurstatistiken.{module.number}.png")
                self.logger.debug(f"File {module.path} wrapped in discord.File, editing original response...")
                await interaction.edit_original_response(attachments=[discord_file])
                self.logger.debug(f"Response for module {modul_nummer} sent successfully.")
            
            self.logger.debug(f"Finished processing request for module {modul_nummer}.")
        except Exception as e:
            self.logger.exception(f"Error while processing grade statistics for module {modul_nummer}!")
            await interaction.edit_original_response(content="Leider konnte ich keine Informationen zu diesem Modul/Kurs finden :(")

    @staticmethod
    async def get_statistics_data(module_number: int) -> GradeStatisticsImage:
        if module_number is None or module_number <= 0:
            raise ValueError(f"Invalid module number")

        found_module: GradeStatisticsImage = GradeStatisticsImage.get_or_none(GradeStatisticsImage.number == module_number)

        if not found_module:
            raise ModuleInformationNotFoundError(f"Zum Modul mit der Nummer {module_number} konnte ich keine Informationen "
                                                 f"finden. Bitte geh sicher, dass dies ein gültiges Modul ist. "
                                                 f"Ansonsten schreibe mir eine Direktnachricht und ich leite sie "
                                                 f"weiter an das Mod-Team.")

        path_to_plots = os.getenv('PLOTS_PATH', 'data/plots')
        path_on_file_system = os.path.join(path_to_plots, str(found_module.path))

        found_module.path = path_on_file_system

        if not os.path.exists(found_module.path):
            raise ModuleInformationNotFoundError(f"Die Grafik für das Modul mit der Nummer {module_number} konnte nicht gefunden werden.")

        return found_module

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GradeStatistics(bot))
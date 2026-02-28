import json
import os
import random
import re

import discord
from discord import app_commands, Interaction
from discord.ext import commands

import utils
from modals.text_command_modal import TextCommandModal
from models import Command, CommandText
from views.text_command_view import TextCommandView

LINKS_FILE = "links.json"

@app_commands.guild_only()
class QuickMenu(commands.GroupCog, name="quickmenu", description="Dies ist ein Text"):
    def __init__(self, bot):
        self.bot = bot


    def load_links(self):
        if not os.path.exists(LINKS_FILE):
            # Create an empty file if missing
            with open(LINKS_FILE, "w") as f:
                json.dump({}, f)
        with open(LINKS_FILE, "r") as f:
            return json.load(f)

    def save_links(self,links):
        with open(LINKS_FILE, "w") as f:
            json.dump(links, f, indent=4)
        print(f"[DEBUG] Saved links.json: {links}")  # debug log

    @app_commands.command(name="listlinks", description="Listet die Text Commands dieses Servers auf.")
    # @app_commands.default_permissions(administrator=True)
    async def cmd_listlinks(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        links = self.load_links()
        
        if not links:
            await interaction.edit_original_response(content="📭 No links have been set yet.")
            return

        lines = []
        for label, value in links.items():
            if value.startswith("channel:"):
                channel_id = int(value.split(":")[1])
                lines.append(f"📌 **{label}** → <#{channel_id}>")  # channel mention
            else:
                lines.append(f"🔗 **{label}** → {value}")  # external link
        
        msg = "\n".join(lines)    
                 
        await interaction.edit_original_response(content=msg)                 

    @app_commands.command(name="addlinks", description="Listet die Text Commands dieses Servers auf.")
    # @app_commands.default_permissions(administrator=True)
    async def cmd_addlinks(self, interaction: Interaction, label: str, url: str):
        await interaction.response.defer(ephemeral=True)

        links = self.load_links()
        
        # # Case 1: If value is a channel mention
        # if len(interaction.message.channel_mentions) > 0:
        #     channel = interaction.message.channel_mentions[0]
        #     links[label] = f"channel:{channel.id}"
        #     display_value = f"#{channel.name}"
        # else:
        #     # Case 2: External link (URL or text)
        #     links[label] = url
        #     display_value = url
        
        links[label] = url     

        self.save_links(links)
                         
        await interaction.edit_original_response(content=f"✅ Link for '{label}' set to: {url}\n")         


    @app_commands.command(name="removelinks", description="Listet die Text Commands dieses Servers auf.")
    async def cmd_removelink(self, interaction: Interaction, label: str):
        """Remove a link from the dropdown.
        (works for both external links and channel-based ones).
        Usage: !removelink Docs
        """
        
        await interaction.response.defer(ephemeral=True)
        
        links = self.load_links()
        
        if label not in links:
            await interaction.edit_original_response(content=f"⚠️ Link '{label}' not found.")
            return

        removed_value = links.pop(label)
        self.save_links(links)

        # Format a nice display value
        if removed_value.startswith("channel:"):
            display_value = f"<#{removed_value.split(':')[1]}>"  # mention format
        else:
            display_value = removed_value

        await interaction.edit_original_response(content=f"❌ Link '{label}' removed (was: {display_value}).\n")
        

    # OLD CODE
    # OLD CODE
    # OLD CODE
    # OLD CODE
    # OLD CODE
    # OLD CODE
    # OLD CODE

    @app_commands.command(name="list", description="Listet die Text Commands dieses Servers auf.")
    @app_commands.default_permissions(administrator=True)
    async def cmd_list(self, interaction: Interaction, cmd: str = None):
        await interaction.response.defer(ephemeral=True)
        items = []
        if cmd:
            if command := Command.get_or_none(Command.command == cmd):
                items = [command_text.text for command_text in command.texts]

            if len(items) == 0:
                await interaction.edit_original_response(content=f"{cmd} ist kein verfügbares Text-Command")
                return
        else:
            for command in Command.select():
                if command.texts.count() > 0:
                    items.append(command.command)

        answer = f"Text Commands:\n" if cmd is None else f"Für {cmd} hinterlegte Texte:\n"
        first = True
        for i, item in enumerate(items):
            if len(answer) + len(item) > 2000:
                if first:
                    await interaction.edit_original_response(content=answer)
                    first = False
                else:
                    await interaction.followup.send(answer, ephemeral=True)
                answer = f""

            answer += f"{i}: {item}\n"

        if first:
            await interaction.edit_original_response(content=answer)
        else:
            await interaction.followup.send(answer, ephemeral=True)

    @app_commands.command(name="add",
                          description="Ein neues Text Command hinzufügen, oder zu einem bestehenden einen weiteren Text hinzufügen")
    @app_commands.describe(cmd="Command. Bsp: link für das Command /link.",
                           text="Text, der bei Benutzung des Commands ausgegeben werden soll.")
    async def cmd_add(self, interaction: Interaction, cmd: str, text: str):
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", cmd):
            await interaction.response.send_message(
                "Ein Command darf nur aus Kleinbuchstaben und Zahlen bestehen, die durch Bindestriche getrennt werden können.",
                ephemeral=True)
            return

        command = Command.get_or_none(Command.command == cmd)
        description = command.description if command else ""
        await interaction.response.send_modal(
            TextCommandModal(text_commands=self, cmd=cmd, text=text, description=description))

    @app_commands.command(name="edit", description="Bearbeite bestehende Text Commands")
    @app_commands.describe(cmd="Command, dass du bearbeiten möchtest", id="ID des zu bearbeitenden Texts",
                           text="Neuer Text, der statt des alten ausgegeben werden soll.")
    async def cmd_edit(self, interaction: Interaction, cmd: str, id: int, text: str):
        await interaction.response.defer(ephemeral=True)

        if not utils.is_mod(interaction.user, self.bot):
            await interaction.edit_original_response(content="Du hast nicht die notwendigen Berechtigungen, "
                                                             "um dieses Command zu benutzen!")
            return

        if command := Command.get_or_none(Command.command == cmd):
            command_texts = list(command.texts)
            if 0 <= id < len(command_texts):
                CommandText.update(text=text).where(
                    CommandText.id == command_texts[id].id).execute()
                await interaction.edit_original_response(
                    content=f"Text {id} für Command {cmd} wurde erfolgreich geändert")
            else:
                await interaction.edit_original_response(content="Ungültiger Index")
        else:
            await interaction.edit_original_response(content=f"Command `{cmd}` nicht vorhanden!")

    @app_commands.command(name="remove",
                          description="Entferne ein gesamtes Command oder einen einzelnen Text von einem Command.")
    @app_commands.describe(cmd="Command, dass du entfernen möchtest, oder von dem du einen Text entfernen möchtest.",
                           id="ID des zu entfernenden Texts.")
    async def cmd_command_remove(self, interaction: Interaction, cmd: str, id: int = None):
        await interaction.response.defer(ephemeral=True)

        if not utils.is_mod(interaction.user, self.bot):
            await interaction.edit_original_response(content="Du hast nicht die notwendigen Berechtigungen, "
                                                             "um dieses Command zu benutzen!")
            return

        if command := Command.get_or_none(Command.command == cmd):
            if id is None:
                await self.remove_command(command)
                await interaction.edit_original_response(content=f"Text Command `{cmd}` wurde erfolgreich entfernt.")
            else:
                command_texts = list(command.texts)
                if 0 <= id < len(command_texts):
                    await self.remove_text(command, command_texts, id)
                    await interaction.edit_original_response(
                        content=f"Text {id} für Command `{cmd}` wurde erfolgreich entfernt")
                else:
                    await interaction.edit_original_response(content=f"Ungültiger Index")
        else:
            await interaction.edit_original_response(content=f"Command `{cmd}` nicht vorhanden!")

    async def add_command(self, cmd: str, text: str, description: str, guild_id: int):
        mod_channel_id = self.bot.get_settings(guild_id).modmail_channel_id
        mod_channel = await self.bot.fetch_channel(mod_channel_id)
        if command := Command.get_or_none(Command.command == cmd):
            CommandText.create(text=text, command=command.id)
            if command.description != description:
                Command.update(description=description).where(
                    Command.id == command.id).execute()
                self.bot.tree.get_command(
                    command.command).description = description
                await self.bot.sync_slash_commands_for_guild(command.guild_id)
                await mod_channel.send(f"Beschreibung von Command `{cmd}` geändert zu `{description}`")
        else:
            if self.exists(cmd):
                return False
            command = Command.create(
                command=cmd, description=description, guild_id=guild_id)
            CommandText.create(text=text, command=command.id)
            await self.register_command(command)

        await mod_channel.send(f"[{cmd}] => [{text}] erfolgreich hinzugefügt.")
        return True

    async def remove_text(self, command, command_texts, id):
        command_text = list(command_texts)[id]
        command_text.delete_instance(recursive=True)
        if command.texts.count() == 0:
            await self.remove_command(command)

    async def remove_command(self, command: Command):
        await self.unregister_command(command)
        command.delete_instance(recursive=True)

    def exists(self, cmd):
        for command in self.bot.tree.get_commands():
            if command.name == cmd:
                return True

        return False

    async def init_commands(self):
        for command in Command.select():
            if command.texts.count() > 0:
                await self.register_command(command, sync=False)

    async def register_command(self, command: Command, sync: bool = True):
        @app_commands.command(name=command.command, description=command.description)
        @app_commands.guild_only()
        @app_commands.describe(public="Zeige die Ausgabe des Commands öffentlich, für alle Mitglieder sichtbar.")
        async def process_command(interaction: Interaction, public: bool = True):
            await interaction.response.defer(ephemeral=not public)
            if cmd := Command.get_or_none(Command.command == interaction.command.name):
                texts = list(cmd.texts)
                if len(texts) > 0:
                    await interaction.edit_original_response(content=(random.choice(texts)).text)
                    return

            await interaction.edit_original_response(content="FEHLER! Command wurde nicht gefunden!")

        self.bot.tree.add_command(process_command)
        if sync:
            await self.bot.sync_slash_commands_for_guild(command.guild_id)

    async def unregister_command(self, command: Command):
        self.bot.tree.remove_command(command.command)
        await self.bot.sync_slash_commands_for_guild(command.guild_id)


async def setup(bot: commands.Bot) -> None:
    text_commands = QuickMenu(bot)
    await bot.add_cog(text_commands)
    await text_commands.init_commands()
    # bot.add_view(TextCommandView(text_commands))

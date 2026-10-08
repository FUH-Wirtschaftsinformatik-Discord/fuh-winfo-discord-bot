import logging
from datetime import timedelta

import discord
from discord import File

import utils
from models import Appointment, Attendee

_log = logging.getLogger(__name__)


def embed_state(appointment: Appointment) -> int:
    return 1 if appointment.reminder_sent and appointment.reminder > 0 else 0


class AppointmentView(discord.ui.View):
    """ Buttons under an appointment post.

    Edits go through the interaction (response.edit_message) instead of message.edit, so they
    also work in private channels the bot cannot see. Only deleting needs channel access and
    falls back to clearing the post via the interaction when that is missing. """

    def __init__(self, can_skip: bool):
        super().__init__(timeout=None)
        self.on_skip.disabled = not can_skip

    @discord.ui.button(label='Anmelden', style=discord.ButtonStyle.green, custom_id='appointment_view:accept',
                       emoji="👍")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        appointment = Appointment.get_or_none(Appointment.message == interaction.message.id)
        if appointment is None:
            await interaction.response.defer(thinking=False)
            return

        if appointment.attendees.filter(member_id=interaction.user.id):
            await interaction.response.send_message("Du bist bereits Teilnehmerin dieses Termins.",
                                                    ephemeral=True)
            return

        Attendee.create(appointment=appointment.id, member_id=interaction.user.id)
        await interaction.response.edit_message(embed=appointment.get_embed(embed_state(appointment)))

    @discord.ui.button(label='Abmelden', style=discord.ButtonStyle.red, custom_id='appointment_view:decline', emoji="👎")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        appointment = Appointment.get_or_none(Appointment.message == interaction.message.id)
        if appointment is None:
            await interaction.response.defer(thinking=False)
            return

        attendee = appointment.attendees.filter(member_id=interaction.user.id)
        if not attendee:
            await interaction.response.send_message("Du kannst nur absagen, wenn du vorher zugesagt hast.",
                                                    ephemeral=True)
            return

        attendee[0].delete_instance()
        await interaction.response.edit_message(embed=appointment.get_embed(embed_state(appointment)))

    @discord.ui.button(label='Überspringen', style=discord.ButtonStyle.blurple, custom_id='appointment_view:skip',
                       emoji="⏭️")
    async def on_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        appointment = Appointment.get_or_none(Appointment.message == interaction.message.id)
        if appointment is None or not (interaction.user.id == appointment.author or utils.is_mod(interaction.user)):
            await interaction.response.defer(thinking=False)
            return

        new_date_time = appointment.date_time + timedelta(days=appointment.recurring)
        Appointment.update(date_time=new_date_time, reminder_sent=False).where(
            Appointment.id == appointment.id).execute()
        updated_appointment = Appointment.get(Appointment.id == appointment.id)
        await interaction.response.edit_message(embed=updated_appointment.get_embed(embed_state(updated_appointment)))

    @discord.ui.button(label='Download .ics', style=discord.ButtonStyle.blurple, custom_id='appointment_view:ics',
                       emoji="📅")
    async def ics(self, interaction: discord.Interaction, button: discord.ui.Button):
        if appointment := Appointment.get_or_none(Appointment.message == interaction.message.id):
            await interaction.response.send_message("", file=File(appointment.get_ics_file(),
                                                                  filename=f"{appointment.title}_{appointment.uuid}.ics"),
                                                    ephemeral=True)

    @discord.ui.button(label='Löschen', style=discord.ButtonStyle.gray, custom_id='appointment_view:delete', emoji="🗑")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=False)
        appointment = Appointment.get_or_none(Appointment.message == interaction.message.id)
        if appointment is None or not (interaction.user.id == appointment.author or utils.is_mod(interaction.user)):
            return

        appointment.delete_instance(recursive=True)
        try:
            await interaction.message.delete()
        except discord.Forbidden:
            # No channel access: clear the post through the interaction instead of deleting it.
            _log.warning("Cannot delete appointment post %s in channel %s: missing access, clearing it instead",
                         interaction.message.id, interaction.channel_id)
            await interaction.edit_original_response(content="Dieser Termin wurde gelöscht.", embed=None, view=None)

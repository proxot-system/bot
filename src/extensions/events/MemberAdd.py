import io
import traceback as tb

from interactions import (
	TYPE_MESSAGEABLE_CHANNEL,
	AllowedMentions,
	Extension,
	File,
	listen,
)
from interactions.api.events import MemberAdd

from utilities.database.schemas import ServerData
from utilities.localization.localization import Localization, locale_format
from utilities.textbox.mediagen import Frame, render_frame


class MemberAddEvent(Extension):
	@listen(MemberAdd, delay_until_ready=True)
	async def handler(self, event: MemberAdd):
		guild = event.guild
		loc = Localization(guild)
		server_data: ServerData = await ServerData(_id=guild.id).fetch()
		config = server_data.welcome

		if config.disabled:
			return
		target_channel = guild.system_channel
		channels = list(map(lambda c: str(c.id), guild.channels))
		if config.channel_id and config.channel_id in channels:
			target_channel = guild.get_channel(config.channel_id)

		if not target_channel:
			return
		message = config.message or loc.get("settings.welcome.editor.templates.default", typecheck=str)
		message = await locale_format(
			loc,
			message,
			bot_count=len(event.guild.bots),
			human_count=len(event.guild.humans),
			user_type="bot" if event.member.bot else "human",
			user_name=event.member.display_name,
			server_name=guild.name,
		)
		buffer = io.BytesIO()
		basic_facepic_command = "\\@"
		if not basic_facepic_command in message:
			# default to this face unless they have some in their message already
			message = f"\\@[OneShot/The World Machine/Pancakes]{message}"

		images, durations = await render_frame(Frame(str(message)), False, loc)
		images[0].save(buffer, format="PNG")
		buffer.seek(0)
		try:
			if not event.guild.system_channel:
				return
			if not isinstance(target_channel, TYPE_MESSAGEABLE_CHANNEL):
				raise TypeError(f"tried to send message in a channel where i can't send messages :mumawomp: (guild: {event.guild.id}, channel: {event.guild.system_channel})")
			print(f"Trying to send welcome message (guild: {event.guild.id}, channel: {event.guild.system_channel})")
			return await target_channel.send(
				content=f"-# {event.member.mention}",
				files=File(file=buffer, file_name=f"welcome textbox.png"),
				allowed_mentions=AllowedMentions.all() if server_data.welcome.ping else AllowedMentions.none(),
			)
			
		except Exception as e:
			print(f"Failed to send welcome message. {guild.id}/{target_channel.id}")
			print(tb.format_exc(chain=True))
			await config.update(diabled=True, errored=True)

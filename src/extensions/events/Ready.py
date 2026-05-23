import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable

from interactions import TYPE_MESSAGEABLE_CHANNEL, Embed, Extension, Message, listen
from interactions.api.events import Ready

from utilities.config import get_config
from utilities.emojis import emojis
from utilities.message_decorations import Colors
from utilities.stats import git_log

stuff = {
	"started": False,
	"queue": [],
	"followup_at": None,  # datetime | bool,,,,,,,,,, this becomes Boolean after the first follow up, you can access the datetime version this in clilent.followup_at
}


class ReadyEvent(Extension):
	# WHY DID I MAKE THIS
	@staticmethod
	async def log(
		thing: Callable[[TYPE_MESSAGEABLE_CHANNEL], Any] | Exception,
	) -> Message | Any: ...

	@staticmethod
	def queue(thing: Callable[[TYPE_MESSAGEABLE_CHANNEL], Any] | Exception):
		print(
			f"Queueing some{'thing' if not isinstance(thing, Exception) else ' error'} into the log: {thing}, queue size will be: {len(stuff['queue']) + 1}"
		)
		stuff["queue"].append(thing)

	@staticmethod
	async def followup(timestamp: datetime):
		stuff["followup_at"] = timestamp

	@listen(Ready)
	async def ready(self, event: Ready):
		client = event.client  # <- client is always defined on `event`
		print(f"─ Logged into Discord as {client.user.tag} ({client.user.id})")

	@listen(Ready)
	async def send_logs(self, event: Ready):
		if stuff["started"]:
			return
		stuff["started"] = True
		# this exists to prevent sending more "ready" messages whenever discord disconnects (ready event may fire again) # noqa: ERA001

		client = event.client

		client.ready_at = datetime.now()  # type: ignore
		self.ready_at = client.ready_at  # type: ignore
		from utilities.localization.formatting import fnum

		client = event.client
		channel = get_config("dev.channels.logs", ignore_None=True, typecheck=str)
		if channel:
			channel = await client.fetch_channel(channel)

		extended = get_config("dev.channels.logs", ignore_None=True, typecheck=str)
		if extended:
			extended = await client.fetch_channel(extended)
			assert isinstance(extended, TYPE_MESSAGEABLE_CHANNEL), "extended logs channel must be messageabe"
		assert channel and isinstance(channel, TYPE_MESSAGEABLE_CHANNEL), "logs channel must be messageable"
		ready_delta: timedelta = client.ready_at - client.started_at  # type: ignore
		message: Message | None  # type:ignore
		if get_config("dev.send-startup-message", typecheck=bool):
			version = git_log()
			message = await channel.send(
				embed=Embed(
					description=f"Ready in **{fnum(ready_delta.total_seconds())}**s {emojis['icons']['loading']}\n"
					+ f"<t:{round(client.started_at.timestamp())}:D> <t:{round(client.started_at.timestamp())}:T>. git pushed <t:{round(version.last_updated_at.timestamp())}:R> (#{version.commit})"  # type: ignore
				)
			)

		async def log(
			thing: Callable[[TYPE_MESSAGEABLE_CHANNEL], Any] | Exception,
		) -> Message | Any:
			nonlocal channel
			assert channel and isinstance(channel, TYPE_MESSAGEABLE_CHANNEL), "logs channel must be messageable"
			if isinstance(thing, Callable):
				return await thing(channel)
			elif isinstance(thing, Exception):  ## :pou:
				return await channel.send(
					embed=Embed(description=str(thing), color=Colors.BAD, title="Error"),
					allowed_mentions={"parse": []},
				)
			else:
				print("logged", thing)

		ReadyEvent.log = log

		async def followup(timestamp: datetime):  #
			nonlocal message
			assert message is not None
			client.followup_at = timestamp  # type: ignore
			loadup_delta: timedelta = client.followup_at - client.started_at  # type: ignore
			if get_config("dev.send-startup-message", typecheck=bool):
				embed = message.embeds[0]
				assert embed.description is not None
				embed.description = embed.description.replace(
					" " + emojis["icons"]["loading"],
					f", loaded in **{fnum(loadup_delta.total_seconds())}**s.",
				).replace(" :i:", f", loaded in **{fnum(loadup_delta.total_seconds())}**s.")

				message = await message.edit(embed=embed)
				client.followup_message_edited_at = message.edited_timestamp  # type: ignore

		if isinstance(stuff["followup_at"], datetime):
			await followup(stuff["followup_at"])
		ReadyEvent.followup = followup

		def new_queue(thing: Callable[[TYPE_MESSAGEABLE_CHANNEL], Any] | Exception):
			asyncio.create_task(ReadyEvent.log(thing))

		ReadyEvent.queue = new_queue
		ReadyEvent.stuff = stuff
		while len(stuff["queue"]) > 0:
			for thing in stuff["queue"]:
				await log(thing)
				stuff["queue"].remove(thing)

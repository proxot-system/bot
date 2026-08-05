from interactions import Extension, listen
from interactions.api.events import MessageCreate

from utilities.dev_commands import execute_dev_command


class MessageCreateEvent(Extension):
	@listen(MessageCreate)
	async def handler(self, event: MessageCreate):
		if "flip" in event.message.content and event.message.contains_mention(event.client.user):
			await event.message.reply(file="src/data/images/other/backflip.gif")  # pyright: ignore[reportArgumentType]
		await execute_dev_command(event.message)

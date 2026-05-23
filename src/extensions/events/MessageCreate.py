from interactions import Extension, listen
from interactions.api.events import MessageCreate

from utilities.dev_commands import execute_dev_command


class MessageCreateEvent(Extension):
	@listen(MessageCreate)
	async def handler(self, event: MessageCreate):
		await execute_dev_command(event.message)

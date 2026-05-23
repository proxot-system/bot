from interactions import Extension, listen
from interactions.api.events import MessageCreate

from utilities.dev_commands import execute_dev_command
from utilities.loc_commands import execute_loc_command


class MessageCreateEvent(Extension):
	@listen(MessageCreate)
	async def handler(self, event: MessageCreate):
		client = event.client
		res = await execute_dev_command(event.message)
		if not res:
			await execute_loc_command(event.message)

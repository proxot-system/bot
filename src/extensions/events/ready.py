from interactions import Extension, listen
from interactions.api.events import Ready


class ReadyEvents(Extension):
	@listen(Ready, delay_until_ready=True)
	async def send_logs(self, event: Ready):
		if hasattr(event.client, "followup_message_edited_at"):  # type:ignore
			from extensions.events.readylogger import ReadyLogsEvents

			await ReadyLogsEvents.log(lambda channel: channel.send(content="Ready event triggered!"))

from interactions import Extension, listen
from interactions.api.events import MessageCreate
from interactions.models.discord.components import MediaGalleryComponent, MediaGalleryItem


class FlipEvents(Extension):
	@listen(MessageCreate)
	async def handler(self, event: MessageCreate):
		if "flip" in event.message.content and event.message.contains_mention(event.client.user):
			await event.message.reply(
				components=[  # pyright: ignore[reportArgumentType]
					MediaGalleryComponent(
						items=[
							MediaGalleryItem(
								media="https://cdn.discordapp.com/attachments/1336864890706595852/1534599945448067112/backflip.webp?ex=6a74b712&is=6a736592&hm=8393c2251e5ee8054371991bcdb506fcca9621c98e54accc677da9e3eb040155&",
							)
						]
					)
				]
			)

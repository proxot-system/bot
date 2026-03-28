import random

from interactions import (
	Embed,
	EmbedAttachment,
	Extension,
	OptionType,
	SlashContext,
	contexts,
	integration_types,
	slash_command,
	slash_option,
)

from utilities.emojis import emojis, make_emoji_cdn_url
from utilities.localization.formatting import amperjoin
from utilities.localization.localization import Localization, locale_format
from utilities.message_decorations import Colors


class RollCommand(Extension):
	@slash_command(description="Roll an imaginary dice")
	@slash_option(
		description="What sided dice to roll",
		min_value=0,
		max_value=float("9" * 15),
		name="sides",
		opt_type=OptionType.INTEGER,
		required=True,
	)
	@slash_option(
		description="How many times to roll it",
		min_value=1,
		max_value=234,  # todo: dynamically calculate this from dice side amount (and get it from config)
		name="amount",
		opt_type=OptionType.INTEGER,
	)
	@slash_option(
		description="Whether you want the response to be visible for others in the channel",
		name="public",
		opt_type=OptionType.BOOLEAN,
	)
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def roll(self, ctx: SlashContext, sides: int, amount: int = 1, public: bool = False):
		loc = Localization(ctx, prefix="commands.roll")

		rolls = [0 if sides == 0 else random.randint(1, sides) for _ in range(amount)]

		result = amperjoin([str(roll) for roll in rolls])
		description = await locale_format(loc, loc.get_string("desc"), result=result)

		if len(rolls) > 1:
			description += "\n\n" + await locale_format(loc, loc.get_string("multi"), total=sum(rolls))

		await ctx.send(
			embeds=Embed(
				color=Colors.DEFAULT,
				thumbnail=EmbedAttachment(url=make_emoji_cdn_url(emojis["treasures"]["die"])),
				title=await locale_format(loc, loc.get_string("title"), amount=amount if amount > 1 else "", sides=sides),
				description=description,
			),
			ephemeral=not public,
		)

import asyncio
import re

from interactions import Embed, OptionType, SlashContext, slash_option

from utilities.config import get_config
from utilities.localization.localization import Localization, locale_format
from utilities.message_decorations import Colors, fancy_message
from utilities.textbox.facepics import get_facepic
from utilities.textbox.states import State, states

int_regex = re.compile(r"^\d+$")


@slash_option(
	name="search",
	description='sid here, special: `all` all states, `user:userid/"me"` user\'s states. at end: `!Page:Amount` (ints)',
	opt_type=OptionType.STRING,
	required=False,
)
async def command_(self, ctx: SlashContext, search: str = "user:me!0:5"):
	loc = Localization(ctx)
	await fancy_message(ctx, await locale_format(loc, loc.get_string("generic.loading.checking_developer_status")), ephemeral=True)

	if str(ctx.author.id) not in get_config("dev.whitelist", typecheck=list):
		await asyncio.sleep(3)
		return await fancy_message(
			ctx,
			await locale_format(loc, loc.get_string("generic.errors.not_a_developer")),
			facepic=await get_facepic("OneShot (fan)/Nikonlanger/Jii"),
			edit=True,
		)

	states2show: list[tuple[str, State]] = []
	options = search.split("!")
	filter_str = options[0]

	states2show = list(states.items())

	match filter_str:
		case "all":
			pass
		case _:
			if filter_str.startswith("user:"):
				parts = filter_str.split(":")
				user_id = parts[1] if len(parts) == 2 and parts[1] else "me"

				if not int_regex.match(user_id) and user_id != "me":
					return await ctx.edit(embeds=Embed(color=Colors.BAD, title="Invalid user id"))

				if user_id == "me":
					user_id = str(ctx.user.id)

				states2show = [a for a in states2show if a[1].owner == int(user_id)]

			elif int_regex.match(filter_str):
				if filter_str not in states:
					return await ctx.edit(embeds=Embed(color=Colors.BAD, title=f"Couldn't find sid {filter_str}"))
				states2show = [(filter_str, states[filter_str])]

	if len(states2show) > 0 and len(options) > 1:
		paging = options[1].split(":")

		page_str = paging[0] if len(paging) > 0 and paging[0] else "0"
		amount_str = paging[1] if len(paging) > 1 and paging[1] else "10"

		try:
			page = int(page_str)
			items_per_page = int(amount_str)
		except ValueError:
			return await ctx.edit(embeds=Embed(color=Colors.BAD, title="Invalid Paging syntax"))

		start_index = page * items_per_page

		if start_index >= len(states2show):
			return await ctx.edit(
				embeds=Embed(
					color=Colors.BAD,
					title=f"Page out of bounds, max items: {len(states2show)}",
				)
			)
		states2show = states2show[start_index : start_index + items_per_page]

	if len(states2show) == 0:
		return await ctx.edit(
			embeds=Embed(
				color=Colors.BAD,
				title="Nothing found"
				+ (" (there are no states)" if len(states) == 0 else " (check your filter maybe?)"),
			)
		)

	return await ctx.edit(
		embeds=Embed(
			color=Colors.DEFAULT,
			title=f"Found results: {len(states2show)}",
			description="\n".join(map(lambda a: f"-# {a[0]}:\n```{a[1]}```", states2show)),
		)
	)


exports = {command_}

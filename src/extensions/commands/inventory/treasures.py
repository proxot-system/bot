import asyncio

from interactions import Embed, OptionType, SlashContext, User, contexts, integration_types, slash_option

from utilities.database.schemas import UserData
from utilities.emojis import emojis
from utilities.localization.formatting import fnum
from utilities.localization.localization import Localization, locale_format
from utilities.localization.minis import put_mini
from utilities.message_decorations import Colors, fancy_message
from utilities.shop.fetch_items import fetch_treasure


@integration_types(guild=True, user=True)
@contexts(bot_dm=True)
@slash_option(
	name="target",
	description="Person the inventory of which to check instead",
	opt_type=OptionType.USER,
)
@slash_option(
	name="public",
	description="Whether you want the command to send messages visible for others in the channel",
	opt_type=OptionType.BOOLEAN,
)
async def command(self, ctx: SlashContext, user: User | None = None, public: bool = False):
	loc = Localization(ctx, prefix="commands.inventory")
	treasure_loc = Localization(ctx, prefix="commands.inventory.commands.treasures")

	if user is None:
		user = ctx.user
	if user.bot:
		return await ctx.send(await locale_format(loc, treasure_loc.get_string("empty"), user_id=user.id), ephemeral=True)

	message = asyncio.create_task(
		fancy_message(
			ctx,
			await locale_format(loc, treasure_loc.get_string("loading"), target_type="current" if user == ctx.user else "other"),
			ephemeral=not public,
		)
	)

	all_treasures = await fetch_treasure()
	user_data: UserData = await UserData(_id=user.id).fetch()
	owned_treasures = user_data.owned_treasures
	if len(list(user_data.owned_treasures.items())) == 0:
		await message
		return await fancy_message(ctx, await locale_format(loc, treasure_loc.get_string("empty"), user_id=user.id), edit=True)

	max_amount_length = len(fnum(max(owned_treasures.values(), default=0), locale=loc.locale))
	treasure_string = ""
	for treasure_nid, item in all_treasures.items():
		treasure_metadata: dict = await locale_format(loc, loc.get_string(f"items.treasures", typecheck=dict))

		name = treasure_metadata[treasure_nid]["name"]

		num = fnum(owned_treasures.get(treasure_nid, 0), loc.locale)
		rjust = num.rjust(max_amount_length, " ")
		treasure_string += (
			await locale_format(
				loc,
				loc.get_string("items.entry_template"),
				spacer=rjust.replace(num, ""),
				amount=num,
				icon=emojis["treasures"][treasure_nid],
				name=name,
			)
			+ "\n"
		)

	await ctx.edit(
		embed=Embed(
			description=await locale_format(loc, treasure_loc.get_string("message"), user=user.mention, treasures=treasure_string)
			+ (
				await put_mini(
					treasure_loc,
					"minis.where_to_get_treasure",
					show_up_amount=5,
					type="tip",
					user_id=ctx.user.id,
					pre="\n",
				)
				if not public
				else ""
			),
			color=Colors.DEFAULT,
		),
	)

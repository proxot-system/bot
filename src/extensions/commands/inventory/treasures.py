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
async def command(self, ctx: SlashContext, target: User | None = None, public: bool = False):
	loc = Localization(ctx, prefix="commands.inventory.base")
	treasure_loc = Localization(ctx, prefix="commands.inventory.treasures")

	if target is None:
		target = ctx.user
	if target.bot:
		return await ctx.send(await locale_format(loc, treasure_loc.get("empty"), user_id=target.id), ephemeral=True)

	message = asyncio.create_task(
		fancy_message(
			ctx,
			await locale_format(loc, treasure_loc.get("loading"), target_type="current" if target == ctx.user else "other"),
			ephemeral=not public,
		)
	)

	all_treasures = await fetch_treasure()
	user_data: UserData = await UserData(_id=target.id).fetch()
	owned_treasures = user_data.owned_treasures
	if len(list(user_data.owned_treasures.items())) == 0:
		await message
		return await fancy_message(ctx, await locale_format(loc, treasure_loc.get("empty"), user_id=target.id), edit=True)

	max_amount_length = len(fnum(max(owned_treasures.values(), default=0), locale=loc.locale))
	treasure_string = ""
	for treasure_nid, item in all_treasures.items():
		num = fnum(owned_treasures.get(treasure_nid, 0), loc.locale)
		rjust = num.rjust(max_amount_length, " ")
		treasure_string += (
			await locale_format(
				loc,
				loc.get("items.entry_template"),
				spacer=rjust.replace(num, ""),
				amount=num,
				icon=emojis["treasures"][treasure_nid],
				name=await locale_format(loc, loc.get(f"treasure.{treasure_nid}.name", prefix_override="items", typecheck=str)),
			)
			+ "\n"
		)

	await ctx.edit(
		embed=Embed(
			description=await locale_format(loc, treasure_loc.get("message"), user=target.mention, treasures=treasure_string)
			+ (
				await put_mini(
					treasure_loc,
					"minis.tips.where_to_get_treasure",
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